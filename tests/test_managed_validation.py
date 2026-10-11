"""Candidate evidence collectors cannot fall back to unsigned active records."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch
from local_ai_appliance.folders import AccessDenied

spec = importlib.util.spec_from_file_location('validation_support', Path(__file__).resolve().parents[1]/'scripts/windows_validation_support.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)


class ManagedValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root/'release/payload/app'
        self.state = self.root/'state'
        self.fixture = self.root/'fixture'
        for name in ('Reference', 'Drafts'):
            (self.fixture/name).mkdir(parents=True)
        self.security = SimpleNamespace(release=self.root/'release', release_sha256='a'*64,
            bundle={'version':'1.2.3','configuration_id':'review'}, storage=Mock(), close=Mock())

    def collect(self, **kwargs):
        with patch('local_ai_appliance.evaluation_install.installed_config', return_value={'state_root':str(self.state)}), \
             patch('local_ai_appliance.managed_deployment.ManagedDeployment',return_value=self.security) as gate:
            result = support.candidate_installation(self.app, candidate=True, **kwargs)
            gate.assert_called_once_with(self.app.resolve(),candidate=True)
            return result

    def test_explicit_candidate_is_required_before_accessing_machine_state(self):
        for value in (False,None,1,'true'):
            with self.subTest(value=value), patch('local_ai_appliance.managed_deployment.ManagedDeployment') as gate:
                with self.assertRaises(AccessDenied):support.candidate_installation(self.app,candidate=value)
                gate.assert_not_called()

    def test_identity_is_signed_enrolled_identity_and_acceptance_stays_pending(self):
        config,identity=self.collect(fixture_root=self.fixture)
        self.assertEqual(identity['release_sha256'],'a'*64)
        self.assertEqual(identity['technical_acceptance'],'pending')
        self.assertTrue(identity['candidate'])
        self.security.storage.directory.assert_any_call(self.fixture/'Reference','read-only')
        self.security.storage.directory.assert_any_call(self.fixture/'Drafts','editable')
        self.security.close.assert_called_once()

    def test_denied_storage_closes_gate_and_preserves_fixture(self):
        self.security.storage.directory.side_effect=AccessDenied('Denied')
        with self.assertRaises(AccessDenied):self.collect(fixture_root=self.fixture)
        self.security.close.assert_called_once()
        self.assertEqual(list((self.fixture/'Reference').iterdir()),[])

    def test_existing_fixture_is_preserved_and_refused(self):
        file=self.fixture/'Reference/original.txt';file.write_bytes(b'existing')
        with self.assertRaises(AccessDenied):self.collect(fixture_root=self.fixture)
        self.assertEqual(file.read_bytes(),b'existing')
        self.security.close.assert_called_once()

    def test_software_or_private_state_is_never_a_synthetic_grant(self):
        for folder in (self.state,self.app,self.root/'release',self.root):
            with self.subTest(folder=folder):
                with self.assertRaises(AccessDenied):self.collect(fixture_root=folder)

    def test_source_checkout_cannot_collect_managed_candidate_evidence(self):
        with patch('local_ai_appliance.evaluation_install.installed_config',return_value=None), \
             patch('local_ai_appliance.managed_deployment.ManagedDeployment') as gate:
            with self.assertRaises(AccessDenied):support.candidate_installation(self.app,candidate=True)
            gate.assert_not_called()


if __name__=='__main__':unittest.main()
