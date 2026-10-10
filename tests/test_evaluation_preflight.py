"""Preflight failure/reporting decisions; native execution is deliberately mocked."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('evaluation_preflight', ROOT/'scripts/check_evaluation_install.py')
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class SyntheticSession:
    def __init__(self):
        token = {'appcontainer': True, 'capability_count': 0, 'profile_loopback_exempt': False}
        self.evidence = {'full_gpu': True, 'server_token': token, 'worker_tokens': [token],
                         'parser_tokens': [token, token]}
        self.granted, self.closed = False, False
        self.workspace = self
        self.broker = self
    def start(self, progress): pass
    def folders(self): return [SimpleNamespace(id='synthetic')] if self.granted else []
    def grant(self, path, access):
        self.granted = True
        return SimpleNamespace(id='synthetic')
    def revoke(self, identifier): self.granted = False
    def ask(self, prompt):
        return SimpleNamespace(answer='37 crates', citations=[SimpleNamespace(cited_start=2, cited_end=2)])
    def open_document(self, folder, filename):
        return SimpleNamespace(unit_kind='page' if filename.endswith('.pdf') else 'paragraph')
    def close(self):
        self.closed = True
        self.evidence['cleanup_complete'] = True


class EvaluationPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name).resolve()
        self.session = SyntheticSession()
    def run_preflight(self):
        with patch.object(preflight, 'os', SimpleNamespace(name='nt')), \
             patch.object(preflight, 'verify_release'), \
             patch.object(preflight, 'installed_config', return_value={'state_root': str(self.state)}), \
             patch.object(preflight.importlib, 'import_module'), \
             patch.object(preflight, 'WindowsSession', return_value=self.session), \
             contextlib.redirect_stdout(io.StringIO()):
            result = preflight.main(['--manifest-sha256', 'a'*64])
        return result, json.loads((self.state/'installation-preflight.json').read_text())
    def test_success_report_keeps_deployment_and_isolation_acceptance_false(self):
        result, report = self.run_preflight()
        self.assertEqual(result, 0)
        self.assertTrue(report['evaluation_preflight_passed'])
        self.assertFalse(report['deployment_ready'])
        self.assertFalse(report['full_isolation_accepted'])
        self.assertTrue(self.session.closed)
    def test_model_startup_failure_reports_stage_and_closes_without_error_text(self):
        with patch.object(self.session, 'start', side_effect=RuntimeError('SENSITIVE hypothetical exception text')):
            result, report = self.run_preflight()
        self.assertEqual(result, 1)
        self.assertEqual(report['failure'], {'stage': 'model_startup', 'error_type': 'RuntimeError'})
        self.assertFalse(report['evaluation_preflight_passed'])
        self.assertTrue(self.session.closed)
        self.assertNotIn('SENSITIVE', json.dumps(report))
    def test_cleanup_failure_prevents_publication(self):
        with patch.object(self.session, 'close', side_effect=OSError('Synthetic cleanup failure')):
            result, report = self.run_preflight()
        self.assertEqual(result, 1)
        self.assertEqual(report['failure']['stage'], 'cleanup')
        self.assertFalse(report['checks']['cleanup'])
    def test_missing_token_or_loopback_exemption_is_not_accepted(self):
        self.session.evidence['worker_tokens'] = []
        result, report = self.run_preflight()
        self.assertEqual(result, 1)
        self.assertFalse(report['checks']['contained_tokens'])
        self.session.evidence['worker_tokens'] = [{'appcontainer':True, 'capability_count':0, 'profile_loopback_exempt':True}]
        result, report = self.run_preflight()
        self.assertEqual(result, 1)
        self.assertFalse(report['checks']['contained_tokens'])
    def test_existing_nonfixture_bytes_are_preserved(self):
        fixture = self.state/'preflight'
        fixture.mkdir()
        original = b'Existing bytes that are not installer fixtures'
        (fixture/'source.txt').write_bytes(original)
        result, report = self.run_preflight()
        self.assertEqual(result, 1)
        self.assertEqual(report['failure']['stage'], 'synthetic_fixtures')
        self.assertEqual((fixture/'source.txt').read_bytes(), original)
        self.assertFalse(self.session.closed)  # No session was acquired.


if __name__ == '__main__': unittest.main()
