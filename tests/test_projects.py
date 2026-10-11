import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from local_ai_appliance.agent import Source
from local_ai_appliance.backend import PortableSession
from local_ai_appliance.contracts import Project,WorkspaceKind
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.model import ModelReply
from local_ai_appliance.project_store import LocalVault,ProjectStore,ProjectSession
from local_ai_appliance.workspace import Workspace

class Model:
    def complete(self,messages,tools):return ModelReply('Synthetic answer')

@unittest.skipUnless(os.name=='posix','POSIX persistence fixture')
class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.state=self.root/'private';self.state.mkdir(mode=0o700)
        self.reference=self.root/'reference';self.reference.mkdir()
        self.drafts=self.root/'drafts';self.drafts.mkdir()
        (self.reference/'a.txt').write_text('Capacity is 108 kg.\n')
        self.vault=LocalVault(self.state);self.addCleanup(self.vault.close)
        self.now=[1000.0];self.store=ProjectStore(self.vault,clock=lambda:self.now[0])
        self.backend=PortableSession(Project('temporary','Temporary'),Workspace(),Model())
        self.addCleanup(self.backend.close)
        self.session=ProjectSession(self.backend,self.store)
        self.ro=self.session.grant(self.reference,WorkspaceKind.REFERENCE)
        self.rw=self.session.grant(self.drafts,WorkspaceKind.DRAFT)

    def remember(self):
        data=(self.reference/'a.txt').read_bytes()
        source=Source('S1',self.ro.id,'a.txt',hashlib.sha256(data).hexdigest(),1,1,data.decode())
        self.session.conversation.append('Sensitive synthetic prompt','108 kg. [source:S1]',[source],self.backend.workspace.broker.revision)
        self.session.persist()

    def test_explicit_persistence_encrypted_roundtrip_with_new_folder_ids(self):
        self.assertEqual(self.store.listing(),[])
        self.session.ask('An unsaved prompt');self.assertEqual(self.store.listing(),[])
        project=self.session.create_project('Capacity study');self.remember()
        proposal=self.backend.workspace.propose(self.rw.id,'unsaved.txt','unsaved')
        blobs=b''.join(p.read_bytes() for p in self.state.glob('*.seal'))
        self.assertNotIn(b'Sensitive synthetic',blobs);self.assertNotIn(str(self.reference).encode(),blobs)
        old=self.ro.id;self.session.close_project()
        outcome=self.session.open_project(project.id)
        self.assertFalse(outcome['context_invalidated']);self.assertEqual(len(self.session.conversation.turns),1)
        source=self.session.conversation.turns[0].sources[0]
        self.assertNotEqual(source.folder_id,old)
        self.assertEqual(self.backend.workspace.open_text(source.folder_id,'a.txt').text,'Capacity is 108 kg.\n')
        self.assertEqual(self.backend.workspace.pending_proposals(),())
        with self.assertRaises(AccessDenied):self.backend.approve(proposal.id)

    def test_nested_transactions_exclude_other_vault_clients(self):
        second=LocalVault(self.state)
        try:
            with self.vault.transaction():
                self.vault.put('synthetic-record',{'value':1})
                self.assertEqual(self.vault.get('synthetic-record')['value'],1)
                with self.assertRaises(FileExistsError):second.put('synthetic-record',{'value':2})
            self.assertEqual(second.get('synthetic-record')['value'],1)
            second.put('synthetic-record',{'value':2})
            self.assertEqual(self.vault.get('synthetic-record')['value'],2)
        finally:second.close()

    def test_changed_source_clears_history_on_reopen_and_before_next_request(self):
        project=self.session.create_project('Changed');self.remember();self.session.close_project()
        (self.reference/'a.txt').write_text('Changed source')
        self.assertTrue(self.session.open_project(project.id)['context_invalidated'])
        self.assertFalse(self.session.conversation.turns)
        self.ro=next(f for f in self.session.workspace.broker.folders() if f.access=='read-only')
        self.remember();(self.reference/'a.txt').write_text('Changed again')
        self.session.persist();self.assertFalse(self.store.load(project.id)['turns'])

    def test_replaced_folder_identity_not_regranted(self):
        project=self.session.create_project('Replaced');self.remember();self.session.close_project()
        self.reference.rename(self.root/'old-reference');self.reference.mkdir()
        (self.reference/'a.txt').write_text('Capacity is 108 kg.\n')
        result=self.session.open_project(project.id)
        self.assertTrue(result['context_invalidated']);self.assertFalse(self.session.conversation.turns)
        self.assertEqual(len(self.session.workspace.broker.folders()),1)

    def test_revoke_clears_saved_context_and_updates_saved_grants(self):
        project=self.session.create_project('Revoked');self.remember();self.session.revoke(self.ro.id)
        saved=self.store.load(project.id)
        self.assertEqual(saved['turns'],[]);self.assertEqual(len(saved['grants']),1)
        self.assertEqual(saved['grants'][0]['access'],'editable')

    def test_instructions_bound_and_clear_context_without_expanding_tools(self):
        project=self.session.create_project('Instructions');self.remember()
        self.session.set_instructions('Answer concisely.')
        self.assertIn('Answer concisely.',self.backend.harness.instructions)
        self.assertEqual(self.store.load(project.id)['turns'],[])
        with self.assertRaises(AccessDenied):self.session.set_instructions('x'*8193)

    def test_retention_expiry_delete_and_user_files_preserved(self):
        project=self.session.create_project('Expired',retention_days=1)
        self.session.close_project();self.now[0]+=86401
        with self.assertRaises(AccessDenied):self.store.load(project.id)
        self.assertTrue(self.store.listing()[0]['expired'])
        self.assertEqual(self.store.prune(),[project.id])
        self.assertEqual(self.store.listing(),[])
        self.assertTrue((self.reference/'a.txt').exists())

    def test_tamper_ciphertext_and_relocate_record_denied(self):
        project=self.session.create_project('Authenticated');self.remember()
        path=next(self.state.glob('project-*.seal'));data=bytearray(path.read_bytes());data[-1]^=1;path.write_bytes(data)
        with self.assertRaisesRegex(AccessDenied,'authentication'):self.store.load(project.id)

    def test_backup_authentication_same_key_empty_restore_no_overwrite(self):
        project=self.session.create_project('Backup');self.remember();backup=self.vault.backup()
        self.assertNotIn(b'vault.key',backup)
        with self.assertRaises(AccessDenied):self.vault.restore(backup)
        for name in ['project-'+project.id,'active-project']:self.vault.delete(name)
        self.vault.restore(backup);self.assertEqual(self.store.load(project.id)['project']['name'],'Backup')
        other=self.root/'other';other.mkdir(mode=0o700)
        with_key=LocalVault(other)
        try:
            with self.assertRaises(AccessDenied):with_key.restore(backup)
        finally:with_key.close()

    def test_portable_recovery_reseals_under_new_key_and_rejects_password_tamper(self):
        project=self.session.create_project('Portable recovery');self.remember()
        archive=self.vault.recovery_backup('Synthetic recovery password only')
        self.assertNotIn(self.vault._key,archive)
        other=self.root/'recovery-state';other.mkdir(mode=0o700)
        vault=LocalVault(other)
        try:
            self.assertNotEqual(vault.key_id,self.vault.key_id)
            for bad,password in [(archive,'Wrong password long enough'),(archive[:-1]+bytes([archive[-1]^1]),'Synthetic recovery password only')]:
                with self.assertRaises(AccessDenied):vault.restore_recovery(bad,password)
                self.assertEqual(ProjectStore(vault).listing(),[])
            vault.restore_recovery(archive,'Synthetic recovery password only')
            self.assertEqual(ProjectStore(vault,clock=lambda:self.now[0]).load(project.id)['project']['name'],'Portable recovery')
            with self.assertRaises(AccessDenied):vault.restore_recovery(archive,'Synthetic recovery password only')
        finally:vault.close()

    def test_project_backup_excludes_policy_keys_and_disables_restored_schedules(self):
        self.session.create_project('Safe backup')
        self.vault.put('trust-anchor',{'sha256':'not a real anchor'})
        self.vault.put('active-policy',{'sequence':1})
        self.vault.put('schedules',{'format':1,'items':{'fixture':{'enabled':True,'state':'ready'}}})
        archive=self.vault.backup();self.assertNotIn(b'trust-anchor',archive);self.assertNotIn(b'active-policy',archive)
        for name in self.vault.names('project-')+['active-project','schedules']:self.vault.delete(name)
        self.vault.restore(archive)
        self.assertEqual(self.vault.get('schedules')['items']['fixture'],{'enabled':False,'state':'unknown'})

    def test_state_links_and_non_private_directory_denied(self):
        loose=self.root/'loose';loose.mkdir(mode=0o755)
        with self.assertRaises(Exception):LocalVault(loose)
        linked=self.root/'linked';linked.symlink_to(self.state,target_is_directory=True)
        with self.assertRaises(Exception):LocalVault(linked)

    def test_expired_active_project_prune_does_not_refresh_retention(self):
        project=self.session.create_project('Expired active',retention_days=1)
        self.now[0]+=86401;self.session.close_project()
        self.assertEqual(self.store.prune(),[project.id])

    def test_private_storage_and_ancestors_cannot_be_model_grants(self):
        for path in (self.state,self.root):
            with self.assertRaisesRegex(AccessDenied,'private storage'):
                self.session.grant(path,WorkspaceKind.REFERENCE)

    def test_project_delete_closes_current_grants_and_retained_context(self):
        project=self.session.create_project('Delete');self.remember();self.session.delete_project(project.id)
        self.assertIsNone(self.session.record);self.assertFalse(self.session.workspace.broker.folders())
        self.assertFalse(self.session.conversation.turns);self.assertFalse(self.store.listing())
