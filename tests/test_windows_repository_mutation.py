"""Actual NTFS held-handle mutations in an owned synthetic fixture only.

These observations do not enroll repository-apply acceptance. No generated code,
Git hooks or model executes. The production controller continues to fail closed.
"""
import os
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
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



    def test_checked_edit_lease_blocks_readers_and_renames_until_close(self):
        target=self.root/'a.py';target.write_bytes(b'old')
        native=self.broker._native;grant=self.broker._get(self.grant.id)
        with self.broker._directory(grant,[]) as parent:
            handle=native.open_child(parent,'a.py',directory=False,edit=True)
            try:
                for action in (target.read_bytes,lambda:target.write_bytes(b'foreign'),lambda:target.rename(self.root/'other.py')):
                    with self.assertRaises(OSError):action()
                self.assertEqual(native.read(handle,100),b'old')
            finally:native.close(handle)
        self.assertFalse(native._edit_reads)
        target.rename(self.root/'other.py')
        self.assertEqual((self.root/'other.py').read_bytes(),b'old')

    def test_name_replacement_before_id_reopen_denies_without_data_access(self):
        target=self.root/'a.py';target.write_bytes(b'old')
        native=self.broker._native;original=native.open_child
        def replace(parent,name,**options):
            if options.get('delete'):
                target.rename(self.root/'original.py');target.write_bytes(b'foreign')
            return original(parent,name,**options)
        with patch.object(native,'open_child',side_effect=replace),patch.object(native.kernel,'OpenFileById') as data_open:
            with self.assertRaises(OSError):self.broker.apply_reviewed_change(self.grant.id,'a.py',b'old',b'new')
            data_open.assert_not_called()
        self.assertEqual(target.read_bytes(),b'foreign');self.assertEqual((self.root/'original.py').read_bytes(),b'old')
        self.assertFalse(native._edit_reads)

    def test_failed_new_publication_restores_original_and_cleans_temporary(self):
        target=self.root/'a.py';target.write_bytes(b'old');native=self.broker._native
        publish=native.publish;count=0
        def fail_once(*args):
            nonlocal count
            count+=1
            if count==2:raise OSError('Synthetic new-name publication failure')
            return publish(*args)
        with patch.object(native,'publish',side_effect=fail_once):
            with self.assertRaises(OSError):self.broker.apply_reviewed_change(self.grant.id,'a.py',b'old',b'new')
        self.assertEqual(target.read_bytes(),b'old')
        self.assertEqual(sorted(p.name for p in self.root.iterdir()),['a.py'])
        self.assertFalse(native._edit_reads)

    def interrupted_gap(self):
        target=self.root/'a.py';target.write_bytes(b'old');native=self.broker._native;publish=native.publish;receipt={}
        def collision(handle,parent,name):
            if name=='a.py' and not target.exists():target.write_bytes(b'foreign')
            return publish(handle,parent,name)
        with patch.object(native,'publish',side_effect=collision):
            with self.assertRaises(AccessDenied):self.broker.apply_reviewed_change(self.grant.id,'a.py',b'old',b'new',journal=lambda v:receipt.update(v))
        return target,receipt

    def test_concurrent_creation_preserved_then_exact_backup_recovered(self):
        target,receipt=self.interrupted_gap();backup=self.root/receipt['backup']
        self.assertEqual(target.read_bytes(),b'foreign');self.assertEqual(backup.read_bytes(),b'old')
        with self.assertRaises(AccessDenied):self.broker.reconcile_reviewed_artifacts(self.grant.id,'a.py',b'old',b'new',receipt)
        target.unlink();self.broker.reconcile_reviewed_artifacts(self.grant.id,'a.py',b'old',b'new',receipt)
        self.assertEqual(target.read_bytes(),b'old');self.assertFalse(backup.exists())
        self.assertFalse(self.broker._native._edit_reads)

    def test_substituted_backup_identity_is_preserved_and_refused(self):
        target,receipt=self.interrupted_gap();backup=self.root/receipt['backup']
        backup.rename(self.root/'owned-original.py');backup.write_bytes(b'old');target.unlink()
        with self.assertRaises(AccessDenied):self.broker.reconcile_reviewed_artifacts(self.grant.id,'a.py',b'old',b'new',receipt)
        self.assertEqual(backup.read_bytes(),b'old');self.assertFalse(target.exists())
        self.assertEqual((self.root/'owned-original.py').read_bytes(),b'old')

    def test_partial_temporary_recovery_checks_identity_and_prefix(self):
        from secrets import token_hex
        native=self.broker._native;grant=self.broker._get(self.grant.id)
        target=self.root/'a.py';target.write_bytes(b'old')
        receipt={'backup':'.silo-replace-'+token_hex(16),'temporary':'.silo-write-'+token_hex(16),'backup_identity':None,'temporary_identity':None}
        with self.broker._directory(grant,[]) as parent:
            handle=native.open_child(parent,receipt['temporary'],directory=False,create=True)
            try:
                info=native.info(handle);receipt['temporary_identity']={'volume':info.volume,'index':info.index};native.write(handle,b'ne')
            finally:native.close(handle)
        self.broker.reconcile_reviewed_artifacts(self.grant.id,'a.py',b'old',b'new',receipt)
        self.assertFalse((self.root/receipt['temporary']).exists());self.assertEqual(target.read_bytes(),b'old')

    def test_process_crash_after_backup_publication_recovers_owned_remnants(self):
        import local_ai_appliance.windows_native as native_module
        (self.root/'a.py').write_bytes(b'old');receipt=self.root/'recovery.json'
        # Fixed developer-authored host probe. It qualifies neither a worker
        # process boundary nor public repository-apply acceptance.
        source_root=Path(native_module.__file__).resolve().parents[1]
        probe="""import sys,os,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from local_ai_appliance.windows_folders import WindowsFolderBroker
root=Path(sys.argv[2]);receipt=Path(sys.argv[3]);b=WindowsFolderBroker(validation_mode=True);g=b.grant(root,'editable');n=b._native;publish=n.publish
def journal(v):
 with receipt.open('w') as f:
  json.dump(v,f);f.flush();os.fsync(f.fileno())
def crash(handle,parent,name):
 publish(handle,parent,name)
 if name.startswith('.silo-replace-'):os._exit(71)
n.publish=crash
b.apply_reviewed_change(g.id,'a.py',b'old',b'new',journal=journal)
"""
        result=subprocess.run([sys.executable,'-I','-B','-c',probe,str(source_root),str(self.root),str(receipt)],capture_output=True,timeout=15)
        self.assertEqual(result.returncode,71,result.stderr.decode())
        artifacts=json.loads(receipt.read_text());self.assertFalse((self.root/'a.py').exists())
        self.assertEqual((self.root/artifacts['backup']).read_bytes(),b'old')
        self.assertEqual((self.root/artifacts['temporary']).read_bytes(),b'new')
        self.broker.reconcile_reviewed_artifacts(self.grant.id,'a.py',b'old',b'new',artifacts)
        self.assertEqual((self.root/'a.py').read_bytes(),b'old')
        self.assertFalse((self.root/artifacts['backup']).exists());self.assertFalse((self.root/artifacts['temporary']).exists())

    def test_unicode_empty_and_newline_variants(self):
        for i,(before,after) in enumerate(((b'',b'new'),(b'old',b''),(b'old\n',b'new\n'),(b'old\r\n',b'new'))):
            name=f'cafÃ©-{i}.py';target=self.root/name;target.write_bytes(before)
            self.broker.apply_reviewed_change(self.grant.id,name,before,after);self.assertEqual(target.read_bytes(),after)
            self.broker.apply_reviewed_change(self.grant.id,name,after,None);self.assertFalse(target.exists())


if __name__=='__main__':unittest.main()
