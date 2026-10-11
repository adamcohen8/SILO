"""Cross-lane host lifecycle and unsigned-update authority regressions."""
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.windows_session import WindowsSession
from local_ai_appliance.terminal_updates import TerminalUpdater
from local_ai_appliance.update_installation import install_update
from local_ai_appliance.backend import WindowsSessionAdapter
from local_ai_appliance.contracts import Project


class SecurityReconciliationTests(unittest.TestCase):
    def cleanup_service(self):
        service = WindowsSession.__new__(WindowsSession)
        service._operation = threading.RLock()
        service._guard = threading.RLock()
        service.closed = False
        service.conversation = Mock()
        service.code = service.drain = service.directory = service.security = None
        service.workspace = Mock()
        service.workspace.broker.saved_grants.return_value = []
        service.workspace.pending_proposals.return_value = []
        service.container = Mock()
        service._lockfile = Mock()
        service.evidence = {}
        service.model_manager = None
        service.instructions = ''
        service.recreate = Mock()
        return service

    def test_failed_native_service_cleanup_blocks_every_recovery_attempt(self):
        service = self.cleanup_service()
        service.container.close.side_effect = OSError('owned process remains live')
        host = WindowsSessionAdapter(Project('fixture', 'Fixture'), service)
        host._cancelled.set()
        native_lock = SimpleNamespace(locking=Mock(), LK_UNLCK=0)
        with patch.dict('sys.modules', {'msvcrt': native_lock}):
            for attempt in range(2):
                with self.subTest(attempt=attempt), self.assertRaisesRegex(RuntimeError, 'cleanup was incomplete'):
                    host.recover()
                service.recreate.assert_not_called()
        self.assertFalse(service.evidence['cleanup_complete'])
        service.container.close.assert_called_once()

    def test_successful_service_cleanup_remains_idempotent(self):
        service = self.cleanup_service()
        native_lock = SimpleNamespace(locking=Mock(), LK_UNLCK=0)
        with patch.dict('sys.modules', {'msvcrt': native_lock}):
            service.close()
            service.close()
        self.assertTrue(service.evidence['cleanup_complete'])
        service.container.close.assert_called_once()
        service._lockfile.close.assert_called_once()

    def test_native_lock_retirement_failure_cannot_be_hidden_by_closed_flag(self):
        service = self.cleanup_service()
        native_lock = SimpleNamespace(locking=Mock(side_effect=OSError('unlock failed')), LK_UNLCK=0)
        with patch.dict('sys.modules', {'msvcrt': native_lock}):
            with self.assertRaises(OSError): service.close()
            with self.assertRaisesRegex(RuntimeError, 'cleanup was incomplete'): service.close()
        self.assertFalse(service.evidence['cleanup_complete'])

    def test_recreation_reopens_machine_policy_and_preserves_candidate_mode(self):
        old = WindowsSession.__new__(WindowsSession)
        old.root, old.evaluation = Path('/inert/app'), True
        old.model_manager = SimpleNamespace(root=old.root, vault=object(), model_cache=Path('/inert/models'),
            required_key_sha256='a'*64, policy=SimpleNamespace(clock=lambda: 42, vault=object()))
        fresh = SimpleNamespace(security=SimpleNamespace(store=object()), close=Mock())
        with patch.object(WindowsSession, '__new__', return_value=fresh) as allocate, \
             patch('local_ai_appliance.model_management.ModelManager') as manager:
            result = old.recreate()
        self.assertIs(result, fresh)
        allocate.assert_called_once_with(WindowsSession, old.root, evaluation=True)
        kwargs = manager.call_args.kwargs
        self.assertIs(kwargs['policy_store'], fresh.security.store)
        self.assertIs(manager.call_args.args[1], old.model_manager.vault)
        self.assertEqual(kwargs['model_cache'], old.model_manager.model_cache)
        fresh.close.assert_not_called()

    def test_provisioning_blocks_unsigned_update_before_network_or_ticket_access(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch('local_ai_appliance.terminal_updates.os', SimpleNamespace(name='nt')), \
             patch('local_ai_appliance.machine_security.machine_directory', return_value=Path(temp)), \
             patch('local_ai_appliance.terminal_updates.installed_config') as config:
            with self.assertRaisesRegex(AccessDenied, 'administrator-signed'):
                TerminalUpdater('/inert/app')
            config.assert_not_called()
            with self.assertRaisesRegex(AccessDenied, 'administrator-signed'):
                install_update('/inert/app', '/inert/request.json')

    def test_existing_updater_refuses_after_machine_is_provisioned(self):
        manager = TerminalUpdater.__new__(TerminalUpdater)
        manager.stop = Mock(); manager.stop.is_set.return_value = False
        with tempfile.TemporaryDirectory() as temp, \
             patch('local_ai_appliance.terminal_updates.os', SimpleNamespace(name='nt')), \
             patch('local_ai_appliance.machine_security.machine_directory', return_value=Path(temp)):
            with self.assertRaisesRegex(AccessDenied, 'administrator-signed'):
                manager.checkpoint()
            with self.assertRaisesRegex(AccessDenied, 'administrator-signed'):
                manager.launch('/inert/request.json')


if __name__ == '__main__': unittest.main()
