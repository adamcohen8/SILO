"""Adversarial portable contracts. None of these certify native containment."""
import base64
import copy
import ctypes
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from unittest.mock import Mock
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption

from local_ai_appliance.data_security import document_destination,StoragePolicy,SecurityBroker,ACTIVE_TYPES
from local_ai_appliance.folders import AccessDenied,FolderBroker
from local_ai_appliance.machine_security import MachineStore,enroll_anchor,technical_receipt,TECHNICAL_CHECKS
from local_ai_appliance.managed_deployment import ManagedDeployment,deployment_settings
from local_ai_appliance.model import json_bytes
from local_ai_appliance.model_management import builtin_profiles,validate_model_policy,ModelManager
from local_ai_appliance.project_store import LocalVault,ProjectStore
from local_ai_appliance.release_readiness import signed_bundle,inventory
from local_ai_appliance.security_events import SecurityAudit
from local_ai_appliance.security_maintenance import sbom,scan_advisories
from local_ai_appliance.signed_policy import SignedPolicyStore,sign_document,canonical
from local_ai_appliance.windows_code_runner import RunnerContainer
from local_ai_appliance.windows_container import AppContainer
from local_ai_appliance.windows_crypto import WindowsAESGCM,recovery_key,AuthInfo
from local_ai_appliance.workspace import Workspace

ROOT=Path(__file__).resolve().parents[1]


def keys():
    key=Ed25519PrivateKey.generate()
    private=key.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption())
    public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    return private,public,hashlib.sha256(public).hexdigest()


@unittest.skipUnless(os.name=='posix','Portable security fixtures; Windows has separately labeled acceptance tests')
class SecurityContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        for name in ('machine','projects','references','drafts','excluded'):(self.root/name).mkdir(mode=0o700)
        self.machine=MachineStore(self.root/'machine',development=True,writable=True);self.addCleanup(self.machine.close)
        self.reader=MachineStore(self.root/'machine',development=True);self.addCleanup(self.reader.close)
        self.private,self.public,self.sha=keys()
        for name in ('trust-anchor','release-anchor','reviewer-anchor'):enroll_anchor(self.machine,name,self.public,self.sha)
        self.records=[];self.audit=SecurityAudit(self.records.append)
        self.storage=StoragePolicy([self.root/'references'],[self.root/'drafts'],excluded_roots=[self.root/'excluded'])

    def test_user_project_key_cannot_rewrite_machine_policy_or_anchor(self):
        policy=SignedPolicyStore(self.machine,clock=lambda:1000)
        original={'format':1,'sequence':1,'expires':2000,'profiles':builtin_profiles(ROOT),
                  'blocked_publishers':[],'blocked_jurisdictions':[]}
        policy.update(sign_document(original,self.private),validate_model_policy,development=True)
        old=self.reader.get('active-policy')
        revoked=copy.deepcopy(original);revoked['sequence']=2
        for profile in revoked['profiles']:profile['status']='revoked'
        policy.update(sign_document(revoked,self.private),validate_model_policy,development=True)
        for name,value in [('active-policy',old),('trust-anchor',{'key':'forged'}),('deployment',{})]:
            with self.assertRaises(AccessDenied):self.reader.put(name,value)
        vault=LocalVault(self.root/'projects');self.addCleanup(vault.close)
        vault.put('active-policy',old);vault.put('trust-anchor',{'key':'forged'})
        manager=ModelManager(ROOT,vault,policy_store=self.reader,clock=lambda:1000,required_key_sha256=self.sha)
        with self.assertRaises(AccessDenied):manager.authorize(original['profiles'][0]['id'])
        self.assertEqual(manager.policy.current(validate_model_policy)['sequence'],2)

    def test_signed_policy_replay_and_missing_policy_cannot_enable_fallback(self):
        policy=SignedPolicyStore(self.machine,clock=lambda:1000)
        value={'format':1,'sequence':1,'expires':2000,'profiles':builtin_profiles(ROOT),
               'blocked_publishers':[],'blocked_jurisdictions':[]}
        data=sign_document(value,self.private)
        policy.update(data,validate_model_policy,development=True)
        with self.assertRaises(AccessDenied):policy.update(data,validate_model_policy,development=True)
        self.assertEqual(SignedPolicyStore(self.reader,clock=lambda:1000).current(validate_model_policy)['sequence'],1)

    def test_native_policy_rejects_user_vault_even_if_update_command_would_elevate(self):
        vault=LocalVault(self.root/'projects');self.addCleanup(vault.close)
        with patch('os.name','nt'):
            with self.assertRaises(AccessDenied):SignedPolicyStore(vault)

    def test_all_active_output_types_are_rejected_before_review_or_save(self):
        workspace=Workspace();self.addCleanup(workspace.close)
        folder=workspace.grant(self.root/'drafts','editable')
        for suffix in (*ACTIVE_TYPES,'.unknown',''):
            with self.subTest(suffix=suffix),self.assertRaises(AccessDenied):
                workspace.propose(folder.id,'synthetic'+suffix,'inert synthetic fixture')
        self.assertEqual(list((self.root/'drafts').iterdir()),[])
        proposal=workspace.propose(folder.id,'safe.md','Synthetic report')
        workspace.approve(proposal.id)
        self.assertEqual((self.root/'drafts'/'safe.md').read_text(),'Synthetic report')

    def test_bidi_and_alternate_stream_destinations_denied(self):
        for path in ('report\u202ecmd.txt','report.txt:payload','../report.md','C:/report.md'):
            with self.assertRaises(AccessDenied):document_destination(path)

    def test_granted_storage_rejects_exclusions_outside_roots_and_links(self):
        broker=SecurityBroker(FolderBroker(),self.storage,self.audit);self.addCleanup(broker.close)
        for path in (self.root,self.root/'excluded',self.root/'projects'):
            with self.assertRaises(AccessDenied):broker.grant(path,'editable')
        link=self.root/'drafts'/'linked';link.symlink_to(self.root/'references',target_is_directory=True)
        with self.assertRaises(RuntimeError):broker.grant(link,'editable')
        self.assertEqual(broker.folders(),[])
        self.assertTrue(any(json.loads(r)['outcome']=='denied' for r in self.records))

    def test_read_only_cannot_be_promoted_by_draft_root_or_file_tool(self):
        broker=SecurityBroker(FolderBroker(),self.storage,self.audit);self.addCleanup(broker.close)
        folder=broker.grant(self.root/'references','read-only')
        with self.assertRaises(AccessDenied):broker.write_file(folder.id,'report.md',b'synthetic')
        with self.assertRaises(AccessDenied):broker.grant(self.root/'references','editable')

    def test_audit_omits_content_paths_and_validates_metadata(self):
        path=self.root/'references'/'sensitive-name.txt';path.write_text('sensitive synthetic text')
        broker=SecurityBroker(FolderBroker(),self.storage,self.audit);self.addCleanup(broker.close)
        folder=broker.grant(path.parent,'read-only');self.assertEqual(broker.read_file(folder.id,path.name),path.read_bytes())
        logs=b'\n'.join(self.records)
        self.assertNotIn(str(path).encode(),logs);self.assertNotIn(path.read_bytes(),logs)
        for kwargs in ({'prompt':'secret'},{'object_sha256':'bad'},{'bytes':True}):
            with self.assertRaises(AccessDenied):self.audit.emit('read','success',**kwargs)
        decoded=[json.loads(r) for r in self.records]
        self.assertEqual([r['sequence'] for r in decoded],list(range(1,len(decoded)+1)))

    def test_audit_failure_prevents_reads_and_writes_and_is_sticky(self):
        underlying=FolderBroker();self.addCleanup(underlying.close)
        folder=underlying.grant(self.root/'drafts','editable')
        def unavailable(data):raise OSError('synthetic log failure')
        audit=SecurityAudit(unavailable);broker=SecurityBroker(underlying,self.storage,audit)
        with self.assertRaises(AccessDenied):broker.write_file(folder.id,'report.md',b'synthetic')
        self.assertEqual(list((self.root/'drafts').iterdir()),[])
        audit.sink=self.records.append
        with self.assertRaises(AccessDenied):broker.read_file(folder.id,'report.md')

    def test_code_export_policy_is_distinct_from_document_publication(self):
        underlying=FolderBroker();self.addCleanup(underlying.close)
        broker=SecurityBroker(underlying,self.storage,self.audit)
        folder=broker.grant(self.root/'drafts','editable')
        with self.assertRaises(AccessDenied):broker.validate_create(folder.id,'outputs.zip')
        self.storage.allow_code_exports=True
        broker.validate_create(folder.id,'outputs.zip')
        with self.assertRaises(AccessDenied):broker.write_file(folder.id,'escape.cmd',b'inert')

    def test_backup_destination_policy_rejects_outside_root_and_non_archive(self):
        self.storage.backup(self.root/'drafts'/'backup.silo')
        for path in (self.root/'references'/'backup.silo',self.root/'excluded'/'backup.silo',self.root/'drafts'/'backup.txt'):
            with self.assertRaises(AccessDenied):self.storage.backup(path)

    def test_retention_cannot_exceed_administrator_limit(self):
        vault=LocalVault(self.root/'projects');self.addCleanup(vault.close)
        store=ProjectStore(vault,maximum_retention_days=7,audit=self.audit)
        project=store.create('Synthetic')
        self.assertEqual(store.load(project.id)['retention_days'],7)
        with self.assertRaises(AccessDenied):store.create('Over limit',retention_days=8)
        with self.assertRaises(AccessDenied):store.renew(project.id,8)
        record=store.load(project.id);record['retention_days']=365
        with self.assertRaises(AccessDenied):store.save(record)

    def test_existing_project_over_new_limit_can_be_renewed_or_deleted(self):
        vault=LocalVault(self.root/'projects');self.addCleanup(vault.close)
        old=ProjectStore(vault,clock=lambda:1000)
        project=old.create('Synthetic',retention_days=30)
        restricted=ProjectStore(vault,clock=lambda:1000+8*86400,maximum_retention_days=7)
        with self.assertRaises(AccessDenied):restricted.load(project.id)
        self.assertTrue(restricted.listing()[0]['expired'])
        restricted.renew(project.id,7)
        restricted.delete(project.id)
        self.assertEqual(restricted.listing(),[])

    def test_legacy_recovery_migration_authenticates_and_preserves_old_archive(self):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
        vault=LocalVault(self.root/'projects');self.addCleanup(vault.close)
        project=ProjectStore(vault).create('Synthetic')
        password='Synthetic recovery fixture only';salt=bytes(range(16));nonce=bytes(range(12))
        clear=json_bytes({'key':base64.b64encode(vault._key).decode(),'backup':json.loads(vault.backup())})
        header=b'SILOR1'+salt
        cipher=AESGCM(Scrypt(salt=salt,length=32,n=2**16,r=8,p=1).derive(password.encode()))
        archive=header+nonce+cipher.encrypt(nonce,clear,header)
        migrated=LocalVault.migrate_legacy_recovery(archive,password)
        self.assertEqual(archive[:6],b'SILOR1');self.assertEqual(migrated[:6],b'SILOR2')
        with self.assertRaises(AccessDenied):LocalVault.migrate_legacy_recovery(archive,'Wrong fixture password')
        vault.delete('project-'+project.id)
        vault.restore_recovery(migrated,password)
        self.assertEqual(ProjectStore(vault).load(project.id)['project']['name'],'Synthetic')

    def test_ocr_container_exposes_required_lpac_prepare_method(self):
        self.assertTrue(RunnerContainer.lpac)
        self.assertTrue(callable(RunnerContainer.prepare_process))
        if os.name!='nt':
            with self.assertRaises(RuntimeError):RunnerContainer()

    def test_managed_software_read_does_not_request_acl_write_or_mutate_runtime(self):
        container=object.__new__(AppContainer)
        container.kernel=Mock();container.kernel.CreateFileW.return_value=11
        container.managed_read_handles=[];container._acl=Mock()
        info=SimpleNamespace(disk=True,reparse=False,offline=False,directory=True,links=1)
        with patch('local_ai_appliance.windows_native.NativeFiles') as native, \
             patch('local_ai_appliance.machine_security.protected_acl') as acl:
            native.return_value.info.return_value=info
            container.allow_managed_read(self.root/'references',directory=True)
        self.assertEqual(container.kernel.CreateFileW.call_args.args[1],0x80000000)
        container._acl.assert_not_called()
        acl.assert_called_once_with(11,file=False,runtime=True)
        self.assertEqual(container.managed_read_handles,[11])

    def test_native_crypto_requires_windows_and_auth_info_has_windows_abi_layout(self):
        with self.assertRaises(AccessDenied):WindowsAESGCM(bytes(32))
        self.assertEqual(ctypes.sizeof(AuthInfo),88)
        self.assertEqual(AuthInfo.data_total.offset,72)


class LifecycleFixture:
    def __init__(self):self.changed=False;self.closed=False
    def check(self):
        if self.changed:raise AccessDenied('synthetic route/resume change')
    def close(self):self.closed=True


@unittest.skipUnless(os.name=='posix','Portable managed-deployment contracts only')
class ManagedDeploymentContracts(unittest.TestCase):
    def setUp(self):
        SecurityContracts.setUp(self)
        self.release=self.root/'release';self.app=self.release/'payload'/'app';self.app.mkdir(parents=True)
        (self.app/'source.txt').write_text('Inert signed application fixture')
        self.envelope=signed_bundle(self.release/'payload',version='1.0.0',configuration_id='synthetic',private_key=self.private)
        self.digest=hashlib.sha256(self.envelope).hexdigest()
        model_policy={'format':1,'sequence':1,'expires':time.time()+3600,'profiles':builtin_profiles(ROOT),
                      'blocked_publishers':[],'blocked_jurisdictions':[]}
        SignedPolicyStore(self.machine).update(sign_document(model_policy,self.private),validate_model_policy,development=True)
        self.technical={'format':1,'release_sha256':self.digest,'native_version':'synthetic-os','boundary':'silo-lpac-managed-2',
            'expires':time.time()+3600,'checks':{name:{'status':'pass','evidence_sha256':'a'*64} for name in TECHNICAL_CHECKS}}
        self.record={'format':1,'release_root':str(self.release),'release_envelope':base64.b64encode(self.envelope).decode(),
            'release_sha256':self.digest,'technical_receipt':base64.b64encode(sign_document(self.technical,self.private)).decode(),
            'settings':{'reference_roots':[str(self.root/'references')],'draft_roots':[str(self.root/'drafts')],
                'excluded_roots':[str(self.root/'excluded')],'allow_code':False,'allow_code_exports':False,
                'allow_ocr':False,'allow_schedules':False,'maximum_retention_days':30}}
        bom=sbom(self.release/'payload',inventory(self.release/'payload'))
        self.advisories={'format':1,'sequence':1,'expires':time.time()+3600,'coverage':[],'advisories':[]}
        self.machine.put('advisory-snapshot',{'sequence':1,'envelope':base64.b64encode(sign_document(self.advisories,self.private)).decode()})
        self.maintenance={'format':1,'sequence':1,'expires':time.time()+3600,'release_sha256':self.digest,
            'sbom_sha256':hashlib.sha256(canonical(bom)).hexdigest(),'advisory_snapshot_sha256':hashlib.sha256(canonical(self.advisories)).hexdigest(),
            'status':'accepted','native_components_reviewed':True}
        self.machine.put('maintenance-review',{'sequence':1,'envelope':base64.b64encode(sign_document(self.maintenance,self.private)).decode()})
        self.machine.put('deployment',self.record)
        self.lifecycle=LifecycleFixture()

    def managed(self):
        value=ManagedDeployment(self.app,store=self.reader,audit=self.audit,lifecycle=self.lifecycle,native_version='synthetic-os')
        self.addCleanup(value.close);return value

    def test_valid_protected_signature_and_receipts_allow_only_the_exact_app(self):
        self.managed().check()
        with self.assertRaises(AccessDenied):ManagedDeployment(self.root,store=self.reader,audit=self.audit,lifecycle=self.lifecycle,native_version='synthetic-os')

    def test_mutated_payload_with_self_consistent_adjacent_digest_is_rejected(self):
        (self.app/'source.txt').write_text('Changed fixture')
        (self.release/'release-manifest.sha256').write_text('caller-chosen hash')
        with self.assertRaises(RuntimeError):self.managed()

    def test_unsigned_and_wrong_review_key_cannot_supply_technical_evidence(self):
        for data in (json_bytes(self.technical),sign_document(self.technical,keys()[0])):
            with self.assertRaises(AccessDenied):technical_receipt(data,self.reader,release_sha256=self.digest,native_version='synthetic-os')

    def test_skipped_missing_changed_os_and_expired_receipts_block_startup(self):
        for mutation in ('skip','missing','os','expiry'):
            value=copy.deepcopy(self.technical)
            if mutation=='skip':value['checks']['network_ipv6']['status']='skip'
            elif mutation=='missing':del value['checks']['network_udp']
            elif mutation=='os':value['native_version']='other-os'
            else:value['expires']=1
            with self.assertRaises(AccessDenied):technical_receipt(sign_document(value,self.private),self.reader,
                release_sha256=self.digest,native_version='synthetic-os')

    def test_route_resume_or_policy_change_invalidates_active_session(self):
        security=self.managed();self.lifecycle.changed=True
        with self.assertRaises(AccessDenied):security.check()
        self.assertTrue(security.failed.is_set())
        self.lifecycle.changed=False
        with self.assertRaises(AccessDenied):security.check()

    def test_admin_revocation_is_seen_without_waiting_for_another_model_request(self):
        security=self.managed();self.machine.put('revoked-releases',[self.digest])
        with self.assertRaises(AccessDenied):security.check()

    def test_advisory_snapshot_missing_expired_or_changed_cannot_use_review(self):
        for mutation in ('missing','expired','changed'):
            with self.subTest(mutation=mutation):
                value=copy.deepcopy(self.advisories)
                if mutation=='expired':value['expires']=1
                elif mutation=='changed':value['coverage']=['synthetic-extra-package']
                self.machine.put('advisory-snapshot',None if mutation=='missing' else
                    {'sequence':1,'envelope':base64.b64encode(sign_document(value,self.private)).decode()})
                with self.assertRaises(AccessDenied):self.managed()

    def test_settings_cannot_silently_enable_features_or_omit_exclusions(self):
        for field,value in [('allow_code','true'),('excluded_roots',[]),('maximum_retention_days',True),('allow_code_exports',True)]:
            changed=copy.deepcopy(self.record['settings']);changed[field]=value
            with self.assertRaises(AccessDenied):deployment_settings(changed)


class AdvisoryContracts(unittest.TestCase):
    def test_exact_version_scan_covers_both_worker_and_host_versions(self):
        bom={'components':[{'type':'library','name':'example','version':'1.0'},
                           {'type':'library','name':'example','version':'2.0'}]}
        snapshot={'format':1,'sequence':1,'expires':2000,'coverage':['example'],
            'advisories':[{'id':'SYNTHETIC-001','component':'example','affected_versions':['1.0'],'severity':'high'}]}
        report=scan_advisories(bom,snapshot,clock=lambda:1000)
        self.assertEqual(report['findings'][0]['version'],'1.0')
        self.assertTrue(report['coverage_complete'])
        snapshot['coverage']=[]
        self.assertFalse(scan_advisories(bom,snapshot,clock=lambda:1000)['coverage_complete'])
        snapshot['expires']=1000
        with self.assertRaises(AccessDenied):scan_advisories(bom,snapshot,clock=lambda:1000)

    def test_sbom_reads_authenticated_metadata_without_importing_packages(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();metadata=root/'host'/'Example.dist-info'/'METADATA'
            metadata.parent.mkdir(parents=True);metadata.write_bytes(b'Name: Example_Library\nVersion: 1.0\n')
            files=inventory(root);bom=sbom(root,files)
            self.assertEqual(bom['components'][0]['name'],'example-library')
            metadata.write_bytes(b'Name: Changed\nVersion: 1.0\n')
            with self.assertRaises(AccessDenied):sbom(root,files)


@unittest.skipUnless(os.name=='nt','Native CNG acceptance; never certified by portable fixtures')
class WindowsCryptoAcceptance(unittest.TestCase):
    def test_cng_matches_standard_aes_gcm_and_rejects_tampering(self):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        key,nonce,aad=bytes(range(32)),bytes(range(12)),b'synthetic record identity'
        native=WindowsAESGCM(key)
        try:
            for clear in (b'',b'synthetic public fixture'):
                expected=AESGCM(key).encrypt(nonce,clear,aad)
                self.assertEqual(native.encrypt(nonce,clear,aad),expected)
                self.assertEqual(native.decrypt(nonce,expected,aad),clear)
                with self.assertRaises(AccessDenied):native.decrypt(nonce,expected[:-1]+bytes([expected[-1]^1]),aad)
        finally:native.close()

    def test_native_recovery_derivation_matches_portable_pbkdf2(self):
        salt=bytes(range(16));password=b'synthetic password fixture only'
        self.assertEqual(recovery_key(password,salt),hashlib.pbkdf2_hmac('sha256',password,salt,600_000,32))
