"""Project-local Windows evaluation service. Never enables production mode.

The Qt host owns grants and approvals. Model, graph and parsers execute in
zero-capability AppContainer jobs. No TCP endpoint, automatic download or
fallback is exposed. This service deliberately requires the prepared assets.
"""
import ctypes as C
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import sys
import threading
import time

from .agent import AgentResult, DocumentAgent
from .folders import AccessDenied
from .windows_container import AppContainer, U32
from .windows_model import WindowsUnixConnection
from .windows_workspace import BrokerSession, ContainedWorkspace
from .workspace import DraftTools
from .worker_errors import MESSAGES
from .directory_requests import list_directory_request
from .conversation import Conversation
from .mentions import MentionCatalog, parsed_mentions
from .model import json_bytes
from .agent_instructions import load_instructions
from .asset_integrity import verify_inference
from .evaluation_install import installed_config, verify_release
from .configuration_catalog import authorize_configuration
from .model_adapters import server_command


class Cancelled(Exception):
    pass


class ServerDrain:
    """Drain indefinitely without keeping prompts, documents or response logs.

Only two fixed GPU startup markers are retained as booleans. Close owns and
joins the readers before the process handles can be released.
"""
    def __init__(self, process, *, gpu_layers=53):
        self.process, self.failed = process, threading.Event()
        self.full_gpu = False
        self.gpu_marker = f'offloaded {gpu_layers}/{gpu_layers} layers to GPU'.encode('ascii')
        self.threads = [threading.Thread(target=self.read, args=(i,), daemon=True) for i in (1, 2)]
        process.kernel.CloseHandle(process.parent_handles[0])
        process.parent_handles[0] = None
        for thread in self.threads:
            thread.start()

    def read(self, index):
        pending = b''
        try:
            while True:
                buffer, count = C.create_string_buffer(8192), U32()
                if not self.process.kernel.ReadFile(self.process.parent_handles[index], buffer, len(buffer), C.byref(count), None):
                    return
                if not count.value:
                    return
                pending = (pending + buffer.raw[:count.value])[-16384:]
                if self.gpu_marker in pending:
                    self.full_gpu = True
                # Keep only the overlap necessary to detect a split startup marker.
                pending = pending[-80:]
        finally:
            self.failed.set()

    def stop(self):
        self.process.kernel.TerminateJobObject(self.process.job, 126)
        self.process.kernel.WaitForSingleObject(self.process.info.process, 10000)
        for thread in self.threads:
            thread.join(10)
            if thread.is_alive():
                raise OSError('Model reader did not stop safely')


class WindowsSession:
    def __init__(self, root, *, model_manager=None):
        self.root = Path(root).resolve()
        self.model_manager = model_manager
        self.model_profile = None
        self.installation = installed_config(self.root)
        self.state = (Path(self.installation['state_root']) if self.installation else self.root/'artifacts/windows-ui')
        self.state.mkdir(parents=True, exist_ok=True)
        self.container = self.workspace = self.server = self.drain = None
        self.endpoint = self.token = self.directory = None
        self.executable = self.worker = None
        self.active = None
        self.cancelled = threading.Event()
        self._guard = threading.RLock()
        self._operation = threading.RLock()
        self.ready = False
        self.closed = False
        self.evidence = {'parser_tokens': [], 'worker_tokens': []}
        self.conversation = Conversation()
        self.instructions = ''
        self.code = None
        # Share-denied lock covers the evaluation staging tree and one GPU slot.
        import msvcrt
        self._lockfile = (self.state/'session.lock').open('a+b')
        self._lockfile.seek(0)
        if not self._lockfile.read(1):
            self._lockfile.write(b'0')
            self._lockfile.flush()
        self._lockfile.seek(0)
        try:
            msvcrt.locking(self._lockfile.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self._lockfile.close()
            raise RuntimeError('The local evaluation interface is already running.') from None

    def check_cancelled(self):
        if self.cancelled.is_set():
            raise Cancelled('Request cancelled')

    @staticmethod
    def digest(path):
        result = hashlib.sha256()
        with path.open('rb') as stream:
            while chunk := stream.read(8*1024*1024):
                result.update(chunk)
        return result.hexdigest()

    def verify_assets(self):
        if getattr(self, 'model_manager', None) is not None:
            runtime, model, self.model_profile = self.model_manager.launch_assets(cancel=self.check_cancelled)
            return runtime, model
        identifier = ('nemotron-4090-cp314-evaluation-1' if getattr(self, 'installation', None)
                      else 'nemotron-4090-cp312-evaluation-1')
        authorize_configuration(self.root, identifier, operation='launch')
        return verify_inference(self.root, self.check_cancelled)

    def stage(self):
        if self.installation:
            release = self.root.parent.parent
            digest = (release/'release-manifest.sha256').read_text(encoding='ascii').strip()
            verify_release(release, digest)
            sdk = self.root.parent/'worker'
            self.worker, self.executable = sdk/'contained_agent_worker.py', sdk/'python.exe'
            return sdk
        sdk = self.root/'artifacts/isolation-evaluation/python'
        sdk.mkdir(parents=True, exist_ok=True)
        base = Path(sys.base_prefix)
        for name in ('python.exe', f'python{sys.version_info.major}{sys.version_info.minor}.dll', 'vcruntime140.dll', 'vcruntime140_1.dll'):
            if (base/name).exists():
                shutil.copy2(base/name, sdk/name)
        for name in ('Lib', 'DLLs'):
            self.check_cancelled()
            shutil.copytree(base/name, sdk/name, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('__pycache__', 'site-packages'))
        shutil.copytree(Path(sys.prefix)/'Lib/site-packages', sdk/'Lib/site-packages', dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', 'pip', 'pip-*.dist-info',
                                                     'PySide6*', 'pyside6*', 'shiboken6*'))
        shutil.copytree(self.root/'src/local_ai_appliance', sdk/'Lib/site-packages/local_ai_appliance',
                        dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
        self.worker = sdk/'contained_agent_worker.py'
        shutil.copy2(self.root/'scripts/contained_agent_worker.py', self.worker)
        self.executable = sdk/'python.exe'
        return sdk

    def start(self, progress=lambda message: None, *, load_model=None):
        with self._operation:
            try:
                progress('Reading AGENTS.md…')
                self.instructions = load_instructions(self.state if self.installation else self.root)
                if load_model is False or (load_model is None and self.model_manager is not None and self.model_manager.selected() is None):
                    # Host management remains available after removing the last model.
                    # Parsers retain their contained, zero-capability worker boundary.
                    sdk = self.stage()
                    self.container = AppContainer(evaluation=True)
                    self.container.allow_read(sdk, directory=True)
                    self.workspace = ContainedWorkspace(self.container, self.executable, self.evidence)
                    self.workspace.checkpoint = self.check_cancelled
                    return
                progress('Verifying the local model and runtime…')
                runtime, model = self.verify_assets()
                progress('Preparing contained document workers…')
                sdk = self.stage()
                self.check_cancelled()
                progress('Loading the selected local GPU model…')
                self.container = AppContainer(evaluation=True)
                for path, directory in ((runtime, True), (model, False), (sdk, True)):
                    self.container.allow_read(path, directory=directory)
                ipc_parent = self.state if self.installation else self.root/'artifacts'
                self.directory = ipc_parent/('i-'+secrets.token_hex(4))
                if len(str(self.directory/'s.sock').encode('utf-8')) >= 108:
                    raise RuntimeError('The private socket path is too long. Install into a shorter local path.')
                self.container.create_private_ipc(self.directory)
                self.endpoint, self.token = self.directory/'s.sock', secrets.token_urlsafe(32)
                key = self.directory/'token'
                key.write_text(self.token)
                command = server_command(runtime, model, self.endpoint, key,
                    self.model_profile.get('adapter', 'nemotron3') if self.model_profile else 'nemotron3')
                self.server = self.container.launch(command, cwd=runtime, memory_mib=32768)
                self.evidence['server_token'] = self.server.token_evidence
                self.drain = ServerDrain(self.server, gpu_layers=self.model_profile['gpu_layers'] if self.model_profile else 53)
                started = time.monotonic()
                while time.monotonic()-started < 120:
                    self.check_cancelled()
                    if self.drain.failed.is_set():
                        raise RuntimeError('The contained GPU model stopped during startup.')
                    connection = WindowsUnixConnection(self.endpoint, timeout=2)
                    try:
                        connection.request('GET', '/health', headers={'Authorization': 'Bearer '+self.token})
                        response = connection.getresponse()
                        if response.status == 200:
                            break
                    except OSError:
                        pass
                    finally:
                        connection.close()
                    self.cancelled.wait(.3)
                else:
                    raise RuntimeError('The local model did not become ready within two minutes.')
                if not self.drain.full_gpu:
                    raise RuntimeError('Full GPU placement could not be verified.')
                self.workspace = ContainedWorkspace(self.container, self.executable, self.evidence)
                self.workspace.checkpoint = self.check_cancelled
                if self.model_manager is not None and self.model_manager.vault.get('ocr-policy'):
                    from .ocr import OfflineOCR
                    self.workspace.ocr = OfflineOCR(self.state/'ocr',self.model_manager.policy)
                self.ready = True
                self.evidence['full_gpu'] = True
            except BaseException:
                self.close()
                raise

    def ask(self, prompt):
        with self._operation:
            if not self.ready or self.closed or self.drain is None or self.drain.failed.is_set():
                raise AccessDenied('No ready model. Use /model to install or switch models.')
            if getattr(self, 'model_manager', None) is not None:
                if self.model_manager.selected() != self.model_profile['id']:
                    raise AccessDenied('Selected model changed; restart the session before continuing')
                current = self.model_manager.authorize(self.model_profile['id'],
                    workload='code_evaluation' if getattr(self, 'code', None) is not None else 'documents')
                if (any(current[key] != self.model_profile[key] for key in
                        ('model', 'gpu_layers', 'runtime_lock_sha256', 'harness', 'interpreter'))
                        or current.get('adapter', 'nemotron3') != self.model_profile.get('adapter', 'nemotron3')):
                    raise AccessDenied('Model policy changed; restart the session before continuing')
            if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode()) > 16*1024:
                raise AccessDenied('Enter a request of at most 16 KiB.')
            self.cancelled.clear()
            code_workspace = getattr(self, 'code', None)
            if code_workspace is not None:
                code_workspace.exports.clear(); code_workspace.reviewed.clear()
            references = (MentionCatalog(self.workspace.broker).resolve(self.workspace.broker, prompt)
                          if parsed_mentions(prompt) else [])
            if len(json_bytes(references)) > 8192:
                raise AccessDenied('The folder/file references are too long. Use fewer references.')
            history, cached_sources, history_reset = self.conversation.prepare(self.workspace)
            if code_workspace is not None:
                code_workspace.check()
                retained={s.id:s for s in cached_sources}
                for source in code_workspace.sources.values():
                    previous=retained.get(source.id)
                    if previous is not None and (previous.folder_id,previous.path,previous.sha256)!=(source.folder_id,source.path,source.sha256):
                        raise AccessDenied('Staged source identity conflicts with retained context')
                    retained[source.id]=source
                cached_sources=tuple(retained.values())
            directory_result = list_directory_request(self.workspace, prompt, references=references)
            if directory_result is not None:
                self.check_cancelled()
                if not Conversation.verify_sources(self.workspace, cached_sources):
                    self.conversation.clear()
                    history_reset = True
                return self.remember(prompt, directory_result, (), history_reset)
            session = BrokerSession(self.workspace, sources=cached_sources, code=code_workspace)
            inventory = session.inventory()
            with self._guard:
                self.check_cancelled()
                process = self.container.launch([str(self.executable), '-I', '-B', str(self.worker)],
                                                cwd=self.executable.parent)
                self.active = process
            self.evidence['worker_tokens'].append(process.token_evidence)
            initial = {'endpoint': str(self.endpoint), 'token': self.token, 'prompt': prompt,
                       'permission_revision': session.revision, 'folders': DraftTools(self.workspace).list_folders(),
                       'folder_inventory': inventory}
            initial['folder_references'] = references
            initial['instructions'] = self.instructions
            initial['model_adapter'] = (self.model_profile.get('adapter', 'nemotron3')
                                        if self.model_profile else 'nemotron3')
            if code_workspace is not None:
                initial['code_enabled'] = True
            initial.update(history=history, history_sources=[asdict(s) for s in cached_sources])
            try:
                value, _ = process.exchange(initial, session.handle, timeout=300 if code_workspace is not None else 180)
                self.check_cancelled()
                if isinstance(value, dict) and set(value) == {'failure'}:
                    code = value['failure']
                    if not isinstance(code, str) or code not in MESSAGES:
                        raise AccessDenied('Worker returned an invalid failure code.')
                    # Recognized failures are fixed host text, never worker text.
                    raise AccessDenied(MESSAGES[code])
                if value.get('tracing_enabled') is not False:
                    raise AccessDenied('Worker tracing is not permitted.')
                citations = session.validate(value)
                dropped = value.get('history_dropped', 0)
                if type(dropped) is not int or not 0 <= dropped <= len(history)//2:
                    raise AccessDenied('Worker returned invalid conversation bounds.')
                proposals = tuple(p for p in self.workspace.pending_proposals() if p.id in value['proposal_ids'])
                # Unreturned proposals must not survive a worker request.
                for identifier in session.created-set(value['proposal_ids']):
                    self.workspace.discard(identifier)
                result = AgentResult(value['answer'], tuple(citations), proposals, value['model_calls'], value['tool_calls'],
                                     history_dropped=dropped)
                # Include new reads and sources actually referenced in this turn.
                draft_text = '\n'.join(p.text for p in proposals)
                remembered_sources = session.sources[session.initial_source_count:] + list(
                    DocumentAgent._citations(result.answer+'\n'+draft_text, session.sources))
                references = {(s.folder_id, s.path, s.sha256)
                              for p in proposals for s in (*p.dependencies,*((p.source,) if p.source else ()))}
                remembered_sources += [s for s in session.sources if (s.folder_id, s.path, s.sha256) in references]
                if not Conversation.verify_sources(self.workspace, session.sources):
                    self.conversation.clear()
                    raise AccessDenied('A source changed during the request. Chat cleared; ask again.')
                if self.workspace.broker.revision != session.revision:
                    self.conversation.clear()
                    raise AccessDenied('Folder permissions changed during the request')
                return self.remember(prompt, result, remembered_sources, history_reset)
            except BaseException as error:
                session.discard_all()
                if code_workspace is not None:
                    code_workspace.cancel()
                    wait=getattr(code_workspace.runner,'wait',None)
                    if wait is not None: wait()
                if self.cancelled.is_set():
                    raise Cancelled('Request cancelled') from None
                if isinstance(error, AccessDenied):
                    raise
                raise RuntimeError('The model request failed or exceeded its limits. Try a smaller, specific request.') from None
            finally:
                with self._guard:
                    self.active = None
                    process.close()

    def remember(self, prompt, result, sources, history_reset):
        with self._guard:
            self.check_cancelled()
            self.conversation.drop(result.history_dropped)
            answer = result.answer
            if result.proposals:
                answer += '\n\n'+'\n\n'.join('Draft: '+p.destination_path+' (not saved)\n'+p.text for p in result.proposals)
            trimmed = self.conversation.append(prompt, answer, sources, self.workspace.broker.revision)
            return replace(result, conversation=self.conversation.display(), history_reset=history_reset,
                           history_trimmed=trimmed or result.history_dropped > 0)

    def clear_chat(self):
        with self._operation, self._guard:
            self.conversation.clear()
            if getattr(self, 'code', None) is not None:
                self.code.exports.clear(); self.code.reviewed.clear()
            if self.workspace:
                for proposal in self.workspace.pending_proposals():
                    self.workspace.discard(proposal.id)

    def cancel(self):
        if self.workspace is not None and getattr(self.workspace,'ocr',None): self.workspace.ocr.cancel()
        self.cancelled.set()
        if getattr(self, 'code', None) is not None:
            self.code.cancel()
        with self._guard:
            self.conversation.clear()
            if getattr(self,'container',None) is not None:
                for process in tuple(getattr(self.container,'processes',())):
                    if not process.closed: process.kernel.TerminateJobObject(process.job,124)
            if self.active and not self.active.closed:
                self.active.kernel.TerminateJobObject(self.active.job, 124)
        # Model may still be generating. Restart is required after cancellation;
        # terminating the owned server ensures no outstanding generation survives.
        if self.server and not self.server.closed:
            self.server.kernel.TerminateJobObject(self.server.job, 124)
            self.ready = False

    def close(self):
        with self._operation:
            if self.closed:
                return
            self.conversation.clear()
            errors = []
            for action in ((self.code.close if getattr(self, 'code', None) else None),
                           (self.workspace.close if self.workspace else None),
                           (self.drain.stop if self.drain else None),
                           (self.container.close if self.container else None)):
                if action:
                    try:
                        action()
                    except Exception as error:
                        errors.append(error)
            if self.directory and self.directory.exists():
                ipc_parent = self.state if self.installation else self.root/'artifacts'
                if self.directory.parent.resolve() != ipc_parent.resolve() or self.directory.is_symlink():
                    errors.append(RuntimeError('Private IPC cleanup target was unsafe.'))
                else:
                    try:
                        shutil.rmtree(self.directory)
                    except OSError as error:
                        errors.append(error)
            self.ready, self.closed = False, True
            import msvcrt
            self._lockfile.seek(0)
            msvcrt.locking(self._lockfile.fileno(), msvcrt.LK_UNLCK, 1)
            self._lockfile.close()
            self.evidence['cleanup_complete'] = not errors
            if errors:
                raise RuntimeError('Evaluation cleanup was incomplete. Keep the interface closed and inspect the local setup.') from None

    def create_code(self,policy,*,acceptance=None,acceptance_sha256=None):
        with self._operation:
            if not self.ready or self.closed or not self.installation:
                raise AccessDenied('Code evaluation requires the ready standalone CPython 3.14 installation')
            if getattr(self, 'model_profile', None) is not None:
                self.model_manager.authorize(self.model_profile['id'],workload='code_evaluation')
            if self.code is not None:
                raise AccessDenied('Close the existing Code workspace before creating another')
            from .code_workspace import CodeWorkspace
            from .windows_code_runner import WindowsCodeRunner
            runner=WindowsCodeRunner(self.root,self.root.parent/'code',self.state/'code-runs',
                                     policy=policy,acceptance=acceptance,acceptance_sha256=acceptance_sha256)
            if not runner.available:
                runner.close()
                raise AccessDenied('Complete native boundary acceptance is required before a Code workspace can be enabled')
            self.clear_chat()
            self.code=CodeWorkspace(self.workspace,runner,policy=policy,configuration=runner.configuration|{
                                    'catalog_id':self.model_profile['id'] if self.model_profile else 'nemotron-4090-cp314-evaluation-1',
                                    'model_sha256':self.model_profile['model']['sha256'] if self.model_profile else None},
                                    checkpoint=self.check_cancelled)
            return self.code

    def close_code(self):
        with self._operation:
            if self.code is not None:
                self.code.close(); self.code=None; self.clear_chat()
