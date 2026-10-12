"""Continuation and recovery contracts; no Windows isolation or model-quality claim."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from local_ai_appliance.agent import DocumentAgent, Source
from local_ai_appliance.code_store import CodeStore
from local_ai_appliance.code_workspace import CodeWorkspace
from local_ai_appliance.context_manager import ContextManager
from local_ai_appliance.execution_policy import DisabledExecutionService
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.model import AgentError, LocalChatModel, ModelReply, ToolCall, json_bytes
from local_ai_appliance.model_stream import ChatStream
from local_ai_appliance.project_store import LocalVault, ProjectStore
from local_ai_appliance.repository import RepositorySnapshot
from local_ai_appliance.tasks import TaskStore
from local_ai_appliance.toolchains import ToolchainBundle, candidate_manifest, import_bundle
from local_ai_appliance.work_policy import WorkPolicy
from local_ai_appliance.workspace import Workspace


class ContextTests(unittest.TestCase):
    def test_rollover_preserves_objective_and_complete_tool_pairs(self):
        messages=[{'role':'system','content':'Host rules'},{'role':'user','content':'USER OBJECTIVE'}]
        for i in range(10):
            messages += [{'role':'assistant','content':'','tool_calls':[{'id':str(i)}]},
                         {'role':'tool','tool_call_id':str(i),'content':'x'*900}]
        fitted,_,_,removed=ContextManager(3000).fit(messages,[])
        self.assertGreater(removed,0);self.assertEqual(fitted[1],messages[1])
        self.assertEqual(fitted[-2:],messages[-2:])
        for i,m in enumerate(fitted):
            if m['role']=='tool':self.assertEqual(fitted[i-1]['tool_calls'][0]['id'],m['tool_call_id'])
        self.assertLessEqual(len(json_bytes(fitted)),3000)
        self.assertEqual(len(messages),22)

    def test_large_latest_result_is_marked_partial_and_hashed(self):
        original='x'*10000
        messages=[{'role':'system','content':'Host rules'},{'role':'user','content':'objective'},
                  {'role':'assistant','content':'','tool_calls':[{'id':'x'}]},
                  {'role':'tool','tool_call_id':'x','content':original}]
        fitted,*_=ContextManager(1800).fit(messages,[])
        excerpt=json.loads(fitted[-1]['content'])
        self.assertTrue(excerpt['partial'])
        self.assertEqual(excerpt['original_sha256'],hashlib.sha256(original.encode()).hexdigest())
        self.assertEqual(fitted[-2],messages[-2])

    def test_cannot_drop_or_truncate_objective(self):
        with self.assertRaises(AgentError):ContextManager(1000).fit([
            {'role':'system','content':'rules'},{'role':'user','content':'x'*2000}],[])

    def test_history_removal_is_in_pairs(self):
        messages=[{'role':'system','content':'rules'},{'role':'user','content':'old'*1000},
                  {'role':'assistant','content':'old answer'},{'role':'user','content':'new objective'}]
        fitted,remaining,dropped,_=ContextManager(1000).fit(messages,[],1)
        self.assertEqual((remaining,dropped),(0,1));self.assertEqual(fitted[-1],messages[-1])

    def test_complete_length_text_can_continue_but_partial_tool_cannot_execute(self):
        response={'choices':[{'message':{'role':'assistant','content':'Part one'},'finish_reason':'length'}]}
        self.assertTrue(LocalChatModel._parse(json_bytes(response)).truncated)
        response['choices'][0]['message']['tool_calls']=[{'id':'x','type':'function',
            'function':{'name':'code_write','arguments':'{"path":"x.py"'}}]
        with self.assertRaises(AgentError):LocalChatModel._parse(json_bytes(response))
        seen=[];stream=ChatStream(seen.append,limit=4096)
        stream.feed(b'data: '+json_bytes({'choices':[{'index':0,'delta':{'content':'Part one'},'finish_reason':'length'}]})+b'\n\ndata: [DONE]\n\n')
        self.assertTrue(LocalChatModel._parse(stream.result()).truncated);self.assertEqual(seen,['Part one'])


@unittest.skipUnless(os.name=='posix','Portable broker and encrypted-vault fixture')
class LongWorkTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.private=self.root/'private';self.private.mkdir(mode=0o700)
        self.reference=self.root/'repo';self.reference.mkdir()
        self.drafts=self.root/'drafts';self.drafts.mkdir()
        self.vault=LocalVault(self.private);self.addCleanup(self.vault.close)
        self.workspace=Workspace();self.addCleanup(self.workspace.close)
        self.ro=self.workspace.grant(self.reference,'read-only');self.rw=self.workspace.grant(self.drafts,'editable')
        self.code=CodeWorkspace(self.workspace,DisabledExecutionService());self.addCleanup(self.code.close)
        self.project='a'*32;self.scope='b'*64;self.tasks=TaskStore(self.vault)

    def task(self):return self.tasks.create(self.project,'Synthetic objective',self.scope)

    def test_encrypted_journal_checkpoint_tamper_and_scope_denial(self):
        task=self.task();self.tasks.append(task,'directive',{'text':'Private synthetic direction'},state='running')
        self.tasks.append(task,'answer',{'text':'Done'},state='complete')
        self.assertNotIn(b'Private synthetic direction',b''.join(p.read_bytes() for p in self.private.glob('*.seal')))
        with self.assertRaises(AccessDenied):self.tasks.resume(task,'c'*64)
        self.tasks.resume(task,self.scope)
        event=self.tasks.events(task)[0];event['data']['text']='changed'
        self.vault.put(f'taskevent-{task}-{1:020d}',event)
        with self.assertRaises(AccessDenied):self.tasks.events(task)

    def test_intent_without_result_never_replayed(self):
        task=self.task();self.tasks.append(task,'tool_intent',{'name':'run_python'},state='running')
        with self.assertRaises(AccessDenied):self.tasks.resume(task,self.scope)
        self.assertEqual(self.tasks.load(task)['state'],'unknown')
        with self.assertRaises(AccessDenied):self.tasks.append(task,'tool_intent',{'name':'run_python'})
        self.tasks.reconcile(task);self.tasks.resume(task,self.scope)
        self.assertEqual([e['kind'] for e in self.tasks.events(task)].count('tool_intent'),1)
        self.assertFalse(self.tasks.load(task)['inflight'])

    def test_orphan_checkpoint_requires_explicit_reconciliation(self):
        task=self.task();self.vault.put(f'taskevent-{task}-{1:020d}',{'uncertain':'data'})
        with self.assertRaises(AccessDenied):self.tasks.resume(task,self.scope)
        self.tasks.reconcile(task);self.tasks.resume(task,self.scope)
        self.assertEqual(self.tasks.events(task)[0]['kind'],'reconcile')
        self.assertEqual(len(self.vault.names('taskorphan-'+task+'-')),1)

    def test_many_events_and_paginated_history_have_no_lifetime_quota(self):
        task=self.task()
        for i in range(140):self.tasks.append(task,'directive',{'step':i},state='paused')
        page=self.tasks.events(task,start=101,limit=20)
        self.assertEqual([e['sequence'] for e in page],list(range(101,121)))
        self.assertEqual(self.tasks.load(task)['sequence'],140)

    def test_project_retention_deletes_tasks_snapshots_and_blobs(self):
        store=ProjectStore(self.vault);project=store.create('Synthetic')
        self.tasks.create(project.id,'objective',self.scope)
        self.code.write('a.py','inert');CodeStore(self.vault).save(project.id,self.code)
        store.delete(project.id)
        self.assertFalse(self.tasks.listing(project.id));self.assertFalse(self.vault.names('codeblob-'+project.id))
        self.assertIsNone(self.vault.get('codework-'+project.id))

    def test_backup_roundtrip_includes_code_and_tasks_without_restoring_authority(self):
        task=self.task();self.tasks.append(task,'directive',{},state='running')
        self.code.write('a.py','# never executed');CodeStore(self.vault).save(self.project,self.code)
        backup=self.vault.backup()
        for name in self.vault.names('task-')+self.vault.names('taskevent-')+self.vault.names('codeblob-')+self.vault.names('codework-'):self.vault.delete(name)
        self.vault.restore(backup)
        self.assertEqual(self.tasks.load(task)['state'],'running')
        with self.assertRaises(AccessDenied):self.tasks.resume(task,self.scope)
        new=CodeWorkspace(self.workspace,DisabledExecutionService());self.addCleanup(new.close)
        CodeStore(self.vault).restore(self.project,new)
        self.assertFalse(new.runner.available);self.assertFalse(new.runs);self.assertFalse(new.exports)

    def repository(self):
        (self.reference/'a.py').write_bytes(b'print("old")')
        (self.reference/'.git').mkdir();(self.reference/'.git'/'config').write_text('untrusted metadata')
        (self.reference/'.env').write_text('SYNTHETIC_SECRET=none')
        return RepositorySnapshot.import_from(self.code,self.ro.id)

    def test_repository_exclusions_editing_search_pagination_and_conflicts(self):
        result=self.repository();self.assertEqual(result['files'],1)
        self.assertEqual(set(result['excluded']),{'.git','.env'})
        pin=self.code.read('a.py')['sha256'];self.code.patch('a.py','old','new',pin)
        self.assertEqual(self.code.search('NEW')['total_matches'],1)
        self.assertEqual(self.code.page()['total_files'],1)
        self.assertEqual((self.reference/'a.py').read_bytes(),b'print("old")')
        (self.reference/'a.py').write_bytes(b'concurrent original edit')
        with self.assertRaisesRegex(AccessDenied,'preimages'):self.code.repository.patch(self.code)

    def test_patch_export_requires_host_review_and_detects_source_drift(self):
        self.repository();self.code.patch('a.py','old','new',self.code.read('a.py')['sha256'])
        proposal=self.code.repository.propose_patch(self.code,self.rw.id,'change.patch')
        self.assertIn('No newline at end of file',proposal.text)
        self.assertFalse((self.drafts/'change.patch').exists())
        (self.reference/'a.py').write_bytes(b'changed after proposal')
        with self.assertRaises(AccessDenied):self.workspace.validate_proposal(proposal)
        self.assertFalse((self.drafts/'change.patch').exists())

    def test_exported_git_patch_handles_empty_files_unicode_and_no_final_newline(self):
        import shutil, subprocess
        if not shutil.which('git'): self.skipTest('Git required for actual patch syntax verification')
        (self.reference/'café file.py').write_bytes(b'old')
        (self.reference/'empty.txt').write_bytes(b'')
        RepositorySnapshot.import_from(self.code,self.ro.id)
        self.code.patch('café file.py','old','new',self.code.read('café file.py')['sha256'])
        self.code.delete('empty.txt',self.code.read('empty.txt')['sha256'])
        self.code.write('new.txt','')
        proposal=self.code.repository.propose_patch(self.code,self.rw.id,'change.patch')
        scratch=self.root/'patch-check';scratch.mkdir()
        (scratch/'café file.py').write_bytes(b'old');(scratch/'empty.txt').write_bytes(b'')
        for args in (['--check'],[]):
            result=subprocess.run(['git','apply',*args],input=proposal.text.encode(),cwd=scratch,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((scratch/'café file.py').read_bytes(),b'new')
        self.assertEqual((scratch/'new.txt').read_bytes(),b'');self.assertFalse((scratch/'empty.txt').exists())
        self.assertEqual((self.reference/'café file.py').read_bytes(),b'old')

    def test_restore_retains_baseline_but_no_runs_reviews_or_configuration_authority(self):
        self.repository();self.code.patch('a.py','old','new',self.code.read('a.py')['sha256'])
        store=CodeStore(self.vault);store.save(self.project,self.code)
        new=CodeWorkspace(self.workspace,DisabledExecutionService(),configuration='fresh-authority');self.addCleanup(new.close)
        store.restore(self.project,new)
        self.assertEqual(new.files,self.code.files);self.assertEqual(new.repository.baseline,self.code.repository.baseline)
        self.assertEqual(new.configuration,'fresh-authority');self.assertFalse(new.runs);self.assertFalse(new.reviewed)
        self.assertEqual(len(new.repository.changes(new)),1)
        with self.assertRaises(AccessDenied):new.run('a.py')

    def test_source_drift_or_blob_drift_restore_nothing(self):
        self.repository();store=CodeStore(self.vault);store.save(self.project,self.code)
        (self.reference/'a.py').write_bytes(b'changed')
        new=CodeWorkspace(self.workspace,DisabledExecutionService());self.addCleanup(new.close)
        with self.assertRaises(AccessDenied):store.restore(self.project,new)
        self.assertEqual(new.files,{})
        (self.reference/'a.py').write_bytes(b'print("old")')
        key=self.vault.names('codeblob-')[0];self.vault.put(key,{'data':'AA==','sha256':'0'*64})
        with self.assertRaises(AccessDenied):store.restore(self.project,new)
        self.assertEqual(new.files,{})

    def test_files_only_recovers_edits_after_source_drift_without_authority(self):
        self.repository();store=CodeStore(self.vault)
        self.code.patch('a.py','old','new',self.code.read('a.py')['sha256'])
        store.save(self.project,self.code);(self.reference/'a.py').write_bytes(b'concurrent edit')
        new=CodeWorkspace(self.workspace,DisabledExecutionService());self.addCleanup(new.close)
        store.restore(self.project,new,files_only=True)
        self.assertEqual(new.files['a.py'],b'print("new")')
        self.assertFalse(new.sources);self.assertFalse(new.inputs);self.assertFalse(hasattr(new,'repository'))
        self.assertFalse(new.runs);self.assertFalse(new.reviewed)
        with self.assertRaises(AccessDenied):new.run('a.py')

    def test_delete_rename_and_patch_require_exact_preimages(self):
        self.code.write('x.ts','const x = 1;')
        with self.assertRaises(AccessDenied):self.code.rename('x.ts','y.ts','0'*64)
        digest=self.code.read('x.ts')['sha256'];self.code.rename('x.ts','y.ts',digest)
        with self.assertRaises(AccessDenied):self.code.patch('y.ts','const','new','0'*64)
        self.code.delete('y.ts',digest);self.assertFalse(self.code.files)

    def test_directory_case_aliases_and_file_parent_collisions_are_rejected(self):
        self.code.write('src/a.py','a')
        with self.assertRaises(AccessDenied):self.code.write('SRC/b.py','b')
        self.code.write('file.py','a')
        with self.assertRaises(AccessDenied):self.code.write('file.py/child.py','b')

    def test_more_than_old_file_quota_and_paged_results(self):
        for i in range(130):self.code.write(f'f{i}.py',f'# synthetic {i}\n')
        self.assertEqual(len(self.code.page(limit=100)['files']),100)
        self.assertEqual(len(self.code.page(offset=100)['files']),30)
        self.assertIsNone(self.code.page(offset=100)['next_offset'])

    def test_full_or_partial_repository_listing_cannot_be_mistaken_for_complete(self):
        with patch.object(self.workspace.broker,'list_directory',return_value={'truncated':True,'entries':[]}):
            with self.assertRaises(AccessDenied):RepositorySnapshot.import_from(self.code,self.ro.id)
        self.assertEqual(self.code.files,{})

    def test_interactive_agent_can_exceed_old_call_limits_with_context_rollover(self):
        class Model:
            def __init__(self):self.calls=0;self.requests=[]
            def complete(inner,messages,tools):
                inner.calls+=1;inner.requests.append(messages)
                if inner.calls>55:return ModelReply('Completed synthetic paging work')
                return ModelReply(calls=(ToolCall(str(inner.calls),'list_files',
                    {'folder_id':self.ro.id,'path':f'page{inner.calls}'}),))
        for i in range(1,56):(self.reference/f'page{i}').mkdir()
        model=Model();agent=DocumentAgent(self.workspace,model,max_context_bytes=8192)
        result=agent.run('Inspect the approved synthetic pages')
        self.assertEqual((result.model_calls,result.tool_calls),(56,55))
        self.assertTrue(all(len(json_bytes(m))<=8192 for m in model.requests))
        self.assertTrue(all(m[1]['content']=='Inspect the approved synthetic pages' for m in model.requests))

    def test_benchmark_limits_are_opt_in_and_stall_is_not_a_call_quota(self):
        class Repeated:
            calls=0
            def complete(self,messages,tools):
                self.calls+=1;return ModelReply(calls=(ToolCall(str(self.calls),'list_folders',{}),))
        with self.assertRaisesRegex(AgentError,'paused'):DocumentAgent(self.workspace,Repeated()).run('Inspect folders')
        with self.assertRaisesRegex(AgentError,'budget'):DocumentAgent(self.workspace,Repeated(),max_model_calls=2).run('Inspect folders')
        self.assertEqual(WorkPolicy.benchmark().execution_attempts,8)

    def test_text_continuation_is_joined_and_never_accepted_as_partial_completion(self):
        class Model:
            def __init__(self):self.replies=iter([ModelReply('First ',truncated=True),ModelReply('second')])
            def complete(self,messages,tools):return next(self.replies)
        result=DocumentAgent(self.workspace,Model()).run('Explain a synthetic concept')
        self.assertEqual(result.answer,'First second');self.assertEqual(result.model_calls,2)


class ToolchainTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.bundle=self.root/'bundle';(self.bundle/'payload').mkdir(parents=True)
        (self.bundle/'payload'/'python.exe').write_bytes(b'INERT SYNTHETIC FILE; NOT EXECUTABLE')
        value=candidate_manifest(self.bundle,identifier='fixture',platform='windows-x64',
            commands={'python':{'executable':'python.exe','prefix':['-I','-S'],'suffixes':['.py']}})
        data=json_bytes(value);(self.bundle/'silo-toolchain.json').write_bytes(data);self.digest=hashlib.sha256(data).hexdigest()

    def test_exact_inventory_import_and_structured_command_preview(self):
        imported=import_bundle(self.bundle,self.root/'imported',self.digest)
        plan=imported.plan('python','tests/check.py')
        self.assertEqual(plan.arguments,('-I','-S','tests/check.py'));self.assertEqual(plan.network,'deny')
        with self.assertRaises(AccessDenied):imported.plan('shell','x.py')
        with self.assertRaises(AccessDenied):imported.plan('python','../x.py')
        with self.assertRaises(AccessDenied):imported.plan('python','x.js')
        with self.assertRaises(AccessDenied):imported.activate({'passed':True})

    def test_manifest_payload_or_extra_file_drift_denies_planning(self):
        bundle=ToolchainBundle(self.bundle,self.digest)
        (self.bundle/'silo-toolchain.json').write_bytes(b'changed manifest')
        with self.assertRaises(AccessDenied):bundle.plan('python','x.py')
        (self.bundle/'silo-toolchain.json').write_bytes(json_bytes(bundle.value))
        (self.bundle/'payload'/'extra.dll').write_bytes(b'undeclared')
        with self.assertRaises(RuntimeError):bundle.plan('python','x.py')

    def test_unreviewed_manifest_and_existing_destination_are_rejected(self):
        with self.assertRaises(AccessDenied):ToolchainBundle(self.bundle,'0'*64)
        with self.assertRaises(FileExistsError):import_bundle(self.bundle,self.bundle,self.digest)
        self.assertTrue((self.bundle/'payload'/'python.exe').exists())

@unittest.skipUnless(os.name=='posix','Portable host contract fixture')
class ProjectTaskTests(unittest.TestCase):
    def setUp(self):
        from local_ai_appliance.backend import PortableSession
        from local_ai_appliance.contracts import Project
        from local_ai_appliance.project_store import ProjectSession
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();private=self.root/'private';private.mkdir(mode=0o700)
        self.reference=self.root/'ref';self.reference.mkdir();(self.reference/'a.txt').write_text('Synthetic content\n')
        self.vault=LocalVault(private);self.addCleanup(self.vault.close)
        class Model:
            def complete(self,messages,tools):return ModelReply('Synthetic answer')
        self.backend=PortableSession(Project('unsaved','Unsaved'),Workspace(),Model());self.addCleanup(self.backend.close)
        self.session=ProjectSession(self.backend,ProjectStore(self.vault))
        from local_ai_appliance.contracts import WorkspaceKind
        self.folder=self.session.grant(self.reference,WorkspaceKind.REFERENCE)
        self.session.create_project('Synthetic task')

    def test_automatic_journal_and_scope_change_do_not_restore_old_authority(self):
        self.session.ask('A long objective');task=self.session.active_task
        self.assertEqual(self.session.tasks.load(task)['state'],'complete')
        self.session.set_instructions('A new preference')
        with self.assertRaises(AccessDenied):self.session.ask('Continue')
        self.assertIsNone(self.session.active_task)
        self.session.task_new('New objective');self.session.ask('Continue with current instructions')
        self.assertNotEqual(task,self.session.active_task)

    def test_journal_source_revalidated_after_restart_with_new_grant_id(self):
        task=self.session.task_new('Read synthetic source')
        data=(self.reference/'a.txt').read_bytes()
        self.session._task_event('tool_intent',{'name':'read_text'})
        self.session._task_event('tool_result',{'name':'read_text','result':{
            'folder_id':self.folder.id,'path':'a.txt','sha256':hashlib.sha256(data).hexdigest()}})
        self.session.tasks.append(task,'answer',{'text':'Done'},state='complete')
        project=self.session.project.id
        self.session.close_project();self.session.open_project(project)
        self.session.task_resume(task)
        (self.reference/'a.txt').write_text('Changed source')
        with self.assertRaisesRegex(AccessDenied,'source'):self.session.ask('Continue')

    def test_contained_partial_checkpoint_is_untrusted_and_cannot_grant_authority(self):
        import runpy
        from types import SimpleNamespace
        from local_ai_appliance.windows_workspace import BrokerSession
        task=self.session.task_new('Continue synthetic text')
        broker=BrokerSession(self.session.workspace)
        calls=[]
        channel=SimpleNamespace(initial={'permission_revision':self.session.workspace.broker.revision,'folders':[]},
            request=lambda request: calls.append(request) or broker.handle(request))
        worker=runpy.run_path(str(Path(__file__).resolve().parents[1]/'scripts/contained_agent_worker.py'))
        remote=worker['RemoteWorkspace'](channel)
        remote.task_sink('tool_intent',{'name':'unavailable'})
        self.assertEqual(calls,[])  # No duplicate intents from the worker.
        data={'text':'Partial public text','status':'partial; not a completed answer'}
        remote.task_sink('continuation',data)
        self.assertTrue(calls[-1]['op']=='continuation')
        events=self.session.tasks.events(task)
        self.assertEqual(events[-1]['kind'],'continuation');self.assertEqual(events[-1]['data'],data)
        self.assertFalse(self.session.tasks.load(task)['inflight'])
        for invalid in (dict(data,approval=True),dict(data,status='passed'),dict(data,text='x'*50000)):
            self.assertFalse(broker.handle({'op':'continuation','data':invalid})['ok'])
        self.assertFalse(broker.handle({'op':'reconcile','id':task})['ok'])
        self.assertEqual(len(self.session.tasks.events(task)),1)

    def test_native_service_edit_only_has_no_runner_authority(self):
        import threading
        from types import SimpleNamespace
        from local_ai_appliance.windows_session import WindowsSession
        service=WindowsSession.__new__(WindowsSession)
        service._operation=threading.Lock();service.ready=True;service.closed=False;service.code=None
        service.workspace=self.backend.workspace;service.security=SimpleNamespace(candidate=True)
        service.clear_chat=lambda: None;service.check_cancelled=lambda: None
        code=service.create_code(__import__('local_ai_appliance.execution_policy',fromlist=['ExecutionPolicy']).ExecutionPolicy(),edit_only=True)
        self.addCleanup(code.close);code.write('test.py','# synthetic, never run')
        self.assertFalse(code.runner.available)
        with self.assertRaises(AccessDenied):code.run('test.py')

    def test_actual_run_controller_has_no_eight_run_quota_and_bounds_recent_receipts(self):
        from test_code_workspace import SimulatedRunner
        code=CodeWorkspace(self.backend.workspace,SimulatedRunner());self.addCleanup(code.close)
        code.write('a.py','# inert simulation')
        for _ in range(20):result=code.run('a.py')
        self.assertEqual(result['run'],20);self.assertEqual(code.attempts,20)
        self.assertEqual(len(code.runs),16);self.assertEqual(code.retired_runs,4)
