"""CPU policy/runtime/startup fixtures; no native execution or model quality claims."""
import copy
import hashlib
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import zipfile

from local_ai_appliance.asset_integrity import cpu_runtime_pins, CPU_RUNTIME_DIRECTORY, CPU_RUNTIME_PATH
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.model import AgentError
from local_ai_appliance.model_adapters import server_command, execution_limits
from local_ai_appliance.model_management import CPU_IDS, Hardware, ModelManager, builtin_profiles, validate_model_policy
from local_ai_appliance.runtime_preparation import prepare_cpu_runtime
from local_ai_appliance.windows_session import WindowsSession
from local_ai_appliance.windows_container import ContainedProcess

ROOT = Path(__file__).resolve().parents[1]


class CPUProfileTests(unittest.TestCase):
    def setUp(self):
        self.profiles = [p for p in builtin_profiles(ROOT) if p['id'] in CPU_IDS]

    def policy(self, profile):
        return {'format':1, 'sequence':1, 'expires':2000, 'profiles':[profile],
                'blocked_publishers':[], 'blocked_jurisdictions':[]}

    def test_cpu_profiles_need_no_gpu_but_require_known_windows_x64_and_capacity(self):
        self.assertEqual(len(self.profiles), 2)
        for profile in self.profiles:
            self.assertEqual(profile['minimum_vram_mib'], 0)
            good = Hardware(16384, 4, (), 'win32', 'amd64')
            self.assertTrue(ModelManager.hardware_fit(profile, good))
            self.assertTrue(ModelManager.hardware_fit(profile, Hardware(15872, 4, (), 'win32', 'x86_64')))
            for hardware in (Hardware(8192, 8, (), 'win32', 'amd64'),
                             Hardware(15871, 8, (), 'win32', 'amd64'),
                             Hardware(None, 8, (), 'win32', 'amd64'),
                             Hardware(32768, None, (), 'win32', 'amd64'),
                             Hardware(32768, 2, (), 'win32', 'amd64'),
                             Hardware(32768, 8, (), 'win32', 'arm64'),
                             Hardware(32768, 8, (), 'win32'),
                             Hardware(32768, 8, (), 'darwin', 'x86_64')):
                self.assertFalse(ModelManager.hardware_fit(profile, hardware))
        gpu = next(p for p in builtin_profiles(ROOT) if p['id'] not in CPU_IDS)
        self.assertFalse(ModelManager.hardware_fit(gpu, Hardware(65536, 8, (), 'win32', 'amd64')))

    def test_cpu_binding_cannot_mix_cuda_runtime_layers_or_unbounded_threads(self):
        for profile in self.profiles:
            validate_model_policy(self.policy(profile))
            for key, value in [('execution_backend','cuda'), ('execution_backend','auto'),
                               ('cpu_threads',True), ('cpu_threads',16), ('gpu_layers',1),
                               ('minimum_vram_mib',1024), ('runtime_lock_sha256','0'*64),
                               ('adapter','nemotron3'), ('id','unreviewed-cpu')]:
                changed = copy.deepcopy(profile); changed[key] = value
                with self.subTest(model=profile['id'], field=key), self.assertRaises(AccessDenied):
                    validate_model_policy(self.policy(changed))

    def test_cpu_command_uses_fixed_threads_no_gpu_and_private_offline_endpoint(self):
        command = server_command('/cpu-runtime', '/local.gguf', '/private/s.sock', '/private/key',
                                 'gemma4', execution_backend='cpu', cpu_threads=4)
        for flag, expected in [('--device','none'), ('--n-gpu-layers','0'), ('--flash-attn','off'),
                               ('--threads','4'), ('--threads-batch','4'), ('--ctx-size','8192'),
                               ('--parallel','1'), ('--host','/private/s.sock'), ('--fit','off')]:
            self.assertEqual(command[command.index(flag)+1], expected)
        for flag in ('--offline','--no-ui','--no-agent','--no-ui-mcp-proxy','--no-kv-offload'):
            self.assertIn(flag, command)
        for backend, threads in [('auto',4), ('cpu',None), ('cpu',True), ('cpu',128), ('cuda',4)]:
            with self.assertRaises(AgentError):
                server_command('/r','/m','/s','/k', execution_backend=backend, cpu_threads=threads)

    def test_cpu_requests_have_bounded_time_for_slower_generation(self):
        cpu, cuda = execution_limits('cpu'), execution_limits('cuda')
        self.assertEqual(cuda.request_seconds, 60)
        self.assertEqual((cuda.document_seconds, cuda.code_seconds), (180, 300))
        self.assertEqual(cpu.request_seconds, 300)  # Existing transport maximum.
        self.assertGreater(cpu.document_seconds, cpu.request_seconds)
        self.assertGreater(cpu.code_seconds, cpu.document_seconds)
        self.assertLessEqual(cpu.code_seconds, 1200)
        for invalid in ('remote', 'auto', None, []):
            with self.assertRaises(AgentError): execution_limits(invalid)
        # Invalid bounds fail before acquiring any native process/pipe handles.
        process = object.__new__(ContainedProcess)
        with self.assertRaises(OSError): process.exchange({}, lambda _:None, timeout=301)
        with self.assertRaises(OSError):
            process.exchange({}, lambda _:None, timeout=1201, inference_backend='cpu')
        with self.assertRaises(AgentError):
            process.exchange({}, lambda _:None, inference_backend='automatic')

    def test_cpu_lock_drift_is_rejected_and_inventory_excludes_gpu_backends(self):
        pins = cpu_runtime_pins(ROOT)
        names = {p['path'] for p in pins['extracted_runtime']}
        self.assertIn('llama-server.exe', names)
        self.assertFalse(any('cuda' in n or 'vulkan' in n or 'metal' in n for n in names))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); (root/'profiles').mkdir()
            (root/CPU_RUNTIME_PATH).write_bytes((ROOT/CPU_RUNTIME_PATH).read_bytes()+b' ')
            with self.assertRaisesRegex(RuntimeError, 'lock has changed'):
                cpu_runtime_pins(root)

    def test_launch_verifies_only_the_explicit_cpu_runtime_without_cuda_fallback(self):
        manager = object.__new__(ModelManager); manager.root = ROOT
        profile = self.profiles[0]
        manager.selected = lambda: profile['id']
        manager.authorize = lambda *args, **kwargs: profile
        manager.verify_model = lambda p, cancel=lambda: None: Path('/inert.gguf')
        with patch('local_ai_appliance.model_management.inference_pins', side_effect=AssertionError('CUDA fallback')), \
             patch('local_ai_appliance.model_management.verify_tree') as verify:
            runtime, model, selected = manager.launch_assets()
            self.assertEqual(runtime, ROOT/CPU_RUNTIME_DIRECTORY)
            self.assertEqual(selected, profile)
            self.assertEqual(verify.call_args.args[0], runtime)
        with patch('local_ai_appliance.model_management.verify_tree', side_effect=FileNotFoundError), \
             patch('local_ai_appliance.model_management.inference_pins', side_effect=AssertionError('CUDA fallback')):
            with self.assertRaises(FileNotFoundError): manager.launch_assets()

    def test_cpu_startup_keeps_containment_and_does_not_claim_full_gpu(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            session = object.__new__(WindowsSession)
            session.root = session.state = root
            session.installation = {'synthetic':True}
            session.model_profile = self.profiles[0]
            session.model_manager = None
            session._operation = threading.RLock()
            session.cancelled = threading.Event()
            session.check_cancelled = lambda: None
            session.verify_assets = lambda: (root/'runtime', root/'inert.gguf')
            session.stage = lambda: root/'sdk'
            session.executable = root/'python.exe'
            session.evidence = {}
            session.close = Mock()
            container = Mock()
            container.create_private_ipc.side_effect = lambda p: p.mkdir()
            container.launch.return_value.token_evidence = {'appcontainer':True, 'capability_count':0}
            connection = Mock(); connection.getresponse.return_value.status = 200
            with patch('local_ai_appliance.windows_session.load_instructions', return_value='synthetic'), \
                 patch('local_ai_appliance.windows_session.AppContainer', return_value=container) as factory, \
                 patch('local_ai_appliance.windows_session.ServerDrain') as drain, \
                 patch('local_ai_appliance.windows_session.WindowsUnixConnection', return_value=connection), \
                 patch('local_ai_appliance.windows_session.ContainedWorkspace'):
                drain.return_value.failed.is_set.return_value = False
                drain.return_value.full_gpu = False
                session.start()
            factory.assert_called_once_with(evaluation=True)
            self.assertTrue(session.ready)
            self.assertFalse(session.evidence['full_gpu'])
            self.assertEqual(session.evidence['inference_backend'], 'cpu')
            self.assertTrue(session.evidence['placement_verified'])
            self.assertEqual(container.launch.call_args.kwargs['memory_mib'], 8192)
            self.assertEqual(drain.call_args.kwargs['gpu_layers'], 0)
            self.assertIn('--offline', container.launch.call_args.args[0])
            session.close.assert_not_called()

    def test_changed_cpu_hardware_policy_requires_restart_before_model_use(self):
        session = object.__new__(WindowsSession)
        session._operation = threading.RLock()
        session.ready, session.closed = True, False
        session.drain = Mock()
        session.drain.failed.is_set.return_value = False
        session.model_profile = self.profiles[0]
        manager = Mock(); session.model_manager = manager
        manager.selected.return_value = session.model_profile['id']
        changed = copy.deepcopy(session.model_profile); changed['minimum_ram_mib'] += 1024
        manager.authorize.return_value = changed
        with self.assertRaisesRegex(AccessDenied, 'restart'): session.ask('Synthetic question')


class OfflineCPURuntimeTests(unittest.TestCase):
    def test_verified_offline_staging_reuse_drift_and_installed_immutability(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            payload = b'Inert CPU fixture; never execute'
            archive = root/'cpu.zip'
            with zipfile.ZipFile(archive, 'w') as stream: stream.writestr('llama-server.exe', payload)
            pins = {'assets':[{'name':'cpu.zip','size':archive.stat().st_size,
                               'url':'https://example.invalid/cpu.zip',
                               'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}],
                    'extracted_runtime':[{'path':'llama-server.exe','size':len(payload),
                                          'sha256':hashlib.sha256(payload).hexdigest()}]}
            with patch('local_ai_appliance.runtime_preparation.cpu_runtime_pins', return_value=pins), \
                 patch('local_ai_appliance.runtime_preparation.installed_config', return_value=None):
                bad = root/'bad.zip'; bad.write_bytes(b'wrong')
                with self.assertRaises(RuntimeError): prepare_cpu_runtime(root, bad)
                self.assertFalse((root/CPU_RUNTIME_DIRECTORY).exists())
                path = prepare_cpu_runtime(root, archive)
                self.assertEqual((path/'llama-server.exe').read_bytes(), payload)
                self.assertEqual(prepare_cpu_runtime(root, archive), path)
                (path/'llama-server.exe').write_bytes(b'changed')
                with self.assertRaises(RuntimeError): prepare_cpu_runtime(root, archive)
                self.assertEqual((path/'llama-server.exe').read_bytes(), b'changed')
            with patch('local_ai_appliance.runtime_preparation.installed_config', return_value={}):
                with self.assertRaisesRegex(RuntimeError, 'immutable'): prepare_cpu_runtime(root, archive)
