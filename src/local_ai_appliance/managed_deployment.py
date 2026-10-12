"""Mandatory security gate for installed Windows sessions. No evaluation fallback."""
import base64
import hashlib
import os
from pathlib import Path, PureWindowsPath
import platform
import threading

from .asset_integrity import ordinary
from .data_security import StoragePolicy
from .folders import AccessDenied
from .machine_security import MachineStore, anchor, protected_acl, technical_receipt
from .model import json_bytes
from .release_readiness import verify_signed_bundle
from .security_events import SecurityAudit, WindowsEventSink

SETTINGS = {'reference_roots', 'draft_roots', 'excluded_roots', 'allow_code',
            'allow_code_exports', 'allow_ocr', 'allow_schedules', 'maximum_retention_days'}


def deployment_settings(value, *, windows_paths=False):
    if not isinstance(value, dict) or set(value) != SETTINGS:
        raise AccessDenied('Incomplete administrator deployment settings')
    for name in ('reference_roots', 'draft_roots', 'excluded_roots'):
        if (not isinstance(value[name], list) or not 1 <= len(value[name]) <= 64
                or any(not isinstance(p, str) or not (Path(p).is_absolute() or
                    windows_paths and PureWindowsPath(p).is_absolute()) for p in value[name])):
            raise AccessDenied('Deployment requires explicit absolute storage and exclusion roots')
    for name in ('allow_code', 'allow_code_exports', 'allow_ocr', 'allow_schedules'):
        if type(value[name]) is not bool: raise AccessDenied('Feature decisions must be explicit booleans')
    if (type(value['maximum_retention_days']) is not int or not 1 <= value['maximum_retention_days'] <= 365
            or value['allow_code_exports'] and not value['allow_code']):
        raise AccessDenied('Invalid retention or code-export decision')
    return value


class ManagedDeployment:
    def __init__(self, app, *, store=None, audit=None, lifecycle=None, native_version=None, candidate=False):
        if type(candidate) is not bool:raise AccessDenied('Evaluation mode must be an explicit boolean')
        if candidate:
            from .signed_policy import administrative_access
            administrative_access()
        elif os.name=='nt':
            import ctypes
            if ctypes.windll.shell32.IsUserAnAdmin():
                raise AccessDenied('Ordinary SILO sessions must run without administrator privileges')
        self.candidate = candidate is True
        self.store = store or MachineStore()
        self._owns_store = store is None
        self.app = Path(app).absolute()
        self.record_name = 'evaluation-deployment' if self.candidate else 'deployment'
        self.record = self.store.get(self.record_name)
        self.audit_sink = None
        self.lifecycle = None
        self.model_handles = []
        self.model_native = None
        self._stop, self.failed = threading.Event(), threading.Event()
        self.thread = None
        self._guard = threading.RLock()
        try:
            self.validate_record(self.record)
            self.release = Path(self.record['release_root']).absolute()
            if self.app != self.release / 'payload' / 'app':
                raise AccessDenied('Application path differs from administrator-approved deployment')
            self.settings = deployment_settings(self.record['settings'])
            self.envelope = base64.b64decode(self.record['release_envelope'], validate=True)
            self.release_sha256 = hashlib.sha256(self.envelope).hexdigest()
            if self.release_sha256 != self.record['release_sha256']:
                raise AccessDenied('Approved release signature bytes changed')
            if self.release_sha256 in self.store.get('revoked-releases',[]):
                raise AccessDenied('Application release has been revoked')
            key, digest = anchor(self.store, 'release-anchor')
            self.bundle = verify_signed_bundle(self.release / 'payload', self.envelope, key, digest)
            if os.name == 'nt': self._protect_payload()
            from .security_maintenance import sbom, maintenance_acceptance
            self.sbom = sbom(self.release / 'payload', self.bundle['files'])
            review = self.store.get('maintenance-review')
            if not isinstance(review, dict) or set(review) != {'sequence','envelope'}:
                raise AccessDenied('Administrator must enroll a signed maintenance assessment')
            self.maintenance = base64.b64decode(review['envelope'],validate=True)
            maintenance_acceptance(self.maintenance,self.store,self.sbom,release_sha256=self.release_sha256)
            from .signed_policy import SignedPolicyStore
            from .model_management import validate_model_policy
            self.policy = SignedPolicyStore(self.store)
            if self.policy.current(validate_model_policy) is None:
                raise AccessDenied('Managed deployment requires an active signed model policy')
            self.snapshot={name:self.store.get(name) for name in ('trust-anchor','release-anchor','reviewer-anchor',
                'active-policy','code-acceptance','code-volume','ocr-policy','ocr-acceptance','maintenance-review','advisory-snapshot','revoked-releases')}
            self.native_version = native_version or platform.version()
            self.receipt = base64.b64decode(self.record['technical_receipt'], validate=True)
            if not self.candidate:
                technical_receipt(self.receipt, self.store, release_sha256=self.release_sha256,
                                  native_version=self.native_version)
            self.policy_digest = hashlib.sha256(json_bytes(self.record)).hexdigest()
            self.storage = StoragePolicy(**{k: self.settings[k] for k in
                ('reference_roots', 'draft_roots', 'excluded_roots', 'allow_code_exports')})
            if audit is None:
                self.audit_sink = WindowsEventSink()
                audit = SecurityAudit(self.audit_sink)
            self.audit = audit
            if lifecycle is None:
                from .lifecycle_security import WindowsLifecycle
                lifecycle = WindowsLifecycle()
            self.lifecycle = lifecycle
            self.audit.emit('integrity', 'success', release_sha256=self.release_sha256,
                            policy_sha256=self.policy_digest)
        except BaseException:
            self.close(); raise

    @staticmethod
    def validate_record(record):
        if (not isinstance(record, dict) or set(record) != {'format', 'release_root',
                'release_envelope', 'release_sha256', 'technical_receipt', 'settings'}
                or type(record['format']) is not int or record['format'] != 1
                or not isinstance(record['release_root'], str) or not Path(record['release_root']).is_absolute()):
            raise AccessDenied('Administrator must enroll an authenticated deployment and native evidence')

    def _protect_payload(self):
        from .windows_native import NativeFiles
        from .windows_folders import selected_path
        native = NativeFiles()
        from .machine_security import release_directory
        approved_parent=release_directory()
        if self.release.parent != approved_parent:
            raise AccessDenied('Managed releases must be directly under the Windows Program Files SILO Releases directory')
        drive, components = selected_path(self.release / 'payload')
        handles = [native.open_drive(drive)]
        try:
            for name in components:
                handle = native.open_child(handles[-1], name, directory=True, security=True)
                handles.append(handle)
                info = native.info(handle)
                if info.reparse or info.offline or not info.disk:
                    raise AccessDenied('Installed release ancestor is unsafe')
                if name in {'SILO','Releases',self.release.name,'payload'}:
                    protected_acl(handle,file=True,runtime=True)
            protected_acl(handles[-1],runtime=True)
            def visit(parent, depth=0):
                if depth > 64: raise AccessDenied('Installed release nesting exceeded')
                for name in native.names(parent):
                    if name in {'.', '..'}: continue
                    handle = native.open_child(parent, name, security=True)
                    try:
                        info = native.info(handle)
                        if info.reparse or info.offline or not info.disk or not info.directory and info.links != 1:
                            raise AccessDenied('Installed release object is unsafe')
                        protected_acl(handle, file=True,runtime=True)
                        if info.directory:
                            child = native.open_child(parent, name, directory=True, security=True)
                            try: visit(child, depth + 1)
                            finally: native.close(child)
                    finally: native.close(handle)
            visit(handles[-1])
        finally:
            for handle in reversed(handles): native.close(handle)

    def pin_model(self, path, expected_sha256):
        """Retain a native share-denied data handle through model shutdown."""
        if os.name != 'nt': raise AccessDenied('Model launch pinning requires native Windows')
        from .windows_native import NativeFiles
        from .windows_folders import selected_path
        native=NativeFiles();drive,components=selected_path(path)
        acquired=[native.open_drive(drive)]
        try:
            for index,name in enumerate(components):
                handle=native.open_child(acquired[-1],name,directory=index<len(components)-1)
                acquired.append(handle)
                info=native.info(handle)
                if info.reparse or info.offline or not info.disk:
                    raise AccessDenied('Model storage is unsafe')
            reader=native.open_read(acquired[-1]); acquired.append(reader)
            digest=hashlib.sha256()
            while block:=native.read_chunk(reader,1024*1024):digest.update(block)
            if digest.hexdigest()!=expected_sha256:raise AccessDenied('Model changed before contained launch')
            self.model_native=native;self.model_handles.extend(acquired)
        except BaseException:
            for handle in reversed(acquired):native.close(handle)
            raise

    def check(self):
        with self._guard:
            if self.failed.is_set(): raise AccessDenied('Managed security drift detected; session disabled')
            try:
                self.lifecycle.check()
                if self.store.get(self.record_name) != self.record:
                    raise AccessDenied('Administrator deployment policy changed; restart required')
                if any(self.store.get(name)!=value for name,value in self.snapshot.items()):
                    raise AccessDenied('Administrator security state changed; restart required')
                if self.release_sha256 in self.store.get('revoked-releases',[]):
                    raise AccessDenied('This application release has been revoked')
                from .model_management import validate_model_policy
                self.policy.current(validate_model_policy)
                from .security_maintenance import maintenance_acceptance
                maintenance_acceptance(self.maintenance,self.store,self.sbom,release_sha256=self.release_sha256)
                if not self.candidate:
                    technical_receipt(self.receipt, self.store, release_sha256=self.release_sha256,
                                      native_version=self.native_version)
                # Immutable administrator-owned release files prevent ordinary-user
                # replacement between startup hashing and subsequent execution.
            except Exception:
                self.failed.set()
                self.audit.emit('integrity', 'failed', policy_sha256=self.policy_digest)
                raise

    def monitor(self, container, cancel):
        def monitor():
            try:
                while not self._stop.wait(1):
                    self.check()
                    container.verify_no_loopback_exemption()
                    for process in tuple(container.processes):
                        if not process.closed: container.verify_token(process.info.process)
            except Exception:
                self.failed.set()
                cancel()
        self.thread = threading.Thread(target=monitor, daemon=True, name='SILO-security-monitor')
        self.thread.start()

    def close(self):
        self._stop.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(5)
            if self.thread.is_alive():
                raise AccessDenied('Security monitor did not stop; retain security handles and keep the session closed')
        try:
            if self.lifecycle: self.lifecycle.close()
        finally:
            try:
                for handle in reversed(self.model_handles):self.model_native.close(handle)
                self.model_handles.clear()
                if self.audit_sink: self.audit_sink.close()
            finally:
                if self._owns_store: self.store.close()
