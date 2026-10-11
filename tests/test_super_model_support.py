"""Super policy, complete shard imports, and startup using inert fixtures only."""
import copy
import hashlib
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.model_management import (SUPER_ID, Hardware, ModelManager,
    builtin_profiles, execution_binding, model_download_assets, validate_model_policy)
from local_ai_appliance.project_store import LocalVault
from local_ai_appliance.windows_session import WindowsSession

ROOT = Path(__file__).resolve().parents[1]


class SuperPolicyTests(unittest.TestCase):
    def setUp(self):
        self.profile = next(p for p in builtin_profiles(ROOT) if p['id'] == SUPER_ID)

    def policy(self, profile):
        return {'format': 1, 'sequence': 1, 'expires': 2000, 'profiles': [profile],
                'blocked_publishers': [], 'blocked_jurisdictions': []}

    def test_floor_rejects_small_ram_gpu_pooling_and_non_windows_hosts(self):
        for ram, gpus, platform, arch, expected in [
                (131072, [98304], 'win32', 'amd64', True),
                (131072, [98176], 'win32', 'amd64', True),
                (131072, [98175], 'win32', 'amd64', False),
                (131071, [98304], 'win32', 'amd64', False),
                (65536, [98304], 'win32', 'amd64', False),
                (131072, [24576]*4, 'win32', 'amd64', False),
                (131072, [24576, 98304], 'win32', 'amd64', False),
                (131072, [], 'win32', 'amd64', False),
                (131072, [98304], 'darwin', 'arm64', False),
                (131072, [98304], 'win32', 'arm64', False),
                (None, [98304], 'win32', 'amd64', False)]:
            with self.subTest(ram=ram, gpus=gpus, platform=platform, arch=arch):
                hardware = Hardware(ram, 16, tuple({'name': 'inert GPU', 'vram_mib': v} for v in gpus), platform, arch)
                self.assertEqual(ModelManager.hardware_fit(self.profile, hardware), expected)

    def test_policy_cannot_lower_super_floors_or_change_backend_adapter(self):
        for field, value in [('minimum_ram_mib', 65536), ('minimum_vram_mib', 24576),
                             ('adapter', 'nemotron3'), ('execution_backend', 'cpu')]:
            profile = copy.deepcopy(self.profile); profile[field] = value
            with self.subTest(field=field), self.assertRaises(AccessDenied):
                validate_model_policy(self.policy(profile))

    def test_shards_have_immutable_urls_and_complete_weight_size(self):
        assets = model_download_assets(self.profile)
        self.assertEqual(len(assets), 3)
        self.assertEqual(sum(p['size'] for p in assets), 82541168480)
        self.assertEqual(self.profile['gpu_layers'], 89)
        for pin in assets:
            self.assertIn('/'+self.profile['source']['revision']+'/UD-Q4_K_M/', pin['url'])
            self.assertTrue(pin['url'].endswith(pin['name']))

    def test_incomplete_reordered_aliased_or_unbounded_shard_policies_are_denied(self):
        for mutation in ('missing', 'null', 'reordered', 'duplicate', 'path', 'hash', 'size', 'bool', 'subdirectory', 'first'):
            p = copy.deepcopy(self.profile)
            if mutation == 'missing': p.pop('model_shards')
            if mutation == 'null': p['model_shards'] = None
            if mutation == 'reordered': p['model_shards'].reverse()
            if mutation == 'duplicate': p['model_shards'][2] = p['model_shards'][1]
            if mutation == 'path': p['model_shards'][1]['name'] = '../bad.gguf'
            if mutation == 'hash': p['model_shards'][1]['sha256'] = []
            if mutation == 'size': p['model_shards'][1]['size'] = 513*1024**3
            if mutation == 'bool': p['model_shards'][1]['size'] = True
            if mutation == 'subdirectory': p['source']['subdirectory'] = '../bad'
            if mutation == 'first': p['model']['sha256'] = '0'*64
            with self.subTest(mutation=mutation), self.assertRaises(AccessDenied):
                validate_model_policy(self.policy(p))

    def test_shard_binding_changes_invalidate_coding_and_restart_binding(self):
        changed = copy.deepcopy(self.profile)
        changed['model_shards'][2]['sha256'] = '0'*64
        self.assertNotEqual(execution_binding(self.profile), execution_binding(changed))

    def test_preparation_selects_only_the_requested_pinned_set(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('super_asset_preparation', ROOT/'scripts/download_evaluation_assets.py')
        script = importlib.util.module_from_spec(spec); spec.loader.exec_module(script)
        self.assertEqual(script.selected_model_assets(ROOT, SUPER_ID), model_download_assets(self.profile))
        with self.assertRaises(RuntimeError): script.selected_model_assets(ROOT, 'unknown')


@unittest.skipUnless(os.name == 'posix', 'Portable inert shard fixtures')
class SuperImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        state = self.root/'state'; state.mkdir(mode=0o700)
        self.vault = LocalVault(state); self.addCleanup(self.vault.close)
        self.manager = ModelManager(self.root, self.vault)
        self.profile = next(p for p in builtin_profiles(ROOT) if p['id'] == SUPER_ID)
        self.profile.pop('source'); self.profile['workloads'] = ['documents']
        self.transfer = self.root/'transfer'; self.transfer.mkdir()
        self.bytes = {}
        for pin in self.profile['model_shards']:
            data = b'GGUF INERT '+pin['name'].encode(); self.bytes[pin['name']] = data
            pin.update(size=len(data), sha256=hashlib.sha256(data).hexdigest())
            (self.transfer/pin['name']).write_bytes(data)
        self.profile['model'] = copy.deepcopy(self.profile['model_shards'][0])
        validate_model_policy(SuperPolicyTests.policy(self, self.profile))
        self.manager.authorize = lambda *args, **kwargs: self.profile
        self.first = self.transfer/self.profile['model']['name']

    def test_complete_set_import_keeps_names_and_is_idempotent(self):
        path = self.manager.import_model(SUPER_ID, self.first)
        self.assertEqual(path.name, self.first.name)
        self.assertEqual({p.name for p in path.parent.iterdir()}, set(self.bytes))
        for asset, pin in self.manager.model_asset_paths(self.profile):
            self.assertEqual(asset.read_bytes(), self.bytes[pin['name']])
        self.assertEqual(self.manager.import_model(SUPER_ID, self.first), path)
        self.assertEqual(self.manager.verify_model(self.profile), path)

    def test_any_missing_changed_or_linked_sibling_blocks_import(self):
        sibling = self.transfer/self.profile['model_shards'][1]['name']
        original = sibling.read_bytes()
        for mutation in ('missing', 'changed', 'symlink'):
            sibling.unlink(missing_ok=True)
            if mutation == 'changed': sibling.write_bytes(b'x'*len(original))
            if mutation == 'symlink': sibling.symlink_to(self.first)
            with self.subTest(mutation=mutation), self.assertRaises((RuntimeError, AccessDenied, FileNotFoundError)):
                self.manager.import_model(SUPER_ID, self.first)
            self.assertFalse(self.manager.model_cache.exists())
        sibling.unlink(); sibling.write_bytes(original)

    def test_import_requires_first_shard_exact_name(self):
        second = self.transfer/self.profile['model_shards'][1]['name']
        with self.assertRaises(AccessDenied): self.manager.import_model(SUPER_ID, second)

    def test_import_failure_removes_only_staging_and_never_publishes_partial_set(self):
        real = self.manager._verify_model_file
        def reject_copy(path, pin, *args):
            if '.model-set-' in str(path) and pin == self.profile['model_shards'][2]:
                raise AccessDenied('Inert copy failure')
            return real(path, pin, *args)
        with patch.object(self.manager, '_verify_model_file', side_effect=reject_copy):
            with self.assertRaises(AccessDenied): self.manager.import_model(SUPER_ID, self.first)
        self.assertEqual(list(self.manager.model_cache.iterdir()), [])
        self.assertEqual({p.name for p in self.transfer.iterdir()}, set(self.bytes))

    def test_launch_checks_every_shard_and_existing_corruption_is_not_repaired(self):
        path = self.manager.import_model(SUPER_ID, self.first)
        last = path.parent/self.profile['model_shards'][2]['name']
        last.write_bytes(b'x'*len(last.read_bytes()))
        with self.assertRaises(AccessDenied): self.manager.verify_model(self.profile)
        with self.assertRaises(AccessDenied): self.manager.import_model(SUPER_ID, self.first)
        self.assertTrue(last.read_bytes().startswith(b'x'))

    def test_non_gguf_shard_is_denied_even_with_matching_hash(self):
        pin = self.profile['model_shards'][2]; data = b'NOTG inert'
        pin.update(size=len(data), sha256=hashlib.sha256(data).hexdigest())
        (self.transfer/pin['name']).write_bytes(data)
        with self.assertRaises(AccessDenied): self.manager.import_model(SUPER_ID, self.first)

    def test_verification_honors_cancellation(self):
        self.manager.import_model(SUPER_ID, self.first)
        def cancel(): raise InterruptedError('Cancelled')
        with self.assertRaises(InterruptedError): self.manager.verify_model(self.profile, cancel)


class SuperStartupTests(unittest.TestCase):
    def test_managed_start_pins_and_grants_each_shard_and_requires_full_gpu(self):
        for full_gpu in (True, False):
            with self.subTest(full_gpu=full_gpu), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                session = object.__new__(WindowsSession)
                session.root = session.state = root
                session.installation = {'synthetic': True}
                session.model_profile = next(p for p in builtin_profiles(ROOT) if p['id'] == SUPER_ID)
                assets = [(root/pin['name'], pin) for pin in session.model_profile['model_shards']]
                manager = Mock(); manager.model_asset_paths.return_value = assets
                manager.policy.vault.get.return_value = None; session.model_manager = manager
                security = Mock(); security.release = root/'managed'; session.security = security
                session._operation = threading.RLock(); session.cancelled = threading.Event()
                session.check_cancelled = lambda: None
                session.verify_assets = lambda: (root/'runtime', assets[0][0])
                session.stage = lambda: root/'sdk'; session.executable = root/'python.exe'
                session.evidence = {}; session.close = Mock()
                container = Mock(); container.create_private_ipc.side_effect = lambda p: p.mkdir()
                container.launch.return_value.token_evidence = {'appcontainer': True, 'capability_count': 0}
                connection = Mock(); connection.getresponse.return_value.status = 200
                with patch('local_ai_appliance.windows_session.load_instructions', return_value='synthetic'), \
                     patch('local_ai_appliance.windows_code_runner.RunnerContainer', return_value=container), \
                     patch('local_ai_appliance.windows_session.ServerDrain') as drain, \
                     patch('local_ai_appliance.windows_session.WindowsUnixConnection', return_value=connection), \
                     patch('local_ai_appliance.windows_session.ContainedWorkspace'), \
                     patch('local_ai_appliance.data_security.SecurityBroker'):
                    drain.return_value.failed.is_set.return_value = False
                    drain.return_value.full_gpu = full_gpu
                    if full_gpu:
                        session.start()
                        self.assertTrue(session.ready)
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'Full GPU placement'): session.start()
                        session.close.assert_called_once()
                self.assertEqual(security.pin_model.call_args_list,
                                 [unittest.mock.call(path, pin['sha256']) for path, pin in assets])
                granted = {call.args[0] for call in container.allow_read.call_args_list}
                self.assertTrue({path for path, _ in assets} <= granted)
                self.assertEqual(drain.call_args.kwargs['gpu_layers'], 89)
                command = container.launch.call_args.args[0]
                self.assertEqual(command[command.index('--model')+1], str(assets[0][0]))
                self.assertEqual(command[command.index('--device')+1], 'CUDA0')
                self.assertIn('--offline', command)


if __name__ == '__main__': unittest.main()
