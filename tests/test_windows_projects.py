"""Native key/ACL checks. These do not qualify inference or authorize CUI."""
import os
from pathlib import Path
import tempfile
import unittest

from local_ai_appliance.project_store import LocalVault,ProjectStore,dpapi,project_data_directory

@unittest.skipUnless(os.name=='nt','Native Windows DPAPI/NTFS acceptance deferred')
class WindowsProjectTests(unittest.TestCase):
    def test_current_account_protection_and_authenticated_reopen(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=project_data_directory(Path(temporary))
            vault=LocalVault(root,windows_validation=True)
            project=ProjectStore(vault).create('Native synthetic project')
            protected=(root/'vault.key').read_bytes()
            self.assertNotEqual(len(protected),32)
            self.assertEqual(len(dpapi(protected,decrypt=True)),32)
            vault.close()
            reopened=LocalVault(root,windows_validation=True)
            try:self.assertEqual(ProjectStore(reopened).load(project.id)['project']['name'],'Native synthetic project')
            finally:reopened.close()

    def test_unsafe_existing_directory_acl_not_broadened(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'projects';root.mkdir()
            with self.assertRaises(Exception):LocalVault(root,windows_validation=True)
