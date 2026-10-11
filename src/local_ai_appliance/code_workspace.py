"""Host-owned disposable code state and atomic reviewed artifact-set export.

This controller never executes Python itself. A qualified native runner must
implement execute(); importing or editing files cannot authorize execution.
"""
from dataclasses import dataclass, asdict
import hashlib
import io
import json
import secrets
import threading
import zipfile

from .conversation import Conversation
from .execution_policy import ExecutionPolicy
from .folders import AccessDenied
from .model import json_bytes
from .windows_folders import parts

MAX_FILE = 1024 * 1024
MAX_FILES = 64
SUFFIXES = {'.py', '.txt', '.md', '.json', '.csv', '.png'}


def code_path(path):
    import posixpath
    components = parts(path)
    if len(components) > 8 or components[0].casefold() in {'inputs', 'silo_plot', 'silo_plot.py'}:
        raise AccessDenied('Reserved or deeply nested code path')
    if posixpath.splitext(path)[1].lower() not in SUFFIXES:
        raise AccessDenied('Unsupported code artifact type')
    return path


def digest(data):
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class RunResult:
    exit_code: int
    stdout: str
    stderr: str
    files: tuple[tuple[str, bytes], ...]
    boundary: str


@dataclass(frozen=True)
class Export:
    id: str
    destination_folder: str
    destination_path: str
    permission_revision: int
    files: tuple[tuple[str, str, int], ...]
    sha256: str
    content: bytes


class CodeWorkspace:
    def __init__(self, workspace, runner, *, policy=None, configuration='unqualified', checkpoint=lambda: None):
        self.workspace, self.runner = workspace, runner
        self.policy = policy or ExecutionPolicy()
        self.configuration, self.checkpoint = configuration, checkpoint
        self._lock = threading.RLock()
        self.id = secrets.token_hex(16)
        self.revision = workspace.broker.revision
        self.files, self.inputs, self.sources = {}, {}, {}
        self.runs = []
        self.attempts = 0
        self._running = False
        self.exports, self.reviewed = {}, {}
        self.cancelled, self.closed = False, False

    def check(self):
        self.checkpoint()
        if self.closed or self.cancelled or self.workspace.broker.revision != self.revision:
            raise AccessDenied('Code workspace expired, cancelled, or permissions changed')
        if not Conversation.verify_sources(self.workspace, tuple(self.sources.values())):
            self.exports.clear(); self.reviewed.clear()
            raise AccessDenied('A staged source changed or was revoked')

    def _inventory(self, files):
        if not isinstance(files, dict) or len(files) > MAX_FILES:
            raise AccessDenied('Code file inventory exceeded')
        seen, total = set(), sum(len(v) for v in self.inputs.values())
        for path, data in files.items():
            code_path(path)
            if path.casefold() in seen or type(data) is not bytes or len(data) > MAX_FILE:
                raise AccessDenied('Aliased or oversized code artifact')
            seen.add(path.casefold()); total += len(data)
        if total > self.policy.max_workspace_bytes:
            raise AccessDenied('Code workspace byte budget exceeded')

    def stage(self, source, name):
        with self._lock:
            self.check()
            if self._running: raise AccessDenied('Code workspace is executing')
            if len(parts(name)) != 1 or name.casefold() in {p.casefold() for p in self.inputs}:
                raise AccessDenied('Stage a unique ordinary input filename')
            folder = next((f for f in self.workspace.broker.folders() if f.id == source.folder_id), None)
            if folder is None or folder.access != 'read-only':
                raise AccessDenied('Code inputs require a Reference grant')
            data = self.workspace.broker.read_file(source.folder_id, source.path)
            if digest(data) != source.sha256:
                raise AccessDenied('Read the exact current source before staging')
            if len(self.inputs) >= 16 or sum(map(len, self.inputs.values())) + len(data) > self.policy.max_workspace_bytes:
                raise AccessDenied('Input staging budget exceeded')
            self.inputs[name] = data
            self.sources[name] = source
            try: self._inventory(self.files)
            except BaseException:
                del self.inputs[name]; del self.sources[name]
                raise
            self.exports.clear(); self.reviewed.clear()
            self.runs.clear()
            return {'path':'inputs/'+name, 'sha256':source.sha256, 'size':len(data)}

    def write(self, path, text, expected_sha256=None):
        with self._lock:
            self.check(); code_path(path)
            if self._running: raise AccessDenied('Code workspace is executing')
            if not isinstance(text, str): raise AccessDenied('Code edits require UTF-8 text')
            data = text.encode('utf-8')
            existing = self.files.get(path)
            if existing is None:
                if expected_sha256 is not None: raise AccessDenied('Cannot revise a missing file')
            elif expected_sha256 != digest(existing):
                raise AccessDenied('Read the current file hash before revising it')
            proposed = {**self.files, path:data}
            self._inventory(proposed)
            self.files = proposed
            self.exports.clear(); self.reviewed.clear()
            return {'path':path, 'sha256':digest(data), 'size':len(data), 'published':False}

    def read(self, path):
        with self._lock:
            self.check(); code_path(path)
            if path not in self.files: raise AccessDenied('Code file is unavailable')
            data = self.files[path]
            try: text = data.decode('utf-8')
            except UnicodeError: raise AccessDenied('Binary artifact: inspect its metadata and host preview') from None
            if len(data) > 32*1024: raise AccessDenied('Code text exceeds the read-tool limit')
            return {'path':path, 'text':text, 'sha256':digest(data)}

    def listing(self):
        with self._lock:
            self.check()
            return [{'path':p, 'size':len(b), 'sha256':digest(b)} for p,b in sorted(self.files.items())]

    def run(self, entrypoint, arguments=()):
        with self._lock:
            self.check(); code_path(entrypoint)
            if not entrypoint.endswith('.py') or entrypoint not in self.files:
                raise AccessDenied('Select an existing workspace Python entrypoint')
            if not getattr(self.runner, 'available', False):
                raise AccessDenied('Native execution boundary has not been accepted for this configuration')
            if self._running or self.attempts >= 8: raise AccessDenied('Execution busy or budget exhausted')
            # No shell/executable/options. An optional argument is a staged input name.
            if not isinstance(arguments, (tuple,list)) or len(arguments) > 1:
                raise AccessDenied('Only one staged input argument is supported')
            if arguments and arguments[0] not in self.inputs:
                raise AccessDenied('Execution argument must identify a staged input')
            before = dict(self.files)
            self.exports.clear(); self.reviewed.clear()
            self.attempts += 1
            self._running = True
        try:
            result = self.runner.execute(before, dict(self.inputs), entrypoint, tuple(arguments), self.policy)
        except BaseException:
            self.cancel()
            raise
        finally:
            with self._lock: self._running = False
        with self._lock:
            try:
                self.check()
                if (not isinstance(result, RunResult) or type(result.exit_code) is not int
                        or not 0 <= result.exit_code <= 0xffffffff or not isinstance(result.boundary,str)
                        or not 1 <= len(result.boundary) <= 128):
                    raise AccessDenied('Runner returned invalid host metadata')
                if (not isinstance(result.stdout,str) or not isinstance(result.stderr,str)
                        or len(result.stdout.encode())+len(result.stderr.encode()) > self.policy.max_output_bytes
                        or not isinstance(result.files, tuple) or len(result.files) > MAX_FILES):
                    raise AccessDenied('Runner returned oversized output')
                files = dict(result.files)
                if len(files) != len(result.files): raise AccessDenied('Runner returned duplicate output paths')
                self._inventory(files)
            except BaseException:
                self.runs.clear()
                self.cancel()
                raise
            self.files = files
            record = {'run':len(self.runs)+1, 'entrypoint':entrypoint, 'arguments':list(arguments),
                      'exit_code':result.exit_code, 'boundary':result.boundary,
                      'script_sha256':digest(before[entrypoint]),
                      'files':[{'path':p,'sha256':digest(b),'size':len(b)} for p,b in sorted(files.items())]}
            self.runs.append(record)
            return {**record, 'stdout':result.stdout, 'stderr':result.stderr, 'published':False}

    def prepare_export(self, destination_folder, destination_path):
        with self._lock:
            self.check()
            if self._running: raise AccessDenied('Code workspace is executing')
            if not self.files or not self.runs or self.runs[-1]['exit_code'] != 0:
                raise AccessDenied('A successful actual run is required before preparing an artifact export')
            if self.runs[-1]['files'] != [{'path':p,'sha256':digest(b),'size':len(b)} for p,b in sorted(self.files.items())]:
                raise AccessDenied('Workspace changed after execution; run and inspect it again')
            if not destination_path.endswith('.zip'):
                raise AccessDenied('Publish the reviewed artifact set as one new ZIP file')
            if len(self.exports)>=4: raise AccessDenied('Discard a pending export before preparing another')
            self.workspace.broker.validate_create(destination_folder, destination_path)
            from .code_artifacts import validate_artifact
            for path,data in self.files.items(): validate_artifact(path,data)
            manifest = {'format_version':1,'workspace':self.id,'configuration':self.configuration,
                        'policy':asdict(self.policy),'permission_revision':self.revision,
                        'inputs':[{'staged_path':'inputs/'+p, 'folder_id':s.folder_id, 'source_path':s.path,
                                   'sha256':s.sha256, 'locator':s.locator, 'source_reference':s.reference}
                                  for p,s in sorted(self.sources.items())], 'runs':self.runs,
                        'files':[{'path':p,'size':len(b),'sha256':digest(b)} for p,b in sorted(self.files.items())]}
            content = io.BytesIO()
            with zipfile.ZipFile(content,'w',zipfile.ZIP_DEFLATED) as archive:
                for path,data in [('silo-manifest.json',json_bytes(manifest)), *sorted(self.files.items())]:
                    if path=='silo-manifest.json' and path in self.files:
                        raise AccessDenied('Reserved host manifest filename')
                    item=zipfile.ZipInfo(path,(2026,1,1,0,0,0)); item.compress_type=zipfile.ZIP_DEFLATED
                    item.external_attr=0o100644 << 16
                    archive.writestr(item,data)
            data=content.getvalue()
            if len(data)>min(MAX_FILE,self.workspace.broker.max_file_bytes):
                raise AccessDenied('Export ZIP exceeds the destination broker limit')
            export=Export(secrets.token_hex(16),destination_folder,destination_path,self.revision,
                          tuple((p,digest(b),len(b)) for p,b in sorted(self.files.items())),digest(data),data)
            self.exports[export.id]=export
            return {'export_id':export.id,'files':manifest['files'],'sha256':export.sha256,'status':'awaiting_host_review'}

    def review(self, identifier):
        with self._lock:
            self.check()
            if identifier not in self.exports: raise AccessDenied('Export is unavailable')
            export=self.exports[identifier]
            self.workspace.broker.validate_create(export.destination_folder,export.destination_path)
            self.reviewed[identifier]=export
            return export

    def approve(self, identifier):
        with self._lock:
            self.check()
            export=self.reviewed.pop(identifier,None)
            if export is None or export != self.exports.pop(identifier,None):
                raise AccessDenied('Review the exact current export before approval')
            self.workspace.broker.write_file(export.destination_folder,export.destination_path,export.content)
            return export

    def discard(self, identifier):
        with self._lock:
            self.exports.pop(identifier,None); self.reviewed.pop(identifier,None)

    def cancel(self):
        with self._lock:
            self.cancelled=True
            self.exports.clear(); self.reviewed.clear()
        self.runner.cancel()

    def close(self):
        self.cancel()
        self.runner.close()
        with self._lock:
            self.closed=True; self.files.clear(); self.inputs.clear(); self.sources.clear(); self.runs.clear()
