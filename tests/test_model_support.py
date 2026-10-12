"""Nine-model plumbing using inert weights and synthetic server responses.

These tests do not load model weights or establish native Windows acceptance.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption

from local_ai_appliance.asset_integrity import INFERENCE_LOCK_SHA256, CPU_RUNTIME_SHA256
from local_ai_appliance.configuration_catalog import authorize_configuration
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.model import AgentError, LocalChatModel, json_bytes
from local_ai_appliance.model_adapters import ADAPTERS, model_adapter, server_command
from local_ai_appliance.model_management import BUILTIN_IDS, CPU_IDS, DEFAULT, SUPER_ID, Hardware, ModelManager, builtin_profiles, model_pins, validate_model_policy
from local_ai_appliance.project_store import LocalVault
from local_ai_appliance.signed_policy import sign_document
from local_ai_appliance.windows_model import WindowsSocketChatModel
from local_ai_appliance.windows_session import WindowsSession

from test_model import completion, fixture, tool

ROOT = Path(__file__).resolve().parents[1]


class AdapterTests(unittest.TestCase):
    def test_all_exact_profiles_with_explicit_pinned_backends(self):
        profiles = builtin_profiles(ROOT)
        self.assertEqual(len(profiles), 11)
        self.assertEqual({p['id'] for p in profiles}, BUILTIN_IDS)
        self.assertEqual(profiles[0]['adapter'], 'gemma4')
        self.assertEqual(profiles[1]['adapter'], 'muse_glimmer')
        self.assertEqual(len(profiles), 11)
        self.assertEqual({p['runtime_lock_sha256'] for p in profiles}, {INFERENCE_LOCK_SHA256, CPU_RUNTIME_SHA256})
        for profile in profiles:
            for operation in ('install', 'launch'):
                authorize_configuration(ROOT, profile['id'], operation=operation, workload='code_evaluation')
                with self.assertRaises(RuntimeError):
                    authorize_configuration(ROOT, profile['id'], operation=operation, data_scope='cui')

    def test_each_adapter_keeps_containment_context_and_omits_interactive_token_quotas(self):
        for identifier in ADAPTERS:
            with self.subTest(adapter=identifier):
                adapter = model_adapter(identifier)
                command = server_command('/runtime', '/weights/local.gguf', '/private/s.sock', '/private/key', identifier)
                self.assertEqual(command[command.index('--host')+1], '/private/s.sock')
                self.assertEqual(command[command.index('--n-gpu-layers')+1], '999')
                self.assertEqual(command[command.index('--fit')+1], 'off')
                self.assertEqual(command[command.index('--parallel')+1], '1')
                self.assertEqual(command[command.index('--ctx-size')+1], '8192')
                self.assertIn('--offline', command)
                self.assertIn('--jinja', command)
                self.assertNotIn('--hf-repo', command)
                self.assertNotIn('--chat-template-file', command)
                self.assertNotIn('--stop', command)  # Muse <|eom|> is not end of turn.
                self.assertIsNone(adapter.generation_tokens)
                self.assertEqual(adapter.reasoning_budget,-1)
                self.assertEqual(command[command.index("--reasoning-budget")+1],"-1")
                self.assertEqual(command[command.index("--predict")+1], "-1")
        muse = model_adapter('muse_glimmer')
        self.assertEqual(muse.template_parameters(), {'chat_template_kwargs': {'reasoning_strength': 'high'}})
        self.assertEqual(model_adapter('gpt_oss').template_parameters(), {'reasoning_effort': 'medium'})
        for invalid in ('remote', '--hf-repo', [], None):
            with self.assertRaises(AgentError): model_adapter(invalid)

    def test_transport_selects_sampling_and_private_reasoning_per_adapter(self):
        for identifier in ADAPTERS:
            with self.subTest(adapter=identifier):
                adapter = model_adapter(identifier)
                response = completion(None, [tool('list_folders', {})])
                response['choices'][0]['message']['reasoning_content'] = 'Synthetic private reasoning'
                model = LocalChatModel('http://127.0.0.1:1', 'fixture', adapter=identifier)
                with patch.object(model, '_post', return_value=json_bytes(response)) as post:
                    reply = model.complete([], [])
                    body = json.loads(post.call_args.args[1])
                self.assertEqual(body['temperature'], adapter.temperature)
                self.assertEqual(body['top_p'], adapter.top_p)
                self.assertEqual(body['top_k'], adapter.top_k)
                self.assertEqual(body['min_p'], adapter.min_p)
                self.assertFalse(body['parallel_tool_calls'])
                self.assertEqual(reply.reasoning, 'Synthetic private reasoning' if identifier == 'gpt_oss' else '')
                final = completion('Synthetic final')
                final['choices'][0]['message']['reasoning_content'] = 'Must be discarded'
                with patch.object(model, '_post', return_value=json_bytes(final)):
                    self.assertEqual(model.complete([], []).reasoning, '')

    def test_context_count_uses_the_same_adapter_template_parameters(self):
        for identifier in ADAPTERS:
            model = object.__new__(WindowsSocketChatModel)
            model.adapter = model_adapter(identifier)
            with patch.object(model, '_post', side_effect=[json_bytes({'prompt':'synthetic'}),
                                                          json_bytes({'tokens':[1, 2]})]) as post:
                self.assertEqual(model.prompt_tokens([], []), 2)
                body = json.loads(post.call_args_list[0].args[1])
                for key, value in model.adapter.template_parameters().items():
                    self.assertEqual(body[key], value)

    def test_new_nemotron_template_settings_match_launch_requests_and_token_count(self):
        # These controls affect the rendered prompt. Counting with different
        # settings can silently exceed the worker's context budget.
        for identifier in ('nemotron_cascade2', 'nemotron35'):
            with self.subTest(adapter=identifier):
                adapter = model_adapter(identifier)
                command = server_command('/runtime', '/model.gguf', '/private/s.sock', '/private/key', identifier)
                template = json.loads(command[command.index('--chat-template-kwargs')+1])
                model = LocalChatModel('http://127.0.0.1:1', 'fixture', adapter=identifier)
                with patch.object(model, '_post', return_value=json_bytes(completion('Synthetic final'))) as post:
                    model.complete([{'role':'user', 'content':'Synthetic task'}], [])
                    request = json.loads(post.call_args.args[1])
                self.assertEqual(request['chat_template_kwargs'], template)
                self.assertTrue(template['enable_thinking'])
                self.assertEqual(request['temperature'], 1.)
                self.assertEqual(request['top_p'], .95)
                self.assertEqual(request['top_k'], 0)
                self.assertEqual(request['min_p'], 0.)
                if identifier == 'nemotron_cascade2':
                    self.assertEqual(template['reasoning_budget'],
                                     int(command[command.index('--reasoning-budget')+1]))
                self.assertNotIn('--model-draft', command)
                self.assertNotIn('--spec-type', command)
                self.assertFalse(adapter.retain_tool_reasoning)

    def test_malformed_reasoning_and_incomplete_completions_fail_closed(self):
        for reasoning in ([], {}, False, 0, 'x' * (64 * 1024 + 1)):
            response = completion('answer')
            response['choices'][0]['message']['reasoning_content'] = reasoning
            with self.assertRaises(AgentError): LocalChatModel._parse(json_bytes(response))
        for reason in ('error', 'content_filter'):
            with self.assertRaises(AgentError): LocalChatModel._parse(json_bytes(completion(reason=reason)))


@unittest.skipUnless(os.name == 'posix', 'Portable policy and broker fixtures')
class ModelCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        shutil.copytree(ROOT/'profiles', self.root/'profiles', ignore=shutil.ignore_patterns('* 2.*'))
        state = self.root/'state'; state.mkdir(mode=0o700)
        self.vault = LocalVault(state); self.addCleanup(self.vault.close)
        self.manager = ModelManager(self.root, self.vault, clock=lambda: 1000)

    def policy(self, profiles, **overrides):
        key = Ed25519PrivateKey.generate()
        private = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.manager.policy.enroll(public, hashlib.sha256(public).hexdigest(), development=True)
        value = {'format':1, 'sequence':1, 'expires':2000, 'profiles':profiles,
                 'blocked_publishers':[], 'blocked_jurisdictions':[], **overrides}
        self.manager.policy.update(sign_document(value, private), validate_model_policy, development=True)

    def test_embedded_catalog_allows_all_nine_but_keeps_nemotron_default(self):
        self.assertEqual(self.manager.selected(), DEFAULT)
        for profile in self.manager.profiles():
            self.manager.authorize(profile['id'], operation='install')
            self.manager.authorize(profile['id'], workload='code_evaluation')
            for scope in ('public', 'cui'):
                with self.assertRaises(AccessDenied):
                    self.manager.authorize(profile['id'], workload='code_evaluation', data_scope=scope)

    def test_signed_allowlist_is_authoritative_and_blocks_origin(self):
        gemma = builtin_profiles(self.root)[0]
        self.policy([gemma], blocked_publishers=['google'])
        with self.assertRaises(AccessDenied): self.manager.authorize(gemma['id'])
        with self.assertRaises(AccessDenied): self.manager.authorize(DEFAULT)
        self.assertEqual(len(self.manager.profiles()), 1)

    def test_offline_import_and_selection_for_all_nine_with_inert_signed_fixtures(self):
        profiles = builtin_profiles(self.root)
        payloads = {}
        for profile in profiles:
            for pin in model_pins(profile):
                data = b'GGUF inert fixture; never inference: '+pin['name'].encode()
                payloads[pin['name']] = data
                pin.update(size=len(data), sha256=hashlib.sha256(data).hexdigest())
            if 'model_shards' in profile:
                profile['model'] = copy.deepcopy(profile['model_shards'][0])
            profile['workloads'] = ['documents']
            profile.pop('source')  # These are fixture bytes, not publisher payloads.
        self.policy(profiles)
        for profile in profiles:
            identifier = profile['id']; source = self.root/profile['model']['name']
            for pin in model_pins(profile):
                (self.root/pin['name']).write_bytes(payloads[pin['name']])
            path = self.manager.import_model(identifier, source)
            self.assertEqual(path.read_bytes(), payloads[profile['model']['name']])
            self.manager.select(identifier)
            self.assertEqual(self.manager.selected(), identifier)
            source.write_bytes(b'wrong bytes')
            with self.assertRaises(AccessDenied): self.manager.import_model(identifier, source)

    def test_known_coding_id_cannot_authorize_different_weights_or_adapter(self):
        profile = builtin_profiles(self.root)[0]
        profile['model']['sha256'] = '0'*64
        self.policy([profile])
        with self.assertRaisesRegex(AccessDenied, 'separately reviewed'):
            self.manager.authorize(profile['id'], workload='code_evaluation')

    def test_new_nemotron_provenance_and_coding_bindings_are_enforced(self):
        profiles = [p for p in self.manager.profiles()
                    if p['adapter'] in {'nemotron_cascade2', 'nemotron35'}]
        self.assertEqual(len(profiles), 2)
        for profile in profiles:
            self.assertIn('nvidia', profile['publishers'])
            self.assertIn('unknown', profile['jurisdictions'])
            self.assertEqual(profile['native_acceptance'], 'pending')
            self.assertEqual(profile['license']['redistribution'], 'pending')
            with self.subTest(model=profile['id']):
                changed = copy.deepcopy(profile)
                changed['adapter'] = 'nemotron3'
                with patch.object(self.manager, 'current_policy', return_value={}), \
                     patch.object(self.manager, 'profiles', return_value=[changed]):
                    with self.assertRaisesRegex(AccessDenied, 'separately reviewed'):
                        self.manager.authorize(changed['id'], workload='code_evaluation')
        self.policy(profiles, blocked_publishers=['nvidia'])
        self.assertEqual(self.manager.recommendations(
            Hardware(65536, 8, ({'name':'Synthetic GPU', 'vram_mib':24576},), 'fixture')), [])
        for profile in profiles:
            with self.assertRaises(AccessDenied): self.manager.authorize(profile['id'])

    def test_custom_model_adapter_cannot_expand_execution_authority(self):
        profile = builtin_profiles(self.root)[0]
        profile['id'] = 'custom-document-model'
        value = {'format':1, 'sequence':1, 'expires':2000, 'profiles':[profile],
                 'blocked_publishers':[], 'blocked_jurisdictions':[]}
        with self.assertRaises(AccessDenied): validate_model_policy(value)
        profile['workloads'] = ['documents']
        validate_model_policy(value)
        for bad in ('shell', [], '--reasoning'):
            profile['adapter'] = bad
            with self.assertRaises(AccessDenied): validate_model_policy(value)

    def test_catalog_drift_is_rejected_before_selection_or_launch(self):
        path = self.root/'profiles/model-catalog.json'
        path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(AccessDenied, 'reviewed host policy'): self.manager.profiles()
        with self.assertRaises(AccessDenied): self.manager.authorize(DEFAULT)

    def test_capacity_uses_cuda0_and_has_smaller_hardware_profiles(self):
        recommendations = self.manager.recommendations(Hardware(32768,8,({'name':'NVIDIA','vram_mib':16384},),'win32','amd64'))
        fits = {r['id'] for r in recommendations if r['fits']}
        self.assertEqual(fits, CPU_IDS | {'gemma4-12b-q4-evaluation-1', 'gpt-oss-20b-mxfp4-evaluation-1'})
        for profile in self.manager.profiles():
            if profile['id'] in CPU_IDS:
                continue  # CPU fit requires explicit Windows x64 architecture evidence.
            if profile['id'] == SUPER_ID:
                self.assertFalse(self.manager.hardware_fit(profile,
                    Hardware(65536,8,({'name':'RTX 4090','vram_mib':24564},),'win32','amd64')))
                continue
            self.assertTrue(self.manager.hardware_fit(profile,
                Hardware(65536,8,({'name':'RTX 4090','vram_mib':24564},),'win32','amd64')))
            self.assertFalse(self.manager.hardware_fit(profile,
                Hardware(65536,8,({'name':'small','vram_mib':4096}, {'name':'large','vram_mib':49152}),'fixture')))

    def test_changed_policy_binding_requires_restart_before_another_model_call(self):
        session = object.__new__(WindowsSession)
        session._operation = threading.RLock()
        from types import SimpleNamespace
        session.ready, session.closed = True, False
        session.drain = SimpleNamespace(failed=threading.Event())
        session.cancelled = threading.Event()
        session.model_manager = self.manager
        session.model_profile = copy.deepcopy(builtin_profiles(self.root)[-1])
        session.model_profile['adapter'] = 'gemma4'
        with self.assertRaisesRegex(AccessDenied, 'restart'):
            session.ask('Synthetic question')

    def test_completed_turn_drops_private_reasoning_before_citation_repair_or_history(self):
        from local_ai_appliance.agent import DocumentAgent
        from local_ai_appliance.workspace import Workspace
        workspace = Workspace(); self.addCleanup(workspace.close)
        model = LocalChatModel('http://127.0.0.1:1', 'fixture', adapter='gpt_oss')
        agent = DocumentAgent(workspace, model)
        state = {'messages':[{'role':'system','content':'Synthetic instructions'},
                             {'role':'user','content':'Synthetic request'},
                             {'role':'assistant','content':'','reasoning_content':'PRIVATE_SYNTHETIC_TRACE'},
                             {'role':'tool','tool_call_id':'call1','content':'[]'}],
                 'model_calls':1, 'tool_calls':1, 'used_call_ids':['call1'],
                 'history_messages':0, 'history_dropped':0, 'permission_revision':workspace.broker.revision}
        with patch.object(model, '_post', return_value=json_bytes(completion('Synthetic final'))):
            result = agent._call_model(state)
        self.assertNotIn('PRIVATE_SYNTHETIC_TRACE', json.dumps(result))
        self.assertIn('PRIVATE_SYNTHETIC_TRACE', json.dumps(state))  # Caller state was not mutated.

    def test_provenance_and_qualification_fields_cannot_be_forged(self):
        profile = builtin_profiles(self.root)[0]
        value = {'format':1, 'sequence':1, 'expires':2000, 'profiles':[profile],
                 'blocked_publishers':[], 'blocked_jurisdictions':[]}
        for field, bad in (('native_acceptance','passed'), ('display_name','bad\nname'),
                           ('source',{'url':'https://unreviewed.invalid/weights.gguf'})):
            changed = copy.deepcopy(value); changed['profiles'][0][field] = bad
            with self.assertRaises(AccessDenied): validate_model_policy(changed)

    def test_installer_snapshot_includes_catalog_and_adapters(self):
        from local_ai_appliance.evaluation_install import source_files
        paths = {p['path'] for p in source_files(ROOT)}
        self.assertIn('profiles/model-catalog.json', paths)
        self.assertIn('src/local_ai_appliance/model_adapters.py', paths)

    def test_all_nine_document_code_tool_review_flows_use_synthetic_server(self):
        from local_ai_appliance.code_agent import CodeAgent
        from local_ai_appliance.code_workspace import CodeWorkspace
        from local_ai_appliance.workspace import Workspace
        from test_code_workspace import SimulatedRunner
        for profile in builtin_profiles(self.root):
            with self.subTest(model=profile['id']), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve(); reference = root/'reference'; reference.mkdir()
                destination = root/'destination'; destination.mkdir()
                original = (ROOT/'tests/fixtures/silo-milestone/policy.txt').read_bytes()
                (reference/'policy.txt').write_bytes(original)
                workspace = Workspace()
                runner = SimulatedRunner()
                code = None
                try:
                    ro = workspace.grant(reference, 'read-only'); rw = workspace.grant(destination, 'editable')
                    code = CodeWorkspace(workspace, runner, configuration={'catalog_id':profile['id']})
                    responses = [
                        completion(None, [tool('read_text', {'folder_id':ro.id,'path':'policy.txt'}, id='call1')]),
                        completion(None, [tool('stage_input', {'source_id':'S1','name':'policy.txt'}, id='call2')]),
                        completion(None, [tool('code_write', {'path':'analyze.py','text':'# inert simulation'}, id='call3')]),
                        completion(None, [tool('run_python', {'entrypoint':'analyze.py'}, id='call4')]),
                        completion(None, [tool('prepare_export', {'destination_folder':rw.id,'destination_path':'artifact.zip'}, id='call5')]),
                        completion('Simulated artifact prepared for review. [source:S1:line:2]'),
                    ]
                    for response in responses:
                        response['choices'][0]['message']['reasoning_content'] = 'PRIVATE_SYNTHETIC_TRACE'
                    def respond(body):
                        return 200, json_bytes(responses.pop(0)), {}
                    with fixture(respond) as (endpoint, requests):
                        model = LocalChatModel(endpoint, 'synthetic-model', adapter=profile['adapter'])
                        result = CodeAgent(workspace, model, code).run('Prepare a synthetic artifact')
                    self.assertEqual(result.model_calls, 6)
                    self.assertEqual(result.tool_calls, 5)
                    for request in requests[1:]:
                        self.assertTrue(json.loads(request[2]['messages'][-1]['content'])['ok'])
                    self.assertEqual(len(runner.results), 1)
                    self.assertNotIn('PRIVATE_SYNTHETIC_TRACE', result.answer)
                    reasoning = [m.get('reasoning_content') for m in requests[-1][2]['messages'] if m['role']=='assistant']
                    self.assertEqual(any(reasoning), profile['adapter']=='gpt_oss')
                    self.assertEqual((reference/'policy.txt').read_bytes(), original)
                    self.assertFalse((destination/'artifact.zip').exists())
                    identifier = next(iter(code.exports))
                    with self.assertRaises(AccessDenied): code.approve(identifier)
                    code.review(identifier); code.approve(identifier)
                    self.assertTrue((destination/'artifact.zip').is_file())
                finally:
                    if code is not None: code.close()
                    workspace.close()
