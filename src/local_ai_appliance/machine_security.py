"""Administrator-owned machine policy, independent of project/account secrets.

Native location is obtained from Windows Known Folders, never an environment
variable or ordinary-user CLI override. Portable stores are explicit fixtures.
"""
from contextlib import contextmanager
import base64
import ctypes as C
import hashlib
import os
from pathlib import Path
import re
import tempfile
import threading
import time

from .asset_integrity import ordinary
from .folders import AccessDenied
from .model import json_bytes, strict_json
from .signed_policy import administrative_access, verify_document, canonical

MAX_STATE = 8 * 1024 * 1024
ADMIN_SDDL = 'O:BAD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;0x1200a9;;;BU)'
RELEASE_SDDL = ADMIN_SDDL+'(A;OICI;0x1200a9;;;S-1-15-2-2)'


def known_folder(identifier):
    if os.name != 'nt':
        raise AccessDenied('Machine security requires native Windows')
    import uuid
    # FOLDERID_ProgramData, resolved by the OS rather than %PROGRAMDATA%.
    guid = (C.c_ubyte * 16).from_buffer_copy(uuid.UUID(identifier).bytes_le)
    shell = C.WinDLL('shell32', use_last_error=True)
    shell.SHGetKnownFolderPath.argtypes = [C.c_void_p, C.c_uint32, C.c_void_p, C.POINTER(C.c_void_p)]
    shell.SHGetKnownFolderPath.restype = C.c_int32
    ole = C.WinDLL('ole32')
    ole.CoTaskMemFree.argtypes = [C.c_void_p]
    pointer = C.c_void_p()
    if shell.SHGetKnownFolderPath(C.byref(guid), 0, None, C.byref(pointer)) != 0:
        raise AccessDenied('Windows machine policy location unavailable')
    try:
        return Path(C.wstring_at(pointer))
    finally:
        ole.CoTaskMemFree(pointer)


def machine_directory():
    return known_folder('62ab5d82-fdc1-4dc3-a9dd-070d1d495d97') / 'SILO-Security'


def release_directory():
    return known_folder('6d809377-6af0-444b-8957-a3773f02200e') / 'SILO' / 'Releases'


def protected_acl(handle, *, file=False, runtime=False, private_user=None):
    """Accept only admin/SYSTEM ownership and admin-write, Users-read ACLs."""
    from .windows_native import NativeFiles, HANDLE, U32
    adv = C.WinDLL('advapi32', use_last_error=True)
    kernel = C.WinDLL('kernel32', use_last_error=True)
    NativeFiles._bind(adv, 'GetSecurityInfo', U32, [HANDLE, U32, U32] + [C.POINTER(HANDLE)] * 5)
    NativeFiles._bind(adv, 'GetSecurityDescriptorControl', C.c_int, [HANDLE, C.POINTER(C.c_ushort), C.POINTER(U32)])
    NativeFiles._bind(adv, 'ConvertSecurityDescriptorToStringSecurityDescriptorW', C.c_int,
                      [HANDLE, U32, U32, C.POINTER(HANDLE), C.POINTER(U32)])
    NativeFiles._bind(kernel, 'LocalFree', HANDLE, [HANDLE])
    descriptor, text = HANDLE(), HANDLE()
    control, revision = C.c_ushort(), U32()
    try:
        if adv.GetSecurityInfo(handle, 1, 5, None, None, None, None, C.byref(descriptor)):
            raise AccessDenied('Machine ACL unavailable')
        if (not adv.GetSecurityDescriptorControl(descriptor, C.byref(control), C.byref(revision))
                or not adv.ConvertSecurityDescriptorToStringSecurityDescriptorW(
                    descriptor, 1, 5, C.byref(text), None)):
            raise AccessDenied('Machine ACL inspection failed')
        value = C.wstring_at(text)
        owner, _, dacl = value.partition('D:')
        if owner not in {'O:BA', 'O:SY'} or not file and not control.value & 0x1000:
            raise AccessDenied('Machine security must be administrator-owned with protected inheritance')
        dacl = re.sub(r'^(?:P|AI|AR)+', '', dacl)
        entries = re.findall(r'\(A;([^;]*);([^;]*);;;([^()]+)\)', dacl)
        if len(entries) != (4 if runtime else 3) or ''.join(f'(A;{flags};{mask};;;{sid})' for flags, mask, sid in entries) != dacl:
            raise AccessDenied('Unexpected machine ACL entries')
        rights = {sid: mask.lower() for flags, mask, sid in entries
                  if all(f in {'OI', 'CI', 'ID'} for f in re.findall('..', flags))}
        expected={'SY':{'fa'},'BA':{'fa'},'BU':{'0x1200a9','frfx'}}
        if private_user is not None:
            if runtime or not isinstance(private_user,str) or not private_user.startswith('S-1-'):
                raise AccessDenied('Invalid private code-pool principal')
            expected={'SY':{'fa'},'BA':{'fa'},private_user:{'fa'}}
        if runtime:expected['S-1-15-2-2']={'0x1200a9','frfx'}
        if set(rights)!=set(expected) or any(rights[sid] not in masks for sid,masks in expected.items()):
            raise AccessDenied('Ordinary users and permitted LPAC readers must have read/execute only')
    finally:
        if text.value: kernel.LocalFree(text)
        if descriptor.value: kernel.LocalFree(descriptor)


def create_machine_directory():
    administrative_access()
    path = machine_directory()
    ordinary(path.parent, directory=True)
    if path.exists():
        raise AccessDenied('Machine security already exists; inspect it instead of replacing its ACL')
    kernel, adv = C.WinDLL('kernel32', use_last_error=True), C.WinDLL('advapi32', use_last_error=True)
    class Security(C.Structure):
        _fields_ = [('length', C.c_uint32), ('descriptor', C.c_void_p), ('inherit', C.c_int)]
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [C.c_wchar_p, C.c_uint32, C.POINTER(C.c_void_p), C.c_void_p]
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = C.c_int
    kernel.CreateDirectoryW.argtypes = [C.c_wchar_p, C.POINTER(Security)]
    kernel.CreateDirectoryW.restype = C.c_int
    kernel.LocalFree.argtypes = [C.c_void_p]
    descriptor = C.c_void_p()
    if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(ADMIN_SDDL, 1, C.byref(descriptor), None):
        raise AccessDenied('Machine ACL construction failed')
    try:
        attributes = Security(C.sizeof(Security), descriptor, 0)
        if not kernel.CreateDirectoryW(str(path), C.byref(attributes)):
            raise AccessDenied('Machine security creation failed')
    finally:
        kernel.LocalFree(descriptor)
    return path


class MachineStore:
    administrator_owned = True

    def __init__(self, path=None, *, development=False, writable=False):
        if development:
            if os.name == 'nt' or path is None:
                raise AccessDenied('Portable machine fixtures cannot be selected on Windows')
        elif path is not None and Path(path).absolute() != machine_directory():
            raise AccessDenied('Machine security path cannot be overridden')
        self.path = Path(path).absolute() if development else machine_directory()
        self.development, self.writable = development, writable
        self._guard, self._depth = threading.RLock(), 0
        self.native, self.handles = None, []
        ordinary(self.path, directory=True)
        if development:
            if self.path.stat().st_mode & 0o077:
                raise AccessDenied('Portable fixture directory must be private')
        else:
            from .windows_native import NativeFiles
            from .windows_folders import selected_path
            self.native = NativeFiles()
            drive, components = selected_path(self.path)
            try:
                self.handles.append(self.native.open_drive(drive))
                for name in components:
                    self.handles.append(self.native.open_child(self.handles[-1], name, directory=True, security=True))
                    info = self.native.info(self.handles[-1])
                    if not info.disk or info.reparse or info.offline:
                        raise AccessDenied('Machine security contains an unsupported object')
                protected_acl(self.handles[-1])
            except BaseException:
                self.close()
                raise

    def _read(self):
        if self.development:
            path = self.path / 'records.json'
            if not path.exists(): return {'format': 1, 'generation': 0, 'records': {}}
            if ordinary(path).st_size > MAX_STATE: raise AccessDenied('Machine records oversized')
            data = path.read_bytes()
        else:
            protected_acl(self.handles[-1])
            try:
                handle = self.native.open_child(self.handles[-1], 'records.json', directory=False, security=True)
            except FileNotFoundError:
                return {'format': 1, 'generation': 0, 'records': {}}
            reader = None
            try:
                info=self.native.info(handle)
                if info.reparse or info.offline or not info.disk or info.directory or info.links!=1:
                    raise AccessDenied('Machine record storage is unsafe')
                protected_acl(handle, file=True)
                reader = self.native.open_read(handle)
                data = self.native.read(reader, MAX_STATE)
            finally:
                if reader: self.native.close(reader)
                self.native.close(handle)
        value = strict_json(data)
        if (len(data) > MAX_STATE or not isinstance(value, dict)
                or set(value) != {'format', 'generation', 'records'} or value['format'] != 1
                or type(value['generation']) is not int or value['generation'] < 1
                or not isinstance(value['records'], dict)):
            raise AccessDenied('Machine security records are invalid')
        return value

    @contextmanager
    def transaction(self):
        with self._guard:
            if self._depth:
                self._depth += 1
                try: yield
                finally: self._depth -= 1
                return
            stream = None
            try:
                if self.writable:
                    administrative_access(development=self.development)
                    stream = (self.path / 'admin.lock').open('a+b')
                    if self.development:
                        import fcntl
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                    else:
                        import msvcrt
                        stream.seek(0)
                        if not stream.read(1): stream.write(b'0'); stream.flush()
                        stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                self._depth = 1
                yield
            finally:
                self._depth = 0
                if stream: stream.close()

    def get(self, name, default=None):
        with self.transaction():
            return self._read()['records'].get(name, default)

    def put(self, name, value):
        if not isinstance(name, str):
            raise AccessDenied('Invalid machine record name')
        self.put_many({name: value})

    def put_many(self, records):
        """Publish a validated group in one replace; no partially enrolled deployment."""
        if not self.writable:
            raise AccessDenied('Ordinary sessions cannot write administrator security state')
        if (not isinstance(records, dict) or not records or any(
                not isinstance(name, str) or not re.fullmatch('[a-z0-9-]{1,80}', name)
                for name in records)):
            raise AccessDenied('Invalid machine record name')
        administrative_access(development=self.development)
        with self.transaction():
            state = self._read()
            state['records'].update(records)
            state['generation'] += 1
            data = json_bytes(state)
            if len(data) > MAX_STATE: raise AccessDenied('Machine state exceeds its limit')
            descriptor, temporary = tempfile.mkstemp(dir=self.path, prefix='.admin-')
            try:
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(data); stream.flush(); os.fsync(stream.fileno())
                if not self.development:
                    # File owner must be Administrators, not the enrolling account.
                    _admin_file_owner(temporary)
                os.replace(temporary, self.path / 'records.json')
            finally:
                Path(temporary).unlink(missing_ok=True)

    def close(self):
        for handle in reversed(self.handles): self.native.close(handle)
        self.handles.clear()


def _admin_file_owner(path):
    adv = C.WinDLL('advapi32', use_last_error=True)
    kernel = C.WinDLL('kernel32', use_last_error=True)
    adv.ConvertStringSidToSidW.argtypes = [C.c_wchar_p, C.POINTER(C.c_void_p)]
    adv.ConvertStringSidToSidW.restype = C.c_int
    adv.SetNamedSecurityInfoW.argtypes = [C.c_wchar_p, C.c_uint32, C.c_uint32] + [C.c_void_p] * 4
    adv.SetNamedSecurityInfoW.restype = C.c_uint32
    kernel.LocalFree.argtypes = [C.c_void_p]
    sid = C.c_void_p()
    if not adv.ConvertStringSidToSidW('S-1-5-32-544', C.byref(sid)):
        raise AccessDenied('Administrator owner unavailable')
    try:
        if adv.SetNamedSecurityInfoW(str(path), 1, 1, sid, None, None, None):
            raise AccessDenied('Administrator file ownership failed')
    finally: kernel.LocalFree(sid)


def anchor(store, name):
    record = store.get(name)
    if not isinstance(record, dict) or set(record) != {'key', 'sha256'}:
        raise AccessDenied('Independent machine trust anchor is missing')
    try: key = base64.b64decode(record['key'], validate=True)
    except Exception: raise AccessDenied('Invalid machine trust anchor') from None
    if len(key) != 32 or hashlib.sha256(key).hexdigest() != record['sha256']:
        raise AccessDenied('Machine trust anchor changed')
    return key, record['sha256']


def enroll_anchor(store, name, key, expected_sha256):
    if name not in {'trust-anchor', 'release-anchor', 'reviewer-anchor'}:
        raise AccessDenied('Unknown machine trust role')
    if len(key) != 32 or hashlib.sha256(key).hexdigest() != expected_sha256:
        raise AccessDenied('Trust anchor must match the independently supplied digest')
    with store.transaction():
        if store.get(name) is not None:
            raise AccessDenied('Trust anchor rotation requires a reviewed migration')
        store.put(name, {'key': base64.b64encode(key).decode('ascii'), 'sha256': expected_sha256})


TECHNICAL_CHECKS = frozenset({'network_ipv4', 'network_ipv6', 'network_udp', 'network_dns',
    'network_proxy', 'network_loopback', 'network_lan_ipc', 'network_vpn', 'filesystem_ungranted',
    'filesystem_registry', 'filesystem_profile', 'child_process_denial', 'resource_exhaustion',
    'cancellation_cleanup', 'crash_cleanup', 'reboot', 'sleep_resume', 'runtime_drift',
    'storage_volume_encryption', 'dump_policy', 'sync_exclusion', 'crypto_configuration', 'audit_acl_retention'})


def technical_receipt(envelope, store, *, release_sha256, native_version, clock=time.time):
    key, digest = anchor(store, 'reviewer-anchor')
    value = verify_document(envelope, key, digest, limit=128 * 1024)
    if (not isinstance(value, dict) or set(value) != {'format', 'release_sha256', 'native_version',
            'boundary', 'expires', 'checks'} or type(value['format']) is not int or value['format'] != 1
            or value['release_sha256'] != release_sha256 or value['native_version'] != native_version
            or value['boundary'] != 'silo-lpac-managed-2'
            or type(value['expires']) not in {int, float} or value['expires'] <= clock()
            or not isinstance(value['checks'], dict) or set(value['checks']) != TECHNICAL_CHECKS):
        raise AccessDenied('Native technical acceptance does not match this release, OS, boundary or expiry')
    for result in value['checks'].values():
        if (not isinstance(result, dict) or set(result) != {'status', 'evidence_sha256'}
                or result['status'] != 'pass' or not isinstance(result['evidence_sha256'], str)
                or not re.fullmatch('[a-f0-9]{64}', result['evidence_sha256'])):
            raise AccessDenied('Incomplete native security evidence; failures and skips cannot enable launch')
    return value


def ocr_receipt(store, configuration, *, release_sha256, native_version, clock=time.time):
    record=store.get('ocr-acceptance')
    if not isinstance(record,dict) or set(record)!={'envelope','sha256'}:
        raise AccessDenied('Independent native OCR review is missing')
    envelope=base64.b64decode(record['envelope'],validate=True)
    if hashlib.sha256(envelope).hexdigest()!=record['sha256']:
        raise AccessDenied('OCR acceptance bytes changed')
    key,digest=anchor(store,'reviewer-anchor')
    value=verify_document(envelope,key,digest,limit=128*1024)
    checks={'network_denial','ungranted_files_denied','profile_registry_denied',
            'child_process_denied','malformed_image_bounded','cancellation_cleanup'}
    if (not isinstance(value,dict) or set(value)!={'format','expires','release_sha256','native_version',
            'runtime_policy_sha256','boundary','checks'} or type(value['format']) is not int or value['format']!=1
            or type(value['expires']) not in {int,float} or value['expires']<=clock()
            or value['release_sha256']!=release_sha256 or value['native_version']!=native_version
            or value['boundary']!='silo-lpac-managed-2'
            or value['runtime_policy_sha256']!=hashlib.sha256(canonical(configuration)).hexdigest()
            or not isinstance(value['checks'],dict) or set(value['checks'])!=checks):
        raise AccessDenied('OCR review does not match this exact runtime, release, OS or boundary')
    for result in value['checks'].values():
        if (not isinstance(result,dict) or set(result)!={'status','evidence_sha256'} or result['status']!='pass'
                or not isinstance(result['evidence_sha256'],str) or not re.fullmatch('[a-f0-9]{64}',result['evidence_sha256'])):
            raise AccessDenied('Incomplete OCR native acceptance')
    return value
