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


class Cancelled(Exception):
    pass


class ServerDrain:
    """Drain indefinitely without keeping prompts, documents or response logs.

Only two fixed GPU startup markers are retained as booleans. Close owns and
joins the readers before the process handles can be released.
"""
    def __init__(self, process):
        self.process, self.failed = process, threading.Event()
        self.full_gpu = False
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
                if b'offloaded 53/53 layers to GPU' in pending:
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
    def __init__(self, root):
        self.root = Path(root).resolve()
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

    def start(self, progress=lambda message: None):
        with self._operation:
            try:
                progress('Reading AGENTS.md…')
                self.instructions = load_instructions(self.state if self.installation else self.root)
                progress('Verifying the local model and runtime…')
                runtime, model = self.verify_assets()
                progress('Preparing contained document workers…')
                sdk = self.stage()
                self.check_cancelled()
                progress('Loading Nemotron on the RTX 4090…')
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
                command = [str(runtime/'llama-server.exe'), '--model', str(model), '--alias', 'contained-synthetic',
                    '--host', str(self.endpoint), '--ctx-size', '8192', '--predict', '2048', '--parallel', '1',
                    '--device', 'CUDA0', '--n-gpu-layers', '999', '--fit', 'off', '--flash-attn', 'on',
                    '--jinja', '--reasoning', 'on', '--reasoning-budget', '512', '--no-reasoning-preserve',
                    '--offline', '--no-ui', '--no-agent', '--no-ui-mcp-proxy', '--api-key-file', str(key),
                    '--no-context-shift', '--log-colors', 'off', '--log-verbosity', '4']
                self.server = self.container.launch(command, cwd=runtime, memory_mib=32768)
                self.evidence['server_token'] = self.server.token_evidence
                self.drain = ServerDrain(self.server)
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
                self.ready = True
                self.evidence['full_gpu'] = True
            except BaseException:
                self.close()
                raise

    def ask(self, prompt):
        with self._operation:
            if not self.ready or self.closed or self.drain.failed.is_set():
                raise RuntimeError('The local model is unavailable. Close and restart the interface.')
            if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode()) > 16*1024:
                raise AccessDenied('Enter a request of at most 16 KiB.')
            self.cancelled.clear()
            references = (MentionCatalog(self.workspace.broker).resolve(self.workspace.broker, prompt)
                          if parsed_mentions(prompt) else [])
            if len(json_bytes(references)) > 8192:
                raise AccessDenied('The folder/file references are too long. Use fewer references.')
            history, cached_sources, history_reset = self.conversation.prepare(self.workspace)
            directory_result = list_directory_request(self.workspace, prompt, references=references)
            if directory_result is not None:
                self.check_cancelled()
                if not Conversation.verify_sources(self.workspace, cached_sources):
                    self.conversation.clear()
                    history_reset = True
                return self.remember(prompt, directory_result, (), history_reset)
            session = BrokerSession(self.workspace, sources=cached_sources)
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
            initial.update(history=history, history_sources=[asdict(s) for s in cached_sources])
            try:
                value, _ = process.exchange(initial, session.handle, timeout=180)
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
                references = {(p.source.folder_id, p.source.path, p.source.sha256)
                              for p in proposals if p.source}
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
            if self.workspace:
                for proposal in self.workspace.pending_proposals():
                    self.workspace.discard(proposal.id)

    def cancel(self):
        self.cancelled.set()
        with self._guard:
            self.conversation.clear()
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
            for action in ((self.workspace.close if self.workspace else None),
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
