"""Pinned synthetic weights and inert process replacements; no GPU/network needed."""
import io
import hashlib
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from local_ai_appliance.agent import AgentResult
from local_ai_appliance.backend import SessionCancelled, WindowsSessionAdapter
from local_ai_appliance.contracts import Project, WorkspaceKind
from local_ai_appliance.conversation import Conversation
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.project_store import ProjectSession, ProjectStore
from local_ai_appliance.terminal_client import TerminalClient
from local_ai_appliance.terminal_ui import TerminalView
from local_ai_appliance.workspace import Workspace
import test_model_management as model_fixtures


class InertService:
    starts = []
    failures = set()

    def __init__(self, root, *, model_manager):
        self.root, self.model_manager = root, model_manager
        self.instructions = 'Base instructions'
        self.workspace = Workspace()
        self.conversation = Conversation()
        self.closed = self.ready = False
        self.code = None
        self.questions = []
        self.cancelled = False

    def start(self, progress=lambda text: None):
        selected = self.model_manager.selected()
        self.starts.append(selected)
        if selected in self.failures: raise RuntimeError('Synthetic GPU startup failure')
        if selected is not None:
            self.model_manager.verify_model(self.model_manager.authorize(selected))
        self.ready = selected is not None

    def ask(self, prompt):
        if not self.ready: raise AccessDenied('No ready model')
        self.questions.append(prompt)
        return AgentResult('Inert response', (), (), 1, 0)

    def clear_chat(self): self.conversation.clear()
    def cancel(self): self.cancelled = True
    def close(self):
        self.closed = True; self.ready = False
        self.workspace.close(); self.conversation.clear()


@unittest.skipUnless(os.name == 'posix', 'Portable inert host fixture')
class ModelMenuTests(unittest.TestCase):
    update = model_fixtures.ModelManagementTests.update

    def setUp(self):
        model_fixtures.ModelManagementTests.setUp(self)
        self.other_data = b'GGUF second inert model'
        self.other = json.loads(json.dumps(self.profile))
        self.other['id'] = 'second-model'
        self.other['model'] = {'name': 'second.gguf', 'size': len(self.other_data),
                               'sha256': hashlib.sha256(self.other_data).hexdigest()}
        for profile in (self.profile, self.other):
            profile['source'] = {'upstream': 'fixture/model', 'upstream_revision': 'a'*40,
                'repository': 'fixture/model', 'revision': 'a'*40,
                'url': 'https://huggingface.co/fixture/model/resolve/'+'a'*40+'/'+profile['model']['name'],
                'hash_origin': 'publisher-lfs-metadata', 'metadata_checked': '2026-10-10'}
        self.policy['profiles'] = [self.profile, self.other]
        self.update()
        self.manager.import_model('synthetic-model', self.source)
        self.manager.select('synthetic-model')
        InertService.starts = []; InertService.failures = set()
        self.service = InertService(self.root, model_manager=self.manager)
        self.adapter = WindowsSessionAdapter(Project('fixture', 'Fixture'), self.service)
        self.adapter.start()
        self.session = ProjectSession(self.adapter, ProjectStore(self.vault))
        self.addCleanup(self.session.close)
        self.output = io.StringIO()
        self.client = TerminalClient(self.session, view=TerminalView(self.output, plain=True))

    def install_second(self):
        path = self.root/'second.gguf'; path.write_bytes(self.other_data)
        self.manager.import_model('second-model', path)

    def response(self, data):
        response = io.BytesIO(data)
        response.url = self.other['source']['url']; response.status = 200
        return response

    def test_hardware_recommendation_is_host_only_and_preserves_menu_and_selection(self):
        from local_ai_appliance.model_management import Hardware
        from local_ai_appliance.terminal_completion import COMMANDS
        hw=Hardware(32768,8,({'name':'Inert GPU','vram_mib':24576},),'win32','amd64')
        self.client.handle('/model')
        pending=self.client.model_menu.pending
        before=self.vault.get('selected-model')
        starts=list(InertService.starts)
        with patch('local_ai_appliance.model_menu.scan_hardware',return_value=hw), \
             patch.object(self.manager,'install',side_effect=AssertionError('Unexpected download')):
            self.client.handle('/model recommend')
        self.assertEqual(self.client.model_menu.pending,pending)
        self.assertEqual(self.vault.get('selected-model'),before)
        self.assertEqual(InertService.starts,starts)
        self.assertFalse(self.service.questions)
        self.assertIn('Recommended for this hardware',self.output.getvalue())
        self.assertIn('/model recommend',COMMANDS)

    def test_no_fit_recommendation_keeps_explicit_no_model_and_explains_reason(self):
        from local_ai_appliance.model_management import Hardware
        self.session.switch_model(None)
        starts=list(InertService.starts)
        with patch('local_ai_appliance.model_management.scan_hardware',
                   return_value=Hardware(None,8,(),'win32','amd64')):
            self.client.handle('/hardware')
        self.assertIsNone(self.manager.selected())
        self.assertEqual(InertService.starts,starts)
        self.assertIn('System RAM is unknown',self.output.getvalue())
        self.assertIn('No permitted model fits',self.output.getvalue())

    def test_menu_switch_preserves_verified_grants_and_project_instructions(self):
        self.install_second()
        folder = self.root/'documents'; folder.mkdir()
        self.session.grant(folder, WorkspaceKind.REFERENCE)
        self.session.create_project('Model test')
        self.session.set_instructions('Remember the units')
        self.session.conversation.append('old prompt', 'old answer', (), self.session.workspace.broker.revision)
        self.client.sources['old'] = object()
        for line in ('/model', '1', '2'): self.client.handle(line)
        self.assertEqual(self.manager.selected(), 'second-model')
        self.assertTrue(self.adapter.service.ready)
        self.assertTrue(self.service.closed)
        self.assertEqual(self.session.conversation.display(), ())
        self.assertEqual(len(self.session.workspace.broker.folders()), 1)
        self.assertIn('Remember the units', self.adapter.service.instructions)
        self.assertEqual(self.session.record['configuration_id'], 'second-model')
        self.assertFalse(self.client.sources)
        self.assertFalse(self.adapter.service.questions)

    def test_install_menu_contains_only_missing_model_and_download_does_not_select(self):
        self.client.handle('/model install')
        self.assertEqual(self.client.model_menu.pending, ('install', ('second-model',)))
        with patch('urllib.request.build_opener') as build:
            build.return_value.open.return_value = self.response(self.other_data)
            self.client.handle('1')
            self.assertEqual(build.call_args.args[0].proxies, {})
            self.assertEqual(build.return_value.open.call_args.args[0].full_url, self.other['source']['url'])
        self.assertEqual(self.manager.selected(), 'synthetic-model')
        self.assertEqual(self.manager.verify_model(self.other).read_bytes(), self.other_data)
        self.assertFalse(self.client.model_menu.pending)

    def test_remove_requires_yes_and_active_last_model_leaves_management_available(self):
        self.client.handle('/model remove'); self.client.handle('1')
        self.assertTrue(self.manager.installed(self.profile))
        self.client.handle('no')
        self.assertEqual(self.manager.selected(), 'synthetic-model')
        self.client.handle('/model remove synthetic-model'); self.client.handle('yes')
        self.assertFalse(self.manager.installed(self.profile))
        self.assertIsNone(self.manager.selected())
        self.assertFalse(self.adapter.service.ready)
        self.client.handle('/model install')
        self.assertEqual(len(self.client.model_menu.pending[1]), 2)
        with self.assertRaises(AccessDenied): self.client.ask('No model loaded')

    def test_sharded_removal_confirms_complete_managed_set(self):
        self.other['model']['name'] = 'second-00001-of-00002.gguf'
        self.other['model_shards'] = [dict(self.other['model']),
            dict(self.other['model'], name='second-00002-of-00002.gguf')]
        self.other['source']['url'] = self.other['source']['url'].rsplit('/', 1)[0]+'/'+self.other['model']['name']
        self.policy['sequence'] += 1
        self.update()
        for pin in self.other['model_shards']:
            (self.root/pin['name']).write_bytes(self.other_data)
        self.manager.import_model('second-model', self.root/self.other['model']['name'])
        directory = self.manager.managed_model_path(self.other).parent
        self.client.handle('/model remove second-model')
        self.assertEqual(self.client.model_menu.pending, ('confirm', ('second-model',)))
        self.client.handle('yes')
        self.assertFalse(directory.exists())
        self.assertTrue(self.service.ready)

    def test_active_removal_uses_reopened_policy_manager_after_unload(self):
        from local_ai_appliance.model_management import ModelManager
        original = self.session.switch_model
        def unload(identifier):
            original(identifier)
            self.adapter.service.model_manager = ModelManager(self.root, self.vault,
                clock=lambda: self.now[0], model_cache=self.manager.model_cache)
        with patch.object(self.session, 'switch_model', side_effect=unload), \
             patch.object(self.manager, 'remove', side_effect=AccessDenied('Closed policy store')) as stale:
            self.client.handle('/model remove synthetic-model')
            self.client.handle('yes')
            stale.assert_not_called()
        self.assertFalse(self.manager.installed(self.profile))

    def test_install_menu_displays_total_shard_storage(self):
        self.other['model']['name'] = 'second-00001-of-00002.gguf'
        self.other['model']['size'] = 2*1024**3
        self.other['model_shards'] = [dict(self.other['model']),
            dict(self.other['model'], name='second-00002-of-00002.gguf', size=4*1024**3)]
        self.other['source']['url'] = self.other['source']['url'].rsplit('/', 1)[0]+'/'+self.other['model']['name']
        self.policy['sequence'] += 1
        self.update()
        self.client.handle('/model install')
        self.assertIn('6.0 GiB', self.output.getvalue())

    def test_invalid_menu_input_and_cancel_never_reach_inference(self):
        self.client.handle('/model')
        for line in ('0', '4', 'hello', '/shell anything'):
            with self.assertRaises(AccessDenied): self.client.handle(line)
        self.client.handle('switch'); self.client.handle('/back'); self.client.handle('/cancel')
        self.assertIsNone(self.client.model_menu.pending)
        self.assertFalse(self.service.questions)

    def test_scrollback_keyboard_cancel_closes_menu_and_keeps_session_open(self):
        responses = iter(('/model', KeyboardInterrupt(), '/quit'))
        def read(prompt):
            value = next(responses)
            if isinstance(value, BaseException): raise value
            return value
        self.client.read = read
        self.client.interact()
        self.assertIsNone(self.client.model_menu.pending)
        self.assertFalse(self.service.closed); self.assertFalse(self.service.cancelled)

    def test_failed_switch_restores_previous_model_and_verified_grants(self):
        self.install_second(); InertService.failures.add('second-model')
        folder = self.root/'documents'; folder.mkdir()
        self.session.grant(folder, WorkspaceKind.REFERENCE)
        with self.assertRaisesRegex(AccessDenied, 'previous model was restored'):
            self.client.handle('/model switch second-model')
        self.assertEqual(self.manager.selected(), 'synthetic-model')
        self.assertTrue(self.adapter.service.ready)
        self.assertEqual(len(self.session.workspace.broker.folders()), 1)
        self.client.handle('Still usable')
        self.assertEqual(self.adapter.service.questions, ['Still usable'])

    def test_corrupt_switch_denied_before_stopping_current_model_and_corrupt_model_removable(self):
        self.install_second(); self.manager.model_path(self.other).write_bytes(b'bad')
        with self.assertRaises((AccessDenied, RuntimeError)): self.client.handle('/model switch second-model')
        self.assertFalse(self.service.closed)
        self.client.handle('/model remove second-model'); self.client.handle('yes')
        self.assertFalse(self.manager.installed(self.other))
        self.assertTrue(self.service.ready)

    def test_download_bad_hash_oversize_tls_and_cancel_publish_nothing(self):
        destination = self.manager.model_cache/(self.other['model']['sha256']+'.gguf')
        for data, url in ((b'x'*len(self.other_data), 'https://example.invalid/model'),
                          (self.other_data+b'overflow', 'https://example.invalid/model'),
                          (self.other_data, 'http://example.invalid/model')):
            response = self.response(data); response.url = url
            with patch('urllib.request.build_opener') as build:
                build.return_value.open.return_value = response
                with self.assertRaises(AccessDenied): self.manager.install('second-model')
            self.assertFalse(destination.exists())
            self.assertFalse(list(self.manager.model_cache.glob('.model-*')))
        self.client.model_menu.cancelled.set()
        with self.assertRaises(SessionCancelled):
            self.manager.install('second-model', cancel=self.client.model_menu.checkpoint)
        self.assertFalse(destination.exists())
        self.assertFalse(list(self.manager.model_cache.glob('.model-*')))

    def test_download_cancellation_does_not_cancel_active_inference_host(self):
        entered, release = threading.Event(), threading.Event()
        menu = self.client.model_menu
        def read(size):
            entered.set(); release.wait(3)
            return self.other_data
        response = self.response(self.other_data); response.read1 = read
        errors = []
        def install():
            try: self.client.handle('/model install second-model')
            except Exception as error: errors.append(error)
        with patch('urllib.request.build_opener') as build:
            build.return_value.open.return_value = response
            task = threading.Thread(target=install); task.start()
            try:
                self.assertTrue(entered.wait(2)); menu.cancel(); release.set()
            finally: release.set(); task.join(3)
        self.assertFalse(task.is_alive())
        self.assertIsInstance(errors[0], SessionCancelled)
        self.assertFalse(self.service.cancelled)
        self.assertFalse(self.manager.installed(self.other))

    def test_cancel_during_final_verification_removes_only_our_published_file(self):
        original = self.manager.verify_model
        def cancel_after_publication(profile, checkpoint=lambda: None):
            if profile['id'] == 'second-model':
                self.assertTrue(self.manager.model_path(profile).exists())
                raise SessionCancelled('Synthetic cancellation after atomic publication')
            return original(profile, checkpoint)
        with patch('urllib.request.build_opener') as build, \
             patch.object(self.manager, 'verify_model', side_effect=cancel_after_publication):
            build.return_value.open.return_value = self.response(self.other_data)
            with self.assertRaises(SessionCancelled): self.manager.install('second-model')
        self.assertFalse(self.manager.installed(self.other))
        self.assertTrue(self.manager.installed(self.profile))
        self.assertFalse(list(self.manager.model_cache.glob('.model-*')))

    def test_legacy_payload_model_cannot_be_deleted(self):
        managed = self.manager.model_path(self.profile)
        legacy = self.root/'artifacts/inference/downloads'/self.profile['model']['name']
        legacy.parent.mkdir(parents=True); managed.rename(legacy)
        with self.assertRaisesRegex(AccessDenied, 'verified payload'):
            self.client.handle('/model remove synthetic-model')
        self.assertTrue(legacy.exists())

    def test_changed_folder_identity_is_not_restored(self):
        self.install_second()
        folder = self.root/'documents'; folder.mkdir()
        self.session.grant(folder, WorkspaceKind.REFERENCE)
        folder.rename(self.root/'original-documents'); folder.mkdir()
        self.client.handle('/model switch second-model')
        self.assertFalse(self.session.workspace.broker.folders())

    def test_cancel_during_switch_verification_keeps_current_model_running(self):
        self.install_second()
        verify = self.manager.verify_model
        def cancel_then_verify(profile, checkpoint=lambda: None):
            self.client.model_menu.cancel()
            return verify(profile, checkpoint)
        with patch.object(self.manager, 'verify_model', side_effect=cancel_then_verify):
            with self.assertRaises(SessionCancelled): self.client.handle('/model switch second-model')
        self.assertFalse(self.service.closed); self.assertFalse(self.service.cancelled)
        self.assertFalse(self.adapter._busy)
        self.assertEqual(self.manager.selected(), 'synthetic-model')

    def test_download_policy_revoked_before_publication_is_denied(self):
        policy = json.loads(json.dumps(self.policy)); policy['sequence'] += 1
        policy['profiles'][1]['status'] = 'revoked'
        with patch('urllib.request.build_opener') as build:
            build.return_value.open.return_value = self.response(self.other_data)
            with self.assertRaises(AccessDenied):
                self.manager.install('second-model', progress=lambda _: self.update(policy))
        self.assertFalse(self.manager.installed(self.other))
        self.assertFalse(list(self.manager.model_cache.glob('.model-*')))

    def test_management_only_windows_start_does_not_launch_inference(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from local_ai_appliance.windows_session import WindowsSession
        service = WindowsSession.__new__(WindowsSession)
        service._operation = threading.RLock()
        service.installation = True; service.state = self.root/'state'
        service.model_manager = SimpleNamespace(selected=lambda: None)
        service.security = None
        service.ready = service.closed = False; service.drain = None
        service.evidence = {}; service.executable = self.root/'worker/python.exe'
        service.check_cancelled = lambda: None
        service.stage = Mock(return_value=service.executable.parent)
        with patch('local_ai_appliance.windows_session.load_instructions', return_value='Host preferences'), \
             patch('local_ai_appliance.windows_code_runner.RunnerContainer') as container, \
             patch('local_ai_appliance.windows_session.ContainedWorkspace') as workspace:
            service.start()
            container.return_value.launch.assert_not_called()
            container.return_value.allow_read.assert_called_once_with(service.executable.parent, directory=True)
            self.assertIs(service.workspace, workspace.return_value)
            self.assertFalse(service.ready)
            with self.assertRaisesRegex(AccessDenied, 'No ready model'): service.ask('Must not infer')

    def test_revoked_model_is_removable_but_cannot_switch_or_download(self):
        self.install_second()
        policy = json.loads(json.dumps(self.policy)); policy['sequence'] += 1
        policy['profiles'][1]['status'] = 'revoked'; self.update(policy)
        self.client.handle('/model switch')
        self.assertEqual(self.client.model_menu.pending[1], ('synthetic-model',))
        self.client.handle('/cancel')
        with self.assertRaises(AccessDenied): self.client.handle('/model install second-model')
        self.client.handle('/model remove second-model'); self.client.handle('yes')
        self.assertFalse(self.manager.installed(self.other))
