"""Host observation failures must remain failed and preserve native receipts."""
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from windows_validation_support import host_connected


class HostConnectivityTests(unittest.TestCase):
    def test_timeout_records_failure_without_losing_other_checks(self):
        report = {'checks': {'owned_cleanup': True}}
        with patch('windows_validation_support.urllib.request.urlopen',
                   side_effect=urllib.error.URLError(TimeoutError('synthetic timeout'))):
            self.assertFalse(host_connected(report, 'after'))
        self.assertEqual(report['checks'], {'owned_cleanup': True})
        self.assertEqual(report['connectivity_errors'],
                         [{'phase': 'after', 'exception_type': 'URLError'}])

    def test_success_requires_http_200(self):
        response = MagicMock()
        response.__enter__.return_value.status = 200
        report = {}
        with patch('windows_validation_support.urllib.request.urlopen', return_value=response):
            self.assertTrue(host_connected(report, 'during'))
        self.assertNotIn('connectivity_errors', report)

    def test_other_status_remains_failed(self):
        response = MagicMock()
        response.__enter__.return_value.status = 503
        with patch('windows_validation_support.urllib.request.urlopen', return_value=response):
            self.assertFalse(host_connected({}, 'before'))


if __name__ == '__main__':
    unittest.main()
