import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from local_ai_appliance.folder_settings import FolderSettings


class FolderSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = FolderSettings(Path(self.temp.name)/'folders.json')
        self.entry = {'path': 'C:\\Synthetic\\Reference', 'access': 'read-only', 'volume': 12, 'index': 34}

    def test_missing_settings_and_metadata_only_round_trip(self):
        self.assertEqual(self.settings.load(), [])
        self.settings.save([self.entry])
        self.assertEqual(self.settings.load(), [self.entry])
        self.assertEqual(set(json.loads(self.settings.path.read_bytes())), {'version', 'folders'})

    def test_invalid_network_permissions_identity_and_duplicate_settings_rejected(self):
        for changes in ({'path': '\\\\server\\share'}, {'path': 'C:\\'}, {'access': 'owner'},
                        {'volume': True}, {'index': -1}, {'prompt': 'Unwanted history'}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, RuntimeError)):
                value = {'version': 1, 'folders': [dict(self.entry, **changes)]}
                self.settings.path.write_text(json.dumps(value), encoding='utf-8')
                self.settings.load()
        value = {'version': 1, 'folders': [self.entry, dict(self.entry, path='c:\\synthetic\\reference')]}
        self.settings.path.write_text(json.dumps(value), encoding='utf-8')
        with self.assertRaises(RuntimeError):
            self.settings.load()

    def test_oversized_and_duplicate_json_rejected(self):
        for payload in (b' '*(self.settings.MAX_BYTES+1), b'{"version":1,"version":1,"folders":[]}'):
            self.settings.path.write_bytes(payload)
            with self.assertRaises(RuntimeError):
                self.settings.load()

    def test_failed_atomic_replace_preserves_previous_settings_and_removes_temporary_file(self):
        self.settings.save([self.entry])
        with patch('local_ai_appliance.folder_settings.os.replace', side_effect=OSError('Synthetic write failure')):
            with self.assertRaises(OSError):
                self.settings.save([])
        self.assertEqual(self.settings.load(), [self.entry])
        self.assertEqual(list(self.settings.path.parent.glob('.folders-*.tmp')), [])
