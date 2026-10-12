import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption
from local_ai_appliance.asset_integrity import INFERENCE_LOCK_SHA256
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.model_management import DEFAULT,GPU_DEFAULT,Hardware,ModelManager,preparation_default,validate_model_policy
from local_ai_appliance.project_store import LocalVault
from local_ai_appliance.signed_policy import sign_document,verify_document

@unittest.skipUnless(os.name=='posix','Portable policy fixture; native private storage has separate tests')
class ModelManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();state=self.root/'state';state.mkdir(mode=0o700)
        self.vault=LocalVault(state);self.addCleanup(self.vault.close)
        self.now=[1000];self.manager=ModelManager(self.root,self.vault,clock=lambda:self.now[0])
        key=Ed25519PrivateKey.generate()
        self.private=key.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption())
        self.public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        self.sha=hashlib.sha256(self.public).hexdigest()
        self.manager.policy.enroll(self.public,self.sha,development=True)
        self.data=b'GGUF inert synthetic fixture, never execute'
        self.source=self.root/'original.gguf';self.source.write_bytes(self.data)
        self.profile={'id':'synthetic-model','status':'evaluation_allowed',
            'model':{'name':'fixture.gguf','size':len(self.data),'sha256':hashlib.sha256(self.data).hexdigest()},
            'publishers':['synthetic-publisher'],'jurisdictions':['unknown'],
            'data_scopes':['public','synthetic'],'workloads':['documents'],'harness':'silo-langgraph-1',
            'runtime_lock_sha256':INFERENCE_LOCK_SHA256,'interpreter':'3.14.8','gpu_layers':53,
            'minimum_ram_mib':32768,'minimum_vram_mib':24576,
            'license':{'id':'fixture-only','source':'https://example.invalid/fixture','redistribution':'pending'}}
        self.policy={'format':1,'sequence':1,'expires':2000,'profiles':[self.profile],
                     'blocked_publishers':[],'blocked_jurisdictions':[]}

    def update(self,value=None):
        return self.manager.policy.update(sign_document(value or self.policy,self.private),validate_model_policy,development=True)

    def test_exact_signed_policy_import_selection_then_model_drift(self):
        self.update();destination=self.manager.import_model('synthetic-model',self.source)
        self.assertEqual(destination.read_bytes(),self.data)
        self.manager.select('synthetic-model');self.assertEqual(self.manager.selected(),'synthetic-model')
        destination.write_bytes(self.data+b'changed')
        with self.assertRaises((AccessDenied,RuntimeError)):self.manager.select('synthetic-model')

    def installed_default(self, identifier=GPU_DEFAULT):
        config={'format_version':1,'evaluation_only':True,'state_root':str(self.root/'state'),
                'worker':'../worker','qualification':'evaluation_only_full_isolation_and_CUI_acceptance_pending'}
        if identifier is not None:config['default_model_id']=identifier
        (self.root/'evaluation-installation.json').write_text(json.dumps(config))

    def test_first_installed_default_is_policy_checked_and_persisted(self):
        self.profile['id']=GPU_DEFAULT;self.update();self.installed_default()
        self.assertEqual(self.manager.selected(),GPU_DEFAULT)
        self.assertEqual(self.vault.get('selected-model'),{'id':GPU_DEFAULT})
        self.installed_default(DEFAULT)
        self.assertEqual(self.manager.selected(),GPU_DEFAULT)

    def test_saved_selection_and_explicit_no_model_override_installation_hint(self):
        self.installed_default()
        for identifier in ('synthetic-model',None):
            self.vault.put('selected-model',{'id':identifier})
            self.assertEqual(self.manager.selected(),identifier)

    def test_legacy_install_and_source_keep_implicit_nano(self):
        self.assertEqual(self.manager.selected(),DEFAULT)
        self.installed_default(None)
        self.assertEqual(self.manager.selected(),DEFAULT)
        self.assertIsNone(self.vault.get('selected-model'))

    def test_unapproved_installed_default_cannot_create_selection_or_fallback(self):
        self.update();self.installed_default()
        with self.assertRaises(AccessDenied):self.manager.selected()
        self.assertIsNone(self.vault.get('selected-model'))

    def test_hardware_default_requires_first_gpu_ram_and_native_x64(self):
        root=Path(__file__).resolve().parents[1]
        for ram,gpus,platform,architecture,expected in [
            (32768,(24576,),'win32','amd64',GPU_DEFAULT),
            (65536,(24564,),'win32','x86_64',GPU_DEFAULT),
            (131072,(98304,),'win32','amd64',GPU_DEFAULT),
            (32767,(24576,),'win32','amd64','gemma4-12b-q4-evaluation-1'),
            (65536,(24447,),'win32','amd64','gpt-oss-20b-mxfp4-evaluation-1'),
            (65536,(12288,24576),'win32','amd64','gemma4-12b-q4-evaluation-1'),
            (65536,(),'win32','amd64','gemma4-e4b-q4-cpu-evaluation-1'),
            (None,(24576,),'win32','amd64',None),
            (65536,(24576,),'darwin','arm64',None),
            (65536,(24576,),'win32','arm64',None)]:
            with self.subTest(ram=ram,gpus=gpus,platform=platform,architecture=architecture):
                hardware=Hardware(ram,8,tuple({'name':'fixture','vram_mib':v} for v in gpus),platform,architecture)
                self.assertEqual(preparation_default(root,hardware),expected)

    def test_unknown_revoked_and_prohibited_models_denied(self):
        self.update()
        with self.assertRaises(AccessDenied):self.manager.authorize('unknown',operation='install')
        for change in ['revoked','publisher','jurisdiction','license']:
            with self.subTest(change=change):
                value=json.loads(json.dumps(self.policy));value['sequence']=self.manager.policy.current(validate_model_policy)['sequence']+1
                if change=='revoked':value['profiles'][0]['status']='revoked'
                if change=='publisher':value['blocked_publishers']=['synthetic-publisher']
                if change=='jurisdiction':value['blocked_jurisdictions']=['unknown']
                if change=='license':value['profiles'][0]['license']['redistribution']='prohibited'
                self.update(value)
                for operation in ['install','launch']:
                    with self.assertRaises(AccessDenied):self.manager.authorize('synthetic-model',operation=operation)

    def test_signature_key_substitution_tamper_and_replay_denied(self):
        envelope=sign_document(self.policy,self.private)
        for bad_key,bad_sha,data in [(self.public,'0'*64,envelope),(b'x'*32,hashlib.sha256(b'x'*32).hexdigest(),envelope),
                                    (self.public,self.sha,envelope.replace(b'2000',b'2001'))]:
            with self.assertRaises(AccessDenied):verify_document(data,bad_key,bad_sha)
        self.update()
        with self.assertRaisesRegex(AccessDenied,'rollback'):self.update()
        with self.assertRaises(AccessDenied):self.manager.policy.enroll(self.public,self.sha,development=True)

    def test_required_independent_anchor_and_missing_enrolled_policy_deny_fallback(self):
        with self.assertRaisesRegex(AccessDenied,'missing'):
            self.manager.profiles()
        self.update()
        required=ModelManager(self.root,self.vault,clock=lambda:self.now[0],required_key_sha256=self.sha)
        self.assertEqual(required.profiles()[0]['id'],'synthetic-model')
        self.vault.delete('active-policy')
        with self.assertRaises(AccessDenied):required.profiles()
        self.vault.delete('trust-anchor')
        with self.assertRaises(AccessDenied):required.profiles()

    def test_expired_policy_no_fallback_to_embedded_catalog(self):
        self.update();self.now[0]=2001
        with self.assertRaisesRegex(AccessDenied,'expired'):self.manager.profiles()
        with self.assertRaisesRegex(AccessDenied,'expired'):
            self.manager.recommendations(Hardware(65536,8,(),'win32','amd64'))

    def test_recommendations_use_signed_policy_and_active_project_scope(self):
        self.profile['data_scopes']=['synthetic']; self.update()
        hw=Hardware(65536,8,({'name':'Inert GPU','vram_mib':24576},),'win32','amd64')
        self.assertEqual(self.manager.recommendations(hw,data_scope='public'),[])
        self.assertTrue(self.manager.recommendations(hw,data_scope='synthetic')[0]['recommended'])
        self.assertIsNone(self.vault.get('selected-model'))
        self.profile['status']='revoked';self.policy['sequence']+=1;self.update()
        self.assertEqual(self.manager.recommendations(hw),[])

    def test_scope_harness_interpreter_and_model_paths_cannot_expand_authority(self):
        for key,value in [('data_scopes',['cui']),('harness','shell'),('interpreter','3.12.14'),
                          ('workloads',['code']),('gpu_layers',True),('runtime_lock_sha256','0'*64)]:
            bad=json.loads(json.dumps(self.policy));bad['profiles'][0][key]=value
            with self.assertRaises(AccessDenied):validate_model_policy(bad)
        bad=json.loads(json.dumps(self.policy));bad['profiles'][0]['model']['name']='../escape.gguf'
        with self.assertRaises(AccessDenied):validate_model_policy(bad)

    def test_offline_import_mismatch_symlink_and_changed_copy_denied(self):
        self.update();self.source.write_bytes(b'wrong')
        with self.assertRaises((AccessDenied,RuntimeError)):self.manager.import_model('synthetic-model',self.source)
        self.source.write_bytes(self.data);link=self.root/'link.gguf';link.symlink_to(self.source)
        with self.assertRaises((AccessDenied,RuntimeError)):self.manager.import_model('synthetic-model',link)
        with patch('local_ai_appliance.model_management.digest_file',return_value=self.profile['model']['sha256']):
            self.source.write_bytes(b'x'*len(self.data))
            with self.assertRaises((AccessDenied,RuntimeError)):self.manager.import_model('synthetic-model',self.source)
        self.assertEqual(list((self.root/'artifacts/inference/imported').glob('*.gguf')),[])

    def test_hardware_recommendation_never_claims_qualification_or_guesses_gpu(self):
        self.update()
        for hardware,expected in [(Hardware(65536,8,({'name':'Synthetic GPU','vram_mib':24576},),'win32','amd64'),True),
                                  (Hardware(65536,8,(),'win32','amd64'),False),
                                  (Hardware(None,8,({'name':'GPU','vram_mib':24576},),'win32','amd64'),False)]:
            recommendation=self.manager.recommendations(hardware)[0]
            self.assertEqual(recommendation['fits'],expected);self.assertIn('need evidence',recommendation['qualification'])

    def test_authority_not_part_of_model_tool_registry(self):
        from local_ai_appliance.agent import TOOL_SCHEMAS
        names={row['function']['name'] for row in TOOL_SCHEMAS}
        self.assertFalse(names & {'select_model','update_policy','enroll_key','import_model','approve','grant','schedule'})
