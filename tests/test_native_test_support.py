"""Explicit candidates authenticate managed enrollment; no active-record fallback.

Managed gates are mocked only to exercise this adapter's routing and closure.
These fixtures do not enroll trust or qualify a native contained worker.
"""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import native_test_support as support
from local_ai_appliance.folders import AccessDenied

@unittest.skipUnless(os.name == 'nt', 'Windows installed-worker adapter')
class NativeTestSupportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.app = self.root/'versions'/'fixture'/'payload'/'app'
        self.worker = self.app.parent/'worker'
        self.worker.mkdir(parents=True)
        (self.worker/'python.exe').write_bytes(b'inert mock interpreter')
        self.security = Mock()
        self.environment = patch.dict(os.environ, {'SILO_NATIVE_TEST_ROOT':str(self.app)})
        self.environment.start(); self.addCleanup(self.environment.stop)
        support.verified_native_worker.cache_clear()
        self.addCleanup(support.verified_native_worker.cache_clear)

    def test_invalid_explicit_root_never_falls_back(self):
        with patch('local_ai_appliance.evaluation_install.installed_config',return_value=None), \
             patch('local_ai_appliance.managed_deployment.ManagedDeployment') as authenticate:
            with self.assertRaisesRegex(RuntimeError,'installed payload/app'):
                support.verified_native_worker()
            authenticate.assert_not_called()

    def test_enrolled_candidate_needs_no_active_record_and_closes_gate(self):
        self.assertFalse((self.root/'active.json').exists())
        with patch('local_ai_appliance.evaluation_install.installed_config',return_value={}), \
             patch('local_ai_appliance.managed_deployment.ManagedDeployment',return_value=self.security) as authenticate:
            self.assertEqual(support.verified_native_worker(),self.worker)
            authenticate.assert_called_once_with(self.app,candidate=True)
            self.security.close.assert_called_once_with()

    def test_unsigned_active_record_cannot_replace_managed_authentication(self):
        (self.root/'active.json').write_text(json.dumps({'version':'fixture','manifest_sha256':'a'*64}))
        with patch('local_ai_appliance.evaluation_install.installed_config',return_value={}), \
             patch('local_ai_appliance.managed_deployment.ManagedDeployment',side_effect=AccessDenied('unenrolled candidate')) as authenticate:
            with self.assertRaisesRegex(AccessDenied,'unenrolled candidate'):
                support.verified_native_worker()
            authenticate.assert_called_once_with(self.app,candidate=True)

    def test_integrity_failure_propagates_without_worker_fallback(self):
        with patch('local_ai_appliance.evaluation_install.installed_config',return_value={}), \
             patch('local_ai_appliance.managed_deployment.ManagedDeployment',side_effect=RuntimeError('synthetic drift')):
            with self.assertRaisesRegex(RuntimeError,'synthetic drift'):
                support.verified_native_worker()

    def test_missing_worker_still_closes_authenticated_gate(self):
        (self.worker/'python.exe').unlink()
        with patch('local_ai_appliance.evaluation_install.installed_config',return_value={}), \
             patch('local_ai_appliance.managed_deployment.ManagedDeployment',return_value=self.security):
            with self.assertRaises(unittest.SkipTest):support.verified_native_worker()
            self.security.close.assert_called_once_with()
