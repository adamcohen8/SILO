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
MAX_FILES = 4096
SUFFIXES = {'.py','.txt','.md','.json','.csv','.png','.js','.jsx','.cjs','.mjs','.ts','.tsx','.rs','.c','.cpp','.h','.hpp','.toml','.yaml','.yml','.ini','.cfg','.css','.html','.xml','.sql','.sh','.ps1','.lock'}
FILENAMES = {'Dockerfile','Makefile','LICENSE','.gitignore','.gitattributes'}


def code_path(path):
    import posixpath
    components = parts(path)
    if len(components) > 8 or components[0].casefold() in {'inputs', 'silo_plot', 'silo_plot.py'}:
        raise AccessDenied('Reserved or deeply nested code path')
    if any(p.casefold() in {'.git','.silo','.env','id_rsa','id_ed25519'} or p.casefold().startswith('.env.') for p in components):
        raise AccessDenied('Repository metadata and credential files are excluded')
    if posixpath.splitext(path)[1].lower() not in SUFFIXES and components[-1] not in FILENAMES:
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
    def __init__(self, workspace, runner, *, policy=None, configuration='unqualified', checkpoint=lambda: None, max_attempts=None, work_policy=None):
        from .work_policy import WorkPolicy
        self.work_policy = work_policy or WorkPolicy()
        if not isinstance(self.work_policy, WorkPolicy): raise ValueError('Invalid work policy')
        if max_attempts is None: max_attempts = self.work_policy.execution_attempts
        self.workspace, self.runner = workspace, runner
        self.policy = policy or ExecutionPolicy()
        self.configuration, self.checkpoint = configuration, checkpoint
        if max_attempts is not None and (type(max_attempts) is not int or max_attempts < 1):
            raise ValueError("Invalid optional benchmark execution limit")
        self.max_attempts = max_attempts
        self._lock = threading.RLock()
        self.id = secrets.token_hex(16)
        self.revision = workspace.broker.revision
        self.files, self.inputs, self.sources = {}, {}, {}
        self.runs = []
        self.retired_runs = 0
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
        seen, directories = set(), {}
        if any(not isinstance(path,str) for path in files): raise AccessDenied('Invalid code path')
        all_paths={path.casefold() for path in files}
        total=sum(len(v) for v in self.inputs.values())
        for path, data in files.items():
            code_path(path)
            components=path.split('/')
            for i in range(1,len(components)):
                prefix='/'.join(components[:i]);key=prefix.casefold()
                if key in all_paths or key in directories and directories[key]!=prefix:
                    raise AccessDenied('File/directory or directory-case alias in code workspace')
                directories[key]=prefix
            if path.casefold() in seen or type(data) is not bytes or len(data) > MAX_FILE:
                raise AccessDenied('Aliased or oversized code artifact')
            seen.add(path.casefold()); total += len(data)
        if total > self.policy.max_workspace_bytes:
            raise AccessDenied('Code workspace byte budget exceeded')

    def _clear_runs(self):
        self.retired_runs += len(self.runs)
        self.runs.clear()

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
            self._clear_runs()
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

    def read(self, path, start_line=1, end_line=None):
        with self._lock:
            self.check(); code_path(path)
            if path not in self.files: raise AccessDenied('Code file is unavailable')
            data = self.files[path]
            try: text = data.decode('utf-8')
            except UnicodeError: raise AccessDenied('Binary artifact: inspect its metadata and host preview') from None
            if type(start_line) is not int or start_line<1: raise AccessDenied('Invalid line range')
            lines=text.splitlines(keepends=True)
            if end_line is None: end_line=min(len(lines),start_line+199)
            if type(end_line) is not int or end_line<start_line or end_line-start_line>=200:
                if not lines and start_line==1 and end_line==0: end_line=1
                else: raise AccessDenied('Read at most 200 lines per page')
            excerpt=''.join(lines[start_line-1:end_line])
            if len(excerpt.encode())>32*1024: raise AccessDenied('Line range exceeds the read frame; request fewer lines')
            return {'path':path,'text':excerpt,'sha256':digest(data),'start_line':start_line,
                    'end_line':min(end_line,len(lines)),'total_lines':len(lines),
                    'next_start_line':end_line+1 if end_line<len(lines) else None}

    def listing(self):
        with self._lock:
            self.check()
            return [{'path':p, 'sha256':digest(b), 'size':len(b)} for p,b in sorted(self.files.items())]

    def page(self, *, offset=0, limit=100):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise AccessDenied("Invalid file inventory page")
        items = self.listing()
        selected=items[offset:offset+limit]
        while len(json_bytes(selected))>32*1024: selected.pop()
        return {"files": selected, "total_files": len(items),
                "next_offset": offset+len(selected) if offset+len(selected) < len(items) else None,
                "inventory_sha256": digest(json_bytes(items))}

    def patch(self, path, old_text, new_text, expected_sha256):
        with self._lock:
            self.check(); code_path(path)
            data=self.files.get(path)
            if data is None or digest(data)!=expected_sha256: raise AccessDenied('Patch preimage changed')
            text=data.decode('utf-8')
            if not old_text or text.count(old_text)!=1: raise AccessDenied('Patch requires one exact unique preimage')
            return self.write(path,text.replace(old_text,new_text,1),expected_sha256)

    def delete(self, path, expected_sha256):
        with self._lock:
            self.check(); code_path(path)
            if self._running: raise AccessDenied('Code workspace is executing')
            if path not in self.files or digest(self.files[path])!=expected_sha256: raise AccessDenied('Delete preimage changed')
            del self.files[path]; self.exports.clear(); self.reviewed.clear(); self._clear_runs()
            return {'path':path,'deleted':True,'published':False}

    def rename(self, path, destination, expected_sha256):
        with self._lock:
            self.check(); code_path(path); code_path(destination)
            if self._running: raise AccessDenied('Code workspace is executing')
            if path not in self.files or digest(self.files[path])!=expected_sha256: raise AccessDenied('Rename preimage changed')
            if destination.casefold() in {p.casefold() for p in self.files}: raise AccessDenied('Rename destination exists')
            proposed=dict(self.files); proposed[destination]=proposed.pop(path); self._inventory(proposed)
            self.files=proposed; self.exports.clear(); self.reviewed.clear(); self._clear_runs()
            return {'path':destination,'sha256':digest(self.files[destination]),'published':False}

    def search(self, query, *, offset=0, limit=50):
        with self._lock:
            self.check()
            if not isinstance(query,str) or not 1<=len(query)<=256 or type(offset)is not int or offset<0:
                raise AccessDenied('Invalid literal workspace search')
            if type(limit)is not int or not 1<=limit<=100: raise AccessDenied('Invalid search page')
            matches=[]; seen=0
            for path,data in sorted(self.files.items()):
                if path.endswith('.png'): continue
                for number,line in enumerate(data.decode('utf-8').splitlines(),1):
                    if query.casefold() in line.casefold():
                        if seen>=offset and len(matches)<limit:
                            matches.append({'path':path,'line':number,'text':line[:256],'sha256':digest(data)})
                        seen+=1
            while len(json_bytes(matches))>32*1024: matches.pop()
            return {'matches':matches,'next_offset':offset+len(matches) if seen>offset+len(matches) else None,
                    'total_matches':seen,'inventory_sha256':digest(json_bytes(self.listing()))}

    def diff(self, baseline):
        with self._lock:
            self.check()
            return self._diff(baseline)

    def _diff(self, baseline):
        import difflib
        self.check()
        changes=[]
        for path in sorted(set(baseline)|set(self.files)):
            before,after=baseline.get(path,b''),self.files.get(path,b'')
            if before==after and (path in baseline)==(path in self.files): continue
            changes.append({'path':path,'before_sha256':digest(before) if path in baseline else None,
                'after_sha256':digest(after) if path in self.files else None,
                'diff':self._patch_text(path,before,after,path in baseline,path in self.files)
                    if not path.endswith('.png') else '[binary bytes changed]'})
        return changes

    @staticmethod
    def _patch_text(path, before, after, existed, remains):
        import difflib
        def quote(value):
            return '"'+''.join(('\\'+chr(b) if b in {34,92} else chr(b) if 32<=b<127 else f'\\{b:03o}')
                                for b in value.encode('utf-8'))+'"'
        left,right=quote('a/'+path),quote('b/'+path)
        header=f'diff --git {left} {right}\n'
        if not existed: header+='new file mode 100644\n'
        elif not remains: header+='deleted file mode 100644\n'
        if not before and not after:
            header+='index '+('0000000..e69de29' if not existed else 'e69de29..0000000')+'\n'
        lines=difflib.unified_diff(before.decode('utf-8').splitlines(True),after.decode('utf-8').splitlines(True),
            fromfile=left if existed else '/dev/null',tofile=right if remains else '/dev/null')
        return header+''.join(line if line.endswith('\n') else line+'\n\\ No newline at end of file\n' for line in lines)

    def run(self, entrypoint, arguments=()):
        return self._run(entrypoint,arguments)

    def run_operation(self, operation, entrypoint):
        if operation not in {'run','test','check','build'}: raise AccessDenied('Unsupported build operation')
        if not callable(getattr(self.runner,'execute_operation',None)):
            raise AccessDenied('Select a separately qualified build environment first')
        return self._run(entrypoint,(),operation=operation)

    def language_query(self,action,path,*,line=1,column=1):
        with self._lock:
            self.check(); code_path(path)
            if self._running or not getattr(self.runner,'available',False) or not hasattr(self.runner,'language_query'):
                raise AccessDenied('A ready separately qualified language environment is required')
            before=dict(self.files); self._running=True
        try:
            result=self.runner.language_query(before,path,action,line=line,column=column)
            with self._lock:
                self.check()
                if self.files!=before: raise AccessDenied('Source changed during semantic navigation')
            return result
        finally:
            with self._lock: self._running=False

    def _run(self, entrypoint, arguments, *, operation=None):
        with self._lock:
            self.check(); code_path(entrypoint)
            if (operation is None and not entrypoint.endswith('.py')) or entrypoint not in self.files:
                raise AccessDenied('Select an existing workspace Python entrypoint')
            if not getattr(self.runner, 'available', False):
                raise AccessDenied('Native execution boundary has not been accepted for this configuration')
            if self._running or (self.max_attempts is not None and self.attempts >= self.max_attempts): raise AccessDenied('Execution busy or budget exhausted')
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
            if operation is None:
                result = self.runner.execute(before, dict(self.inputs), entrypoint, tuple(arguments), self.policy)
            else:
                result = self.runner.execute_operation(before,dict(self.inputs),operation,entrypoint,self.policy)
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
                self._clear_runs()
                self.cancel()
                raise
            self.files = files
            record = {'run':self.attempts, 'entrypoint':entrypoint, 'arguments':list(arguments),
                      'exit_code':result.exit_code, 'boundary':result.boundary,
                      'script_sha256':digest(before[entrypoint]),
                      'files':[{'path':p,'sha256':digest(b),'size':len(b)} for p,b in sorted(files.items())]}
            from .test_feedback import feedback
            record['feedback']=feedback(result.exit_code,result.stdout,result.stderr)
            if operation is not None: record['operation']=operation
            self.runs.append(record)
            if len(self.runs) > 16:
                self.retired_runs += len(self.runs)-16
                self.runs = self.runs[-16:]
            preview=record['files'][:100]
            while len(json_bytes(preview))>32*1024: preview.pop()
            return {**record, 'files':preview, 'total_files':len(record['files']),
                    'inventory_sha256':digest(json_bytes(record['files'])),
                    'inventory_partial':len(record['files'])>len(preview),
                    'stdout':result.stdout, 'stderr':result.stderr, 'published':False}

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
                        'older_runs_omitted':self.retired_runs,
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
            self.closed=True; self.files.clear(); self.inputs.clear(); self.sources.clear(); self._clear_runs()
            if hasattr(self,'navigation'): self.navigation.cache.clear()
