"""Published-release protocol and real staging/rollback with inert executables."""
from contextlib import contextmanager
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

from local_ai_appliance.evaluation_install import verify_release
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.model import json_bytes
from local_ai_appliance.release_bootstrap import assemble, git_snapshot
from local_ai_appliance.terminal_client import TerminalClient
from local_ai_appliance.terminal_ui import TerminalView
from local_ai_appliance.terminal_updates import (REPOSITORY, TerminalUpdater, discover,
                                               extract_source, read_origin, validate_origin)
from local_ai_appliance import update_installation as installation
import test_evaluation_install as fixtures

ROOT = Path(__file__).resolve().parents[1]


class Network:
    def __init__(self, assets, metadata):
        self.metadata = metadata
        self.assets = assets
        self.release = {'draft': False, 'prerelease': False, 'tag_name': metadata['tag'],
            'assets': [{'name': name, 'state': 'uploaded', 'size': len(data),
                       'browser_download_url': f'https://github.com/{REPOSITORY}/releases/download/{metadata["tag"]}/{name}',
                       'digest': 'sha256:'+hashlib.sha256(data).hexdigest()}
                      for name, data in assets.items()]}
        self.calls = []
    def get(self, url, *, limit, cancel=lambda: None):
        cancel(); self.calls.append(url)
        data = json_bytes(self.release) if url.endswith('/releases/latest') else self.assets[url.rsplit('/', 1)[1]]
        if len(data) > limit: raise AccessDenied('Synthetic response too large')
        cancel(); return data


@contextmanager
def no_native_lock(path):
    yield


class UpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        source = git_snapshot(ROOT, revision)
        # Include current changes so the complete staged source gate runs pre-commit.
        for folder in ('src', 'scripts', 'tests', 'installer', 'profiles'):
            for path in (ROOT/folder).rglob('*'):
                if path.is_file() and path.suffix in {'.py', '.ps1', '.in', '.json'}:
                    source[path.relative_to(ROOT).as_posix()] = path.read_bytes()
        cls.assets, cls.metadata = assemble(source, 'b'*40, REPOSITORY, 'evaluation-update-test', update_sequence=2)

    def setUp(self):
        self.fixture = fixtures.EvaluationInstallTests()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.fixture.fixture()
        for name in ('start_windows_terminal.py', 'run_terminal_update.py'):
            (self.fixture.source/'scripts'/name).write_bytes(b'Inert source; never executed')
        self.base = self.fixture.root/'installed'
        self.old = self.base/'versions'/('a'*16+'-'+'c'*8)
        self.old.mkdir(parents=True)
        self.fixture.destination = self.old
        self.previous = self.fixture.build()
        self.root = self.old/'payload/app'
        self.fixture.state.rename(self.base/'state')
        self.fixture.state = self.base/'state'
        # Rebuild immutable configuration after choosing the final state path.
        import shutil
        shutil.rmtree(self.old); self.old.mkdir()
        self.previous = self.fixture.build()
        self.network = Network(copy.deepcopy(self.assets), copy.deepcopy(self.metadata))
        self.active = {'version': self.old.name, 'manifest_sha256': self.previous['manifest_sha256']}
        (self.base/'active.json').write_bytes(json_bytes(self.active))
        (self.base/'Start-LocalAI.cmd').write_bytes(b'previous launcher\r\n')
        self.updater = TerminalUpdater(self.root, network=self.network, required_key='d'*64, plain=True, scrollback=True)
        self.spawned = []

    def stage(self):
        self.assertIn('Update available', self.updater.check())
        return self.updater.stage()

    def runner(self, command, **kwargs):
        if '--application-update' not in command: raise AssertionError('Updater must preserve models')
        if '--destination' in command:
            self.fixture.destination = Path(command[command.index('--destination')+1])
            (self.fixture.source/'profiles/release-origin.json').write_bytes(json_bytes(self.metadata['update']))
            result = self.fixture.build(include_model=False)
            Path(command[command.index('--result')+1]).write_bytes(json_bytes(result))
        else:
            self.assertIn('--required-policy-key-sha256', command)
            self.assertIn('d'*64, command)
            digest = command[command.index('--manifest-sha256')+1]
            report = {'manifest_sha256': digest, 'mode': 'application_update',
                      'evaluation_preflight_passed': True, 'deployment_ready': False, 'full_isolation_accepted': False}
            (self.fixture.state/'installation-preflight.json').write_bytes(json_bytes(report))
        return SimpleNamespace(returncode=0)

    def install(self, ticket, **options):
        return installation.install_update(self.root, ticket, network=self.network, runner=self.runner,
            lock=no_native_lock, wait=lambda pid: None,
            spawn=lambda release, request: self.spawned.append((release, request)), **options)

    def test_verified_update_stages_activates_and_preserves_model_selection_and_state(self):
        projects = self.fixture.state/'projects'; projects.mkdir()
        sentinel = projects/'retained'; sentinel.write_bytes(b'Inert encrypted project/settings sentinel')
        models = {p.name: p.read_bytes() for p in (self.fixture.state/'models').iterdir()}
        ticket = self.stage()
        result = self.install(ticket)
        self.assertEqual(result['status'], 'installed')
        active = json.loads((self.base/'active.json').read_bytes())
        self.assertEqual(active['version'], result['version'])
        target = self.base/'versions'/result['version']
        verify_release(target, result['manifest_sha256'])
        self.assertEqual(read_origin(target/'payload/app'), self.metadata['update'])
        self.assertEqual(json.loads((self.base/'active.previous.json').read_bytes()), self.active)
        self.assertEqual(sentinel.read_bytes(), b'Inert encrypted project/settings sentinel')
        self.assertEqual({p.name:p.read_bytes() for p in (self.fixture.state/'models').iterdir()}, models)
        self.assertEqual(self.spawned[0][0], target)
        command = installation.terminal_command(target, self.spawned[0][1])
        self.assertIn('--plain', command); self.assertIn('--scrollback', command)
        self.assertIn('d'*64, command)
        self.assertNotIn('--acceptance', command)
        self.assertIn(result['version'].encode(), (self.base/'Start-SILO-Terminal.cmd').read_bytes())
        with self.assertRaises(FileExistsError): self.install(ticket)
        self.assertEqual(len(self.spawned), 1)

    def test_preflight_failure_keeps_old_active_and_restarts_it(self):
        ticket = self.stage()
        original = self.runner
        def fail(command, **kwargs):
            return original(command, **kwargs) if '--destination' in command else SimpleNamespace(returncode=1)
        self.runner = fail
        result = self.install(ticket)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(json.loads((self.base/'active.json').read_bytes()), self.active)
        self.assertTrue(result['previous_restarted'])
        self.assertEqual(self.spawned[0][0], self.old)
        self.assertEqual((self.base/'Start-LocalAI.cmd').read_bytes(), b'previous launcher\r\n')
        self.assertFalse((self.base/'Start-SILO-Terminal.cmd').exists())

    def test_restart_launch_failure_restores_both_launchers_and_active_record(self):
        ticket = self.stage()
        snapshot = installation.activation_snapshot(self.base)
        def spawn(release, request):
            if release != self.old: raise OSError('Inert launch failure')
            self.spawned.append((release, request))
        result = installation.install_update(self.root, ticket, network=self.network, runner=self.runner,
            lock=no_native_lock, wait=lambda pid:None, spawn=spawn)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(installation.activation_snapshot(self.base), snapshot)
        self.assertTrue(result['previous_restarted'])

    def test_activation_write_failure_restores_preimages(self):
        ticket = self.stage(); snapshot = installation.activation_snapshot(self.base)
        def partial(base, record, previous):
            (base/'Start-LocalAI.cmd').write_bytes(b'partial activation')
            raise OSError('Inert write failure')
        with patch.object(installation, 'activate', side_effect=partial): result = self.install(ticket)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(installation.activation_snapshot(self.base), snapshot)

    def test_publication_or_source_changes_fail_before_preparation(self):
        ticket = self.stage()
        self.network.release['prerelease'] = True
        with patch.object(self, 'runner', side_effect=AssertionError('Changed publication must not execute')):
            result = self.install(ticket)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(self.spawned[0][0], self.old)

    def test_download_corruption_or_cancellation_keeps_current_session(self):
        self.updater.check()
        name = self.metadata['source_archive']['filename']
        self.network.assets[name] = b'corrupt source archive'
        with self.assertRaises(AccessDenied): self.updater.stage()
        self.assertEqual(json.loads((self.base/'active.json').read_bytes()), self.active)
        self.assertFalse(self.spawned)
        self.network.assets[name] = self.assets[name]
        self.updater.stop.set()
        with self.assertRaises(AccessDenied): self.updater.stage()

    def test_offline_is_not_reported_as_up_to_date(self):
        self.updater.network = Mock()
        self.updater.network.get.side_effect = OSError('offline')
        self.assertEqual(self.updater.check(), 'Unable to check for updates')
        self.assertIsNone(self.updater.available)

    def test_old_same_downgrade_or_legacy_release_is_not_an_update(self):
        candidate = discover(None, self.network)
        for sequence in (2, 3):
            origin = dict(candidate.origin, sequence=sequence)
            self.assertIsNone(discover(origin, self.network))
        origin = dict(candidate.origin, source_revision='a'*40)
        self.assertIsNone(discover(origin, self.network))
        metadata = dict(self.metadata); metadata.pop('update')
        self.network.assets['release.json'] = json_bytes(metadata)
        asset = next(a for a in self.network.release['assets'] if a['name']=='release.json')
        asset.update(size=len(self.network.assets['release.json']), digest='sha256:'+hashlib.sha256(self.network.assets['release.json']).hexdigest())
        self.assertIsNone(discover(None, self.network))

    def test_staged_source_drift_is_denied_before_any_installer_executes(self):
        ticket = self.stage()
        (ticket.parent/'source/payload/scripts/install_evaluation.py').write_bytes(b'changed installer')
        with patch.object(self, 'runner', side_effect=AssertionError('Changed source must not execute')):
            result = self.install(ticket)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(json.loads((self.base/'active.json').read_bytes()), self.active)

    def test_changed_active_version_is_preserved_without_restart(self):
        ticket = self.stage()
        concurrent = dict(self.active, version='e'*16)
        (self.base/'active.json').write_bytes(json_bytes(concurrent))
        with patch.object(self, 'runner', side_effect=AssertionError('Changed active version must not install')):
            result = self.install(ticket)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(json.loads((self.base/'active.json').read_bytes()), concurrent)
        self.assertFalse(self.spawned)

    def test_parent_exit_failure_never_restarts_over_live_session(self):
        ticket = self.stage()
        result = installation.install_update(self.root, ticket, network=self.network, runner=self.runner,
            lock=no_native_lock, wait=Mock(side_effect=AccessDenied('Parent still running')),
            spawn=Mock(side_effect=AssertionError('Must not restart a live parent')))
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(result['previous_restarted'])

    def test_lock_contention_never_prepares_or_changes_active(self):
        ticket = self.stage()
        @contextmanager
        def denied_lock(path):
            raise AccessDenied('Another installation holds this lock')
            yield
        runner = Mock(side_effect=AssertionError('Lock contention must not execute installer'))
        result = installation.install_update(self.root, ticket, network=self.network, runner=runner,
            lock=denied_lock, wait=lambda pid:None, spawn=Mock())
        runner.assert_not_called()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(json.loads((self.base/'active.json').read_bytes()), self.active)

    def test_missing_hash_or_untrusted_asset_url_is_denied(self):
        for field, value in [('digest', None), ('browser_download_url', 'https://example.invalid/installer')]:
            network = Network(self.assets, self.metadata)
            next(a for a in network.release['assets'] if a['name']=='release.json')[field] = value
            with self.assertRaises(AccessDenied): discover(None, network)
        for change in ({'sequence': True}, {'repository':'other/SILO'}, {'tag':'../bad'}, {'format_version':True}):
            with self.assertRaises(AccessDenied): validate_origin(dict(self.metadata['update'], **change))

    def test_archive_traversal_and_undeclared_payload_are_denied(self):
        candidate = discover(None, self.network)
        for name in ('payload/../escape.py', 'payload/models/model.gguf', 'unexpected.py'):
            archive = self.fixture.root/'unsafe.zip'
            with zipfile.ZipFile(archive, 'w') as stream: stream.writestr(name, b'inert')
            with self.assertRaises((AccessDenied, ValueError, RuntimeError)):
                extract_source(archive, self.fixture.root/'unsafe-output', candidate)
            self.assertFalse((self.fixture.root/'escape.py').exists())

    def test_host_update_guards_pending_reviews_code_and_unretained_chat(self):
        backend = SimpleNamespace(workspace=SimpleNamespace(pending_proposals=lambda:()),
                                  service=SimpleNamespace(code=None), persist=Mock())
        manager = Mock(stage=Mock(return_value='request.json'))
        client = TerminalClient(backend, view=TerminalView(io.StringIO(), plain=True), update_manager=manager)
        for condition in ('draft', 'code', 'chat', 'menu'):
            backend.workspace.pending_proposals = lambda: ('pending',) if condition=='draft' else ()
            backend.service.code = object() if condition=='code' else None
            backend.conversation = SimpleNamespace(turns=['unsaved'] if condition=='chat' else [])
            client.model_menu.pending = object() if condition=='menu' else None
            with self.assertRaises(AccessDenied): client.request_update()
        manager.stage.assert_not_called()
        client.model_menu.pending = None
        self.assertFalse(client.handle('/update'))
        backend.persist.assert_called_once()
        self.assertEqual(client.update_request, 'request.json')


@unittest.skipUnless(os.name == 'nt', 'Native Windows share-denied locks/process wait required')
class NativeUpdateLifecycleTests(unittest.TestCase):
    def test_updater_lock_excludes_another_updater_and_new_silo_session(self):
        from local_ai_appliance.windows_session import WindowsSession
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            state = root/'artifacts/windows-ui'; state.mkdir(parents=True)
            with installation.exclusive_lock(state/'session.lock'):
                with self.assertRaises(AccessDenied):
                    with installation.exclusive_lock(state/'session.lock'): pass
                with self.assertRaises(OSError): WindowsSession(root)
            session = WindowsSession(root)
            session.close()

    def test_existing_silo_session_blocks_update_reservation(self):
        from local_ai_appliance.windows_session import WindowsSession
        with tempfile.TemporaryDirectory() as directory:
            session = WindowsSession(Path(directory).resolve())
            try:
                with self.assertRaises(AccessDenied):
                    with installation.exclusive_lock(session.state/'session.lock'): pass
            finally: session.close()

    def test_parent_wait_requires_owned_child_exit(self):
        child = subprocess.Popen([sys.executable, '-I', '-c', 'import threading; threading.Event().wait(10)'])
        try:
            with self.assertRaises(AccessDenied): installation.wait_for_parent(child.pid, timeout=0)
        finally:
            child.terminate(); child.wait(timeout=5)
        installation.wait_for_parent(child.pid, timeout=1)


if __name__ == '__main__': unittest.main()
