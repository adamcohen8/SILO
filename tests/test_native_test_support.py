"""The test adapter fails closed on an invalid explicit installation."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import native_test_support as support

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
        self.state = self.root/'state'
        self.state.mkdir()
        (self.root/'active.json').write_text(json.dumps({'version':'fixture','manifest_sha256':'a'*64}))
        self.environment = patch.dict(os.environ, {'SILO_NATIVE_TEST_ROOT':str(self.app)})
        self.environment.start(); self.addCleanup(self.environment.stop)
        support.verified_native_worker.cache_clear()
        self.addCleanup(support.verified_native_worker.cache_clear)

    def test_invalid_explicit_root_never_falls_back(self):
        with patch('local_ai_appliance.evaluation_install.installed_config',return_value=None):
            with self.assertRaisesRegex(RuntimeError,'installed payload/app'):
                support.verified_native_worker()

    def test_inactive_payload_refused_before_verification(self):
        (self.root/'active.json').write_text(json.dumps({'version':'other','manifest_sha256':'a'*64}))
        with patch('local_ai_appliance.evaluation_install.installed_config',return_value={'state_root':str(self.state)}), patch('local_ai_appliance.evaluation_install.verify_release') as verify:
            with self.assertRaisesRegex(RuntimeError,'active installed version'):
                support.verified_native_worker()
            verify.assert_not_called()

    def test_active_payload_verified_and_integrity_failure_propagates(self):
        with patch('local_ai_appliance.evaluation_install.installed_config',return_value={'state_root':str(self.state)}), patch('local_ai_appliance.evaluation_install.verify_release',side_effect=RuntimeError('synthetic drift')) as verify:
            with self.assertRaisesRegex(RuntimeError,'synthetic drift'):
                support.verified_native_worker()
            verify.assert_called_once_with(self.app.parent.parent,'a'*64)
            verify.side_effect = None
            self.assertEqual(support.verified_native_worker(),self.worker)
