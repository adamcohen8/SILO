"""Actual NTFS held-handle mutations in an owned synthetic fixture only.

These observations do not enroll repository-apply acceptance. No generated code,
Git hooks or model executes. The production controller continues to fail closed.
"""
import os
from pathlib import Path
import tempfile
import unittest
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.windows_folders import WindowsFolderBroker


@unittest.skipUnless(os.name=='nt','Native NTFS sharing and publication required')
class WindowsRepositoryMutationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='silo-native-repository-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.broker=WindowsFolderBroker(validation_mode=True)
        self.addCleanup(self.broker.close);self.grant=self.broker.grant(self.root,'editable')

    def test_replace_delete_create_and_nested_publication(self):
        (self.root/'a.py').write_bytes(b'old')
        self.broker.apply_reviewed_change(self.grant.id,'a.py',b'old',b'new')
        self.assertEqual((self.root/'a.py').read_bytes(),b'new')
        self.broker.apply_reviewed_change(self.grant.id,'a.py',b'new',None)
        self.broker.apply_reviewed_change(self.grant.id,'sub/new.py',None,b'new')
        self.assertFalse((self.root/'a.py').exists());self.assertEqual((self.root/'sub/new.py').read_bytes(),b'new')

    def test_preimage_conflict_and_existing_create_preserve_bytes(self):
        (self.root/'a.py').write_bytes(b'concurrent')
        for before in (b'old',None):
            with self.assertRaises(AccessDenied):self.broker.apply_reviewed_change(self.grant.id,'a.py',before,b'new')
        self.assertEqual((self.root/'a.py').read_bytes(),b'concurrent')

    def test_readonly_grant_and_hardlink_mutation_refused(self):
        self.broker.revoke(self.grant.id);self.grant=self.broker.grant(self.root,'read-only')
        with self.assertRaises(AccessDenied):self.broker.apply_reviewed_change(self.grant.id,'a.py',None,b'new')
        self.broker.revoke(self.grant.id);self.grant=self.broker.grant(self.root,'editable')
        (self.root/'a.py').write_bytes(b'old');os.link(self.root/'a.py',self.root/'b.py')
        with self.assertRaises((OSError,AccessDenied)):self.broker.apply_reviewed_change(self.grant.id,'a.py',b'old',b'new')
        self.assertEqual((self.root/'b.py').read_bytes(),b'old')

    def test_exclusive_checked_handle_blocks_second_writer(self):
        (self.root/'a.py').write_bytes(b'old')
        grant=self.broker._get(self.grant.id)
        with self.broker._directory(grant,[]) as parent:
            handle=self.broker._native.open_child(parent,'a.py',directory=False,edit=True)
            try:
                with self.assertRaises(OSError):(self.root/'a.py').write_bytes(b'concurrent')
                self.assertEqual(self.broker._native.read(handle,100),b'old')
            finally:self.broker._native.close(handle)


if __name__=='__main__':unittest.main()
