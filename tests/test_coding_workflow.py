"""Authority, real portable Git, recovery and offline closure regressions."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from local_ai_appliance.build_policy import BuildPolicy
from local_ai_appliance.code_workspace import CodeWorkspace,RunResult
from local_ai_appliance.code_navigation import NavigationIndex
from local_ai_appliance.code_store import CodeStore
from local_ai_appliance.execution_policy import DisabledExecutionService,ExecutionPolicy
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.git_workflow import GitWorkflow
from local_ai_appliance.language_service import LanguageClient
from local_ai_appliance.model import json_bytes
from local_ai_appliance.offline_environment import OfflineEnvironment,inventory_environment,import_environment
from local_ai_appliance.offline_wheels import resolve_wheels
from local_ai_appliance.project_store import LocalVault,ProjectStore
from local_ai_appliance.repository import RepositorySnapshot
from local_ai_appliance.repository_apply import RepositoryApply
from local_ai_appliance.test_feedback import feedback
from local_ai_appliance.workspace import Workspace


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.env=self.root/'environment';(self.env/'payload').mkdir(parents=True)
        (self.env/'payload/python.exe').write_bytes(b'inert runtime never executed')

    def manifest(self,**updates):
        v=inventory_environment(self.env,identifier_value='python-fixture',platform='windows-x64',language='python',packages=[],
            commands={'run':{'executable':'python.exe','arguments':['{entrypoint}'],'suffixes':['.py']}})
        v.update(updates);data=json_bytes(v);(self.env/'silo-environment.json').write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def test_exact_inventory_import_and_preview_without_execution(self):
        sha=self.manifest();e=OfflineEnvironment(self.env,sha)
        self.assertFalse(e.plan('run','a.py')['execution_enabled'])
        new=import_environment(self.env,self.root/'copy',sha)
        self.assertEqual(new.value,e.value)
        with self.assertRaises(AccessDenied): e.plan('test','a.py')
        for path in ('../host.py','inputs/a.py','a.ps1'):
            with self.assertRaises(AccessDenied):e.plan('run',path)

    def test_payload_and_manifest_drift(self):
        sha=self.manifest();e=OfflineEnvironment(self.env,sha)
        (self.env/'payload/python.exe').write_bytes(b'changed')
        with self.assertRaises(RuntimeError):e.verify()
        with self.assertRaises(AccessDenied):OfflineEnvironment(self.env,'0'*64)

    def test_missing_dependency_and_conflicting_version(self):
        a={'name':'analysis','version':'1','license':'MIT','source':'synthetic','requires':{'array':'2'}}
        with self.assertRaises(AccessDenied):OfflineEnvironment(self.env,self.manifest(packages=[a]))
        b={'name':'array','version':'3','license':'BSD','source':'synthetic','requires':{}}
        with self.assertRaises(AccessDenied):OfflineEnvironment(self.env,self.manifest(packages=[a,b]))
        b['version']='2';self.assertEqual(len(OfflineEnvironment(self.env,self.manifest(packages=[a,b])).value['packages']),2)

    def test_existing_destination_and_extra_file_rejected(self):
        sha=self.manifest();(self.root/'copy').mkdir()
        with self.assertRaises(FileExistsError):import_environment(self.env,self.root/'copy',sha)
        (self.env/'payload/unpinned.dll').write_bytes(b'extra')
        with self.assertRaises(RuntimeError):OfflineEnvironment(self.env,sha)

    def wheel(self,name,version,requires=()):
        filename=f'{name}-{version}-py3-none-any.whl';p=self.root/filename
        with zipfile.ZipFile(p,'w') as z:
            metadata=f'Name: {name}\nVersion: {version}\nLicense-Expression: MIT\nRequires-Python: >=3.11\n'
            metadata+=''.join('Requires-Dist: '+r+'\n' for r in requires)
            z.writestr(f'{name}-{version}.dist-info/METADATA',metadata)
        return {'filename':filename,'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'source':'synthetic fixture'}

    def test_wheel_resolution_uses_actual_metadata_and_windows_markers(self):
        a=self.wheel('analysis','1',['array>=2','posixonly; sys_platform == "linux"'])
        b=self.wheel('array','2')
        result=resolve_wheels(self.root,[a,b],['analysis==1'])
        self.assertEqual([p['name'] for p in result],['analysis','array'])
        self.assertEqual(result[0]['requires'],{'array':'2'})
        with self.assertRaises(AccessDenied):resolve_wheels(self.root,[a],['analysis==1'])

    def test_wheel_hash_conflict_and_direct_url_rejected(self):
        a=self.wheel('analysis','1')
        with self.assertRaises(AccessDenied):resolve_wheels(self.root,[a],['analysis>=2'])
        with self.assertRaises(AccessDenied):resolve_wheels(self.root,[a],['analysis @ https://example.test/a.whl'])
        a['sha256']='0'*64
        with self.assertRaises(AccessDenied):resolve_wheels(self.root,[a],['analysis'])

    def test_marker_interpreter_version_is_target_not_host_and_unknown_os_is_refused(self):
        a=self.wheel('analysis','1',['array; implementation_version >= "3.14"'])
        b=self.wheel('array','2')
        with self.assertRaises(AccessDenied):resolve_wheels(self.root,[a],['analysis==1'])
        self.assertEqual(len(resolve_wheels(self.root,[a,b],['analysis==1'])),2)
        a=self.wheel('analysis','1',['array; platform_release == "10"'])
        with self.assertRaises(AccessDenied):resolve_wheels(self.root,[a,b],['analysis==1'])

    def test_numpy_preparer_imports_its_helpers_in_isolated_startup(self):
        script=Path(__file__).resolve().parents[1]/'scripts/prepare_numpy_environment.py'
        result=subprocess.run([sys.executable,'-I','-B',str(script),'--help'],capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr.decode())
        self.assertIn(b'--profile-sha256',result.stdout)

    def test_build_policy_keeps_single_process_policy_separate(self):
        self.assertEqual(ExecutionPolicy().max_processes,1);self.assertEqual(BuildPolicy().max_processes,8)
        with self.assertRaises(ValueError):ExecutionPolicy(max_processes=2)
        with self.assertRaises(ValueError):BuildPolicy(network='allow')
        with self.assertRaises(ValueError):BuildPolicy(max_processes=33)

    def test_fixed_adapters_keep_entrypoints_literal_and_dependencies_offline(self):
        from local_ai_appliance.build_profiles import fixed_commands
        for language in ('javascript','typescript','rust','cpp'):
            commands=fixed_commands(language,executable='python.exe',compiler='compiler.js',vendored=True,driver='driver.exe')
            for command in commands.values():self.assertEqual(command['arguments'].count('{entrypoint}'),1)
            if language=='rust':
                self.assertIn('--frozen',commands['test']['arguments']);self.assertIn('--offline',commands['test']['arguments'])
            if language=='javascript':self.assertIn('--no-addons',commands['run']['arguments'])
        env=OfflineEnvironment(self.env,self.manifest())
        self.assertEqual(env.plan('run','-option.py')['arguments'],['./-option.py'])

    def test_bootstrap_requires_real_tests_and_reports_their_exit(self):
        # Fixed developer-authored fixture only; no Windows binary/generated
        # program or production portable execution fallback is involved.
        work=self.root/'work';work.mkdir();library=work/'silo_plot';library.mkdir()
        manifest=self.root/'runtime.json';manifest.write_text(json.dumps({'language':'python','python_paths':[]}))
        script=Path(__file__).resolve().parents[1]/'scripts/build_runner_bootstrap.py'
        cases=[('value = 1\n',2),('import unittest\nclass T(unittest.TestCase):\n def test_value(self):self.assertEqual(1,1)\n',0),
               ('import unittest\nclass T(unittest.TestCase):\n def test_value(self):self.assertEqual(1,2)\n',1)]
        executable=sys.executable
        # Embedded host _pth explicitly imports site even with -S. Preserve
        # that host and use a disposable stdlib-only copy for the fixed probe.
        runtime=Path(sys.executable).parent
        pth=runtime/f'python{sys.version_info.major}{sys.version_info.minor}._pth'
        if pth.exists():
            isolated=self.root/'isolated-interpreter';isolated.mkdir()
            for item in runtime.iterdir():
                if item.is_file() and item.suffix.lower() in {'.exe','.dll','.pyd','.zip'}:
                    shutil.copyfile(item,isolated/item.name)
            (isolated/pth.name).write_text(pth.stem+'.zip\n.\n',encoding='ascii')
            executable=str(isolated/Path(sys.executable).name)
        for source,expected in cases:
            (work/'test_fixed.py').write_text(source)
            result=subprocess.run([executable,'-I','-S','-B',str(script),str(work),str(library),str(manifest),'test','./test_fixed.py'],capture_output=True)
            self.assertEqual(result.returncode,expected,result.stderr.decode())


@unittest.skipUnless(os.name=='posix','Portable development broker fixture')
class RepositoryWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
        self.ref=self.root/'ref';self.target=self.root/'target';self.ref.mkdir();self.target.mkdir()
        for root in (self.ref,self.target):
            (root/'a.py').write_bytes(b'old\n');(root/'delete.txt').write_bytes(b'delete\n')
        self.workspace=Workspace();self.addCleanup(self.workspace.close)
        self.ro=self.workspace.grant(self.ref,'read-only');self.rw=self.workspace.grant(self.target,'editable')
        self.code=CodeWorkspace(self.workspace,DisabledExecutionService());self.addCleanup(self.code.close)
        RepositorySnapshot.import_from(self.code,self.ro.id)
        self.code.write('a.py','new\n',self.code.read('a.py')['sha256'])
        self.code.delete('delete.txt',self.code.read('delete.txt')['sha256']);self.code.write('add.txt','new file\n')
        (self.root/'vault').mkdir(mode=0o700)
        self.vault=LocalVault(self.root/'vault');self.addCleanup(self.vault.close)
        self.project=ProjectStore(self.vault).create('Synthetic')
        self.service=RepositoryApply(self.code,self.vault,self.project.id,development=True)

    def prepared(self):
        v=self.service.prepare(self.rw.id);self.service.review(v['id']);return v

    def test_review_required_apply_add_edit_delete_and_reference_preserved(self):
        v=self.service.prepare(self.rw.id)
        with self.assertRaises(AccessDenied):self.service.apply(v['id'],v['review_sha256'])
        self.service.review(v['id']);result=self.service.apply(v['id'],v['review_sha256'])
        self.assertEqual(result['state'],'completed');self.assertEqual((self.target/'a.py').read_text(),'new\n')
        self.assertFalse((self.target/'delete.txt').exists());self.assertEqual((self.ref/'a.py').read_text(),'old\n')
        with self.assertRaises(AccessDenied):self.service.apply(v['id'],v['review_sha256'])

    def test_preimage_or_code_drift_prevents_any_effect(self):
        v=self.prepared();(self.target/'a.py').write_text('concurrent')
        with self.assertRaises(AccessDenied):self.service.apply(v['id'],v['review_sha256'])
        self.assertFalse((self.target/'add.txt').exists());self.assertTrue((self.target/'delete.txt').exists())

    def test_edit_after_review_invalidates_approval(self):
        v=self.prepared();self.code.write('a.py','later',self.code.read('a.py')['sha256'])
        with self.assertRaises(AccessDenied):self.service.apply(v['id'],v['review_sha256'])

    def test_interruption_is_unknown_and_explicit_rollback_restores_bytes(self):
        v=self.prepared();original=self.workspace.broker.apply_reviewed_change;count=0
        def crash(*args,**kwargs):
            nonlocal count
            count+=1
            if count==2:raise RuntimeError('synthetic interruption')
            return original(*args,**kwargs)
        with patch.object(self.workspace.broker,'apply_reviewed_change',side_effect=crash):
            with self.assertRaises(RuntimeError):self.service.apply(v['id'],v['review_sha256'])
        self.assertEqual(self.service.inspect(v['id'])['state'],'unknown')
        fresh=RepositoryApply(self.code,self.vault,self.project.id,development=True)
        fresh.reconcile(v['id'],'rollback')
        self.assertEqual((self.target/'a.py').read_text(),'old\n');self.assertFalse((self.target/'add.txt').exists())
        self.assertTrue((self.target/'delete.txt').exists())

    def test_recovery_preserves_concurrent_foreign_content(self):
        v=self.prepared()
        with patch.object(self.workspace.broker,'apply_reviewed_change',side_effect=RuntimeError('crash')):
            with self.assertRaises(RuntimeError):self.service.apply(v['id'],v['review_sha256'])
        (self.target/'a.py').write_text('foreign')
        with self.assertRaises(AccessDenied):self.service.reconcile(v['id'],'rollback')
        self.assertEqual((self.target/'a.py').read_text(),'foreign')

    def test_code_gc_backup_and_project_deletion_preserve_then_remove_transaction(self):
        v=self.prepared();CodeStore(self.vault).save(self.project.id,self.code)
        blob=self.service._load(v['id'])['changes'][0]['before'];self.assertIsNotNone(self.vault.get(blob))
        backup=self.vault.backup();ProjectStore(self.vault).delete(self.project.id);self.vault.restore(backup)
        self.assertEqual(self.service.inspect(v['id'])['state'],'prepared')
        ProjectStore(self.vault).delete(self.project.id)
        self.assertFalse(self.vault.names('repoapply-'+self.project.id));self.assertFalse(self.vault.names('codeblob-'+self.project.id))

    def test_no_development_flag_cannot_enable_native_publication(self):
        service=RepositoryApply(self.code,self.vault,self.project.id)
        v=service.prepare(self.rw.id);service.review(v['id'])
        with self.assertRaises(AccessDenied):service.apply(v['id'],v['review_sha256'])

    def test_navigation_incremental_diagnostics_and_no_code_execution(self):
        self.code.write('a.py','def answer():\n    return danger()\n',self.code.read('a.py')['sha256'])
        index=NavigationIndex.for_code(self.code);self.assertEqual(index.query('definitions','answer')['total'],1)
        self.assertEqual(index.query('references','danger')['total'],1)
        self.code.write('a.py','def broken(',self.code.read('a.py')['sha256'])
        self.assertEqual(NavigationIndex.for_code(self.code).query('definitions','answer')['total'],0)
        self.assertEqual(index.query('diagnostics')['total'],1)
        with self.assertRaises(AccessDenied):self.code.language_query('symbols','a.py')

    def test_build_snapshot_restores_as_editing_without_runner_authority(self):
        self.code.policy=BuildPolicy()
        store=CodeStore(self.vault);store.save(self.project.id,self.code)
        editing=CodeWorkspace(self.workspace,DisabledExecutionService(),policy=BuildPolicy());self.addCleanup(editing.close)
        result=store.restore(self.project.id,editing)
        self.assertEqual(editing.files,self.code.files);self.assertFalse(editing.runner.available)
        self.assertEqual(editing.runs,[])
        with self.assertRaises(AccessDenied):editing.run_operation('test','a.py')


@unittest.skipUnless(os.name=='posix' and shutil.which('git'),'Portable real Git fixture')
class GitWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
        self.git=Path(shutil.which('git')).resolve()
        self.git_command('init','-q');self.git_command('config','user.name','Fixture');self.git_command('config','user.email','fixture@example.test')
        (self.root/'a.py').write_text('old\n');self.git_command('add','a.py');self.git_command('commit','-qm','Initial')
        self.workspace=Workspace();self.addCleanup(self.workspace.close);self.grant=self.workspace.grant(self.root,'editable')
        self.service=GitWorkflow(self.workspace.broker,self.grant.id,self.git,development=True)
        (self.root/'a.py').write_text('new\n')

    def git_command(self,*args): return subprocess.check_output([str(self.git),*args],cwd=self.root,stderr=subprocess.STDOUT)
    def prepare(self): return self.service.prepare_commit(['a.py'],'Reviewed repair','Fixture','fixture@example.test')

    def test_real_git_status_diff_and_exact_tree_commit_without_hooks(self):
        hook=self.root/'.git/hooks/pre-commit';hook.write_text('#!/bin/sh\ntouch HOOK_EXECUTED\n');hook.chmod(0o700)
        self.assertIn('a.py',self.service.status());self.assertIn('+new',self.service.diff())
        v=self.prepare();result=self.service.commit(v['review_sha256'])
        self.assertEqual(self.git_command('rev-parse','HEAD^{tree}').decode().strip(),v['tree'])
        self.assertFalse((self.root/'HOOK_EXECUTED').exists());self.assertFalse(result['pushed'])

    def test_staged_drift_and_approval_replay_denied(self):
        v=self.prepare();(self.root/'a.py').write_text('concurrent\n');self.git_command('add','a.py')
        with self.assertRaises(AccessDenied):self.service.commit(v['review_sha256'])
        with self.assertRaises(AccessDenied):self.service.commit(v['review_sha256'])

    def test_preexisting_staging_and_config_include_denied(self):
        self.git_command('add','a.py')
        with self.assertRaises(AccessDenied):self.prepare()
        with (self.root/'.git/config').open('a') as f:f.write('\n[include]\n path = /unapproved\n')
        with self.assertRaises(AccessDenied):self.service.status()

    def mirror(self):
        from local_ai_appliance.git_mirror import GitMirror
        root=self.root.parent/(self.root.name+'-mirror')
        root.mkdir();self.addCleanup(shutil.rmtree,root)
        return GitMirror(self.workspace.broker,self.grant.id,root)

    def mirror_commit(self,m):
        def git(*args):
            return subprocess.check_output([str(self.git),'-C',str(m.root),*args],stderr=subprocess.STDOUT).decode().strip()
        parent=git('rev-parse','HEAD');branch=git('symbolic-ref','HEAD')
        git('add','a.py');tree=git('write-tree')
        commit=git('-c','user.name=Fixture','-c','user.email=fixture@example.test','commit-tree',tree,'-p',parent,'-m','Reviewed')
        return commit,tree,parent,branch

    def test_private_git_copy_publishes_exact_objects_index_and_branch(self):
        m=self.mirror();review=self.mirror_commit(m)
        self.assertEqual(self.git_command('diff','--cached').strip(),b'')
        m.publish(*review)
        self.assertEqual(self.git_command('rev-parse','HEAD').decode().strip(),review[0])
        self.assertEqual(self.git_command('diff','--cached').strip(),b'')
        self.git_command('fsck','--no-reflogs')

    def test_private_copy_source_drift_and_malformed_objects_never_publish_head(self):
        m=self.mirror();review=self.mirror_commit(m);head=self.git_command('rev-parse','HEAD')
        (self.root/'a.py').write_text('concurrent source\n')
        with self.assertRaises(AccessDenied):m.publish(*review)
        self.assertEqual(self.git_command('rev-parse','HEAD'),head)
        with self.assertRaises(AccessDenied):m._object(b'not compressed','0'*40)

    def test_private_copy_interrupt_before_branch_keeps_old_head_and_reviewed_stage(self):
        m=self.mirror();review=self.mirror_commit(m);head=self.git_command('rev-parse','HEAD')
        original=self.workspace.broker.apply_reviewed_change
        def interrupted(fid,path,before,after,**kw):
            if path=='.git/'+review[3]:raise OSError('Synthetic interruption before branch publication')
            return original(fid,path,before,after,**kw)
        with patch.object(self.workspace.broker,'apply_reviewed_change',side_effect=interrupted):
            with self.assertRaises(OSError):m.publish(*review)
        self.assertEqual(self.git_command('rev-parse','HEAD'),head)
        self.assertEqual(self.git_command('write-tree').decode().strip(),review[1])

    def test_private_copy_excludes_hooks_and_rejects_shared_storage(self):
        m=self.mirror();self.assertFalse((m.root/'.git/hooks').exists())
        (self.root/'.git/objects/info/alternates').write_text('/unapproved\n')
        with self.assertRaises(AccessDenied):m.snapshot()

    def test_private_git_output_links_and_index_drift_cannot_publish(self):
        m=self.mirror();review=self.mirror_commit(m);head=self.git_command('rev-parse','HEAD')
        expected=m.index_digest()
        (m.root/'.git/index').write_bytes(b'changed index')
        with self.assertRaises(AccessDenied):m.publish(*review,index_sha256=expected)
        self.assertEqual(self.git_command('rev-parse','HEAD'),head)
        (m.root/'.git/index').unlink();(m.root/'.git/index').symlink_to(self.root/'.git/index')
        with self.assertRaises(AccessDenied):m.publish(*review,index_sha256=expected)
        self.assertEqual(self.git_command('rev-parse','HEAD'),head)

    def test_strict_source_inventory_refuses_links_instead_of_omitting_them(self):
        m=self.mirror();(self.root/'outside.py').symlink_to('/ungranted/host/source.py')
        with self.assertRaises(AccessDenied):m.snapshot()


class CodingAcceptanceTests(unittest.TestCase):
    def setUp(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption
        key=Ed25519PrivateKey.generate()
        self.private=key.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption())
        self.public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        self.digest=hashlib.sha256(self.public).hexdigest()

    def sign(self,value):
        from local_ai_appliance.signed_policy import sign_document
        return sign_document(value,self.private)

    def test_build_receipt_cannot_inherit_python_checks_or_change_environment(self):
        from local_ai_appliance.windows_build_runner import qualify_build,BUILD_CHECKS,WindowsBuildRunner
        from local_ai_appliance.windows_code_runner import BOUNDARY_TESTS
        config={'release_sha256':'a'*64,'environment_sha256':'b'*64,'environment_id':'fixture'}
        v={'format_version':1,'scope':'synthetic_build_evaluation','configuration':config,'native_os':'Windows','expires':2000,
           'checks':{c:{'status':'passed','evidence_sha256':'c'*64} for c in BUILD_CHECKS}}
        def check(value,expected=config):
            data=self.sign(value)
            return qualify_build(data,hashlib.sha256(data).hexdigest(),expected,key=self.public,key_digest=self.digest,clock=lambda:1000)
        self.assertEqual(check(v)['scope'],'synthetic_build_evaluation')
        for changed in (v|{'expires':999},v|{'expires':True},v|{'checks':{c:{'status':'passed','evidence_sha256':'c'*64} for c in BOUNDARY_TESTS}}):
            with self.assertRaises(AccessDenied):check(changed)
        with self.assertRaises(AccessDenied):check(v,config|{'environment_sha256':'d'*64})
        unsigned=json_bytes(v)
        with self.assertRaises(AccessDenied):qualify_build(unsigned,hashlib.sha256(unsigned).hexdigest(),config,key=self.public,key_digest=self.digest)
        if os.name!='nt':
            with self.assertRaises(AccessDenied):WindowsBuildRunner(Path('.'),Path('.'),None,'fixture')

    def test_environment_registry_requires_signed_exact_unexpired_map(self):
        from types import SimpleNamespace
        from local_ai_appliance.host_capabilities import environment_registry
        from local_ai_appliance.machine_security import anchor
        v={'format':1,'scope':'offline-environments','expires':2000,'environments':{'fixture':{'root':'synthetic','sha256':'b'*64}}}
        records={'reviewer-anchor':{'key':base64.b64encode(self.public).decode(),'sha256':self.digest}}
        class Store:
            def get(self,k):return records.get(k)
        security=SimpleNamespace(store=Store(),check=lambda:None)
        def enroll(value):
            data=self.sign(value);records['build-environments']=value['environments']
            records['build-environments-review']={'envelope':base64.b64encode(data).decode(),'sha256':hashlib.sha256(data).hexdigest()}
        with self.assertRaises(AccessDenied):environment_registry(security)
        enroll(v)
        with patch('local_ai_appliance.host_capabilities.time.time',return_value=1000):
            self.assertEqual(environment_registry(security),v['environments'])
            records['build-environments']={}
            with self.assertRaises(AccessDenied):environment_registry(security)
            enroll(v|{'expires':999})
            with self.assertRaises(AccessDenied):environment_registry(security)


class ScriptedTransport:
    def __init__(self,responses):
        self.data=io.BytesIO(b''.join(b'Content-Length: '+str(len(json_bytes(v))).encode()+b'\r\n\r\n'+json_bytes(v) for v in responses))
        self.sent=[]
    def write(self,data):self.sent.append(data)
    def read_exact(self,size):
        value=self.data.read(size)
        if len(value)!=size:raise AccessDenied('Fixture EOF')
        return value


class LanguageTests(unittest.TestCase):
    def response(self,identifier,result):return {'jsonrpc':'2.0','id':identifier,'result':result}
    def client(self,messages):return LanguageClient(ScriptedTransport(messages),Path('/synthetic/work'),{'a.py':b'def f(): pass\n'})

    def test_handshake_symbol_query_and_server_command_removed(self):
        c=self.client([self.response(1,{'capabilities':{}}),self.response(2,[{'name':'f','command':{'command':'host-action'}}]),self.response(3,None)])
        result=c.query('symbols','a.py');self.assertNotIn('command',result['result'][0])
        self.assertIn(b'initialize',c.transport.sent[0]);self.assertIn(b'shutdown',c.transport.sent[-2])

    def test_external_location_and_wrong_response_id_denied(self):
        c=self.client([self.response(1,{'capabilities':{}}),self.response(2,{'uri':'file:///outside/secret.py'}),self.response(3,None)])
        with self.assertRaises(AccessDenied):c.query('definitions','a.py')
        with self.assertRaises(AccessDenied):self.client([self.response(5,{})]).query('symbols','a.py')

    def test_server_requests_refused_and_local_location_rewritten(self):
        request={'jsonrpc':'2.0','id':900,'method':'workspace/executeCommand','params':{'command':'download'}}
        c=self.client([request,self.response(1,{'capabilities':{}}),self.response(2,{'uri':(Path('/synthetic/work').absolute()/'a.py').as_uri()}),self.response(3,None)])
        self.assertEqual(c.query('definitions','a.py')['result']['path'],'a.py')
        self.assertTrue(any(b'Host actions are unavailable' in data for data in c.transport.sent))

    def test_duplicate_content_length_and_out_of_document_position_refused(self):
        c=self.client([]);c.transport.data=io.BytesIO(b'Content-Length: 2\r\nContent-Length: 2\r\n\r\n{}')
        with self.assertRaises(AccessDenied):c.receive()
        with self.assertRaises(AccessDenied):self.client([]).query('references','a.py',line=99)

    def test_test_output_claim_cannot_override_process_exit(self):
        self.assertEqual(feedback(1,'ALL TESTS PASSED','FAIL: test_real')['status'],'failed')
        self.assertEqual(feedback(0,'ok','')['status'],'passed')
        self.assertEqual(feedback(1,'a.cpp:12:3: error: missing','')['diagnostics'][0]['line'],12)


if __name__=='__main__':unittest.main()
