"""Native DPAPI/NTFS project lifecycle, independent of model-quality claims."""
import os
from pathlib import Path
import tempfile
import unittest

from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.project_store import LocalVault, ProjectStore, project_data_directory

@unittest.skipUnless(os.name == 'nt', 'Native Windows private project storage')
class WindowsVaultLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='silo-vault-tests-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.state = project_data_directory(self.root)
        self.vault = LocalVault(self.state, windows_validation=True)
        self.addCleanup(self.vault.close)
        self.now = [1000.0]
        self.store = ProjectStore(self.vault, clock=lambda: self.now[0])
        self.project = self.store.create('Synthetic native lifecycle', retention_days=1)

    def other_vault(self, name):
        parent = self.root/name
        parent.mkdir()
        vault = LocalVault(project_data_directory(parent), windows_validation=True)
        self.addCleanup(vault.close)
        return vault

    def test_encrypted_records_and_tampered_ciphertext_denied(self):
        path = next(self.state.glob('project-*.seal'))
        original = path.read_bytes()
        self.assertNotIn(b'Synthetic native lifecycle', original)
        changed = bytearray(original); changed[-1] ^= 1
        path.write_bytes(changed)
        with self.assertRaisesRegex(AccessDenied, 'authentication'):
            self.store.load(self.project.id)

    def test_nested_transaction_excludes_second_client(self):
        second = LocalVault(self.state, windows_validation=True)
        self.addCleanup(second.close)
        with self.vault.transaction():
            self.vault.put('synthetic-record', {'value':1})
            self.assertEqual(self.vault.get('synthetic-record'), {'value':1})
            # Native object-name collision is deliberately exposed for host inspection.
            with self.assertRaisesRegex(OSError, 'NTSTATUS 0xC0000035'):
                second.put('synthetic-record', {'value':2})
        second.put('synthetic-record', {'value':2})
        self.assertEqual(self.vault.get('synthetic-record'), {'value':2})

    def test_account_backup_authentication_empty_restore_and_no_overwrite(self):
        backup = self.vault.backup()
        self.assertNotIn(b'vault.key', backup)
        with self.assertRaises(AccessDenied): self.vault.restore(backup)
        with self.assertRaises(AccessDenied): self.other_vault('other').restore(backup)
        self.store.delete(self.project.id)
        self.vault.restore(backup)
        self.assertEqual(self.store.load(self.project.id)['project']['name'], 'Synthetic native lifecycle')
        with self.assertRaises(AccessDenied): self.vault.restore(backup)

    def test_password_recovery_new_vault_tamper_wrong_password_and_replay(self):
        password = 'Synthetic test password only'
        archive = self.vault.recovery_backup(password)
        target = self.other_vault('recovery')
        self.assertNotEqual(self.vault.key_id, target.key_id)
        for data, secret in ((archive,'Incorrect synthetic password'), (archive[:-1]+bytes([archive[-1]^1]),password)):
            with self.assertRaises(AccessDenied): target.restore_recovery(data,secret)
            self.assertEqual(ProjectStore(target).listing(),[])
        target.restore_recovery(archive,password)
        self.assertEqual(ProjectStore(target,clock=lambda:self.now[0]).load(self.project.id)['project']['name'], 'Synthetic native lifecycle')
        with self.assertRaises(AccessDenied): target.restore_recovery(archive,password)

    def test_backup_excludes_trust_and_disables_restored_schedules(self):
        self.vault.put('trust-anchor', {'synthetic':True})
        self.vault.put('active-policy', {'synthetic':True})
        self.vault.put('schedules', {'format':1,'items':{'synthetic':{'enabled':True,'state':'ready'}}})
        backup = self.vault.backup()
        for marker in (b'vault.key',b'trust-anchor',b'active-policy'): self.assertNotIn(marker,backup)
        self.store.delete(self.project.id); self.vault.delete('schedules')
        self.vault.restore(backup)
        self.assertEqual(self.vault.get('schedules')['items']['synthetic'],{'enabled':False,'state':'unknown'})
        self.assertEqual(self.vault.get('trust-anchor'),{'synthetic':True})

    def test_expiry_and_prune_preserve_original_references_and_exports(self):
        reference = self.root/'reference.txt'; reference.write_bytes(b'SYNTHETIC REFERENCE')
        export = self.root/'approved.txt'; export.write_bytes(b'SYNTHETIC APPROVED COPY')
        self.now[0] += 86401
        with self.assertRaisesRegex(AccessDenied,'retention expired'): self.store.load(self.project.id)
        self.assertEqual(self.store.prune(),[self.project.id])
        self.assertEqual(self.store.listing(),[])
        self.assertEqual(reference.read_bytes(),b'SYNTHETIC REFERENCE')
        self.assertEqual(export.read_bytes(),b'SYNTHETIC APPROVED COPY')