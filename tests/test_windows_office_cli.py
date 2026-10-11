"""Office CLI must retain operation failures when owned-process teardown passes."""
import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class OfficeValidatorCliTests(unittest.TestCase):
    def run_case(self, *, kind='powerpoint', checks=None, receipt=True,
                 helper_exit=0, wait_exit=0, owner=True, status=None):
        with tempfile.TemporaryDirectory(prefix='silo-office-validator-') as temp:
            fixtures = Path(temp)/'fixtures'
            fixtures.mkdir()
            evidence = Path(temp)/'evidence'
            commands = []

            def run(command, **kwargs):
                commands.append(command)
                if '-File' in command:
                    output = Path(command[command.index('-Output')+1])
                    if receipt:
                        value = {'kind': kind, 'checks': checks or {}, 'errors': []}
                        if status is not None:
                            value['status'] = status
                        output.write_text(json.dumps(value), encoding='utf-8')
                    if owner:
                        output.with_name(output.name+'.owner.json').write_text(json.dumps({
                            'ProcessId': 12345, 'Name': 'POWERPNT.EXE',
                            'StartTimeUtcTicks': 638900000000000000}), encoding='utf-8')
                    return SimpleNamespace(returncode=helper_exit, stdout='', stderr='')
                return SimpleNamespace(returncode=wait_exit, stdout='', stderr='')

            argv = ['validate_windows_office.py', '--fixtures', str(fixtures),
                    '--evidence', str(evidence), '--kinds', kind]
            with patch.object(sys, 'argv', argv), patch('subprocess.run', side_effect=run), \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as stopped:
                    runpy.run_path(str(ROOT/'scripts/validate_windows_office.py'), run_name='__main__')
            result = json.loads((evidence/('native-office-'+kind+'.json')).read_text())
            return stopped.exception.code, result, commands

    def test_missing_receipt_fails_even_after_successful_teardown(self):
        for helper_exit in (0, 1):
            with self.subTest(helper_exit=helper_exit):
                exit_code, receipt, _ = self.run_case(receipt=False, helper_exit=helper_exit)
                self.assertEqual(exit_code, 1)
                self.assertTrue(receipt['checks']['owned_process_exited'])
                self.assertEqual(receipt['status'], 'failed')
                self.assertEqual(receipt['helper_exit'], helper_exit)
                self.assertTrue(receipt['errors'])

    def test_nonzero_helper_exit_fails_with_an_otherwise_passing_receipt(self):
        exit_code, receipt, _ = self.run_case(checks={'values': True, 'geometry': True}, helper_exit=1)
        self.assertEqual(exit_code, 1)
        self.assertEqual(receipt['helper_exit'], 1)
        self.assertTrue(receipt['errors'])

    def test_empty_or_partial_operation_checks_cannot_pass_on_teardown_alone(self):
        for checks in ({}, {'values': True}, {'values': True, 'geometry': False}):
            with self.subTest(checks=checks):
                exit_code, receipt, _ = self.run_case(checks=checks)
                self.assertEqual(exit_code, 1)
                self.assertTrue(receipt['checks']['owned_process_exited'])

    def test_each_office_case_requires_its_own_complete_results(self):
        cases = {
            'word-control': {'new_empty_document': True},
            'word': {'values': True, 'pdf_export': True},
            'excel': {'values': True, 'no_formulas': True, 'no_external_links': True, 'pdf_export': True},
            'powerpoint-control': {'new_empty_presentation': True},
            'powerpoint': {'values': True, 'geometry': True},
        }
        for kind, checks in cases.items():
            with self.subTest(kind=kind):
                self.assertEqual(self.run_case(kind=kind, checks=checks, owner=False)[0], 0)
                self.assertEqual(self.run_case(kind=kind, checks={'unrelated': True}, owner=False)[0], 1)

    def test_successful_operation_and_owned_exit_pass(self):
        exit_code, receipt, commands = self.run_case(checks={'values': True, 'geometry': True})
        self.assertEqual(exit_code, 0)
        self.assertTrue(receipt['checks']['owned_process_exited'])
        self.assertIn("$ErrorActionPreference='Stop'", commands[1][-1])

    def test_failed_owned_exit_remains_failed(self):
        exit_code, receipt, _ = self.run_case(checks={'values': True, 'geometry': True}, wait_exit=1)
        self.assertEqual(exit_code, 1)
        self.assertFalse(receipt['checks']['owned_process_exited'])
        self.assertTrue(receipt['errors'])

    def test_explicit_failure_status_cannot_pass(self):
        for status in ('failed', 'blocked'):
            with self.subTest(status=status):
                self.assertEqual(self.run_case(checks={'values': True, 'geometry': True}, status=status)[0], 1)


if __name__ == '__main__':
    unittest.main()
