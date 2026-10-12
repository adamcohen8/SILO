"""Native storage and source navigation fixtures; no execution/acceptance enrollment."""
import os
from pathlib import Path
import tempfile
import unittest
import test_coding_workflow as portable
from local_ai_appliance.code_workspace import CodeWorkspace
from local_ai_appliance.code_navigation import NavigationIndex
from local_ai_appliance.execution_policy import DisabledExecutionService
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.project_store import LocalVault, ProjectStore, project_data_directory
from local_ai_appliance.repository import RepositorySnapshot
from local_ai_appliance.repository_apply import RepositoryApply
from local_ai_appliance.windows_folders import WindowsFolderBroker
from local_ai_appliance.workspace import Workspace


@unittest.skipUnless(os.name=='nt','Native NTFS/DPAPI/CNG coding data fixture')
class WindowsCodingDataTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='silo-native-coding-data-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.ref=self.root/'ref';self.target=self.root/'target'
        self.ref.mkdir();self.target.mkdir()
        for root in (self.ref,self.target):
            (root/'a.py').write_bytes(b'old\n');(root/'delete.txt').write_bytes(b'delete\n')
        self.workspace=Workspace(WindowsFolderBroker(validation_mode=True));self.addCleanup(self.workspace.close)
        self.ro=self.workspace.grant(self.ref,'read-only');self.rw=self.workspace.grant(self.target,'editable')
        self.code=CodeWorkspace(self.workspace,DisabledExecutionService());self.addCleanup(self.code.close)
        RepositorySnapshot.import_from(self.code,self.ro.id)
        self.code.write('a.py','new\n',self.code.read('a.py')['sha256'])
        self.code.delete('delete.txt',self.code.read('delete.txt')['sha256']);self.code.write('add.txt','new file\n')
        state=self.root/'state';state.mkdir();self.vault=LocalVault(project_data_directory(state),windows_validation=True)
        self.addCleanup(self.vault.close);self.project=ProjectStore(self.vault).create('Synthetic native coding')
        self.service=RepositoryApply(self.code,self.vault,self.project.id,development=True)

    test_navigation_incremental_diagnostics_and_no_code_execution=portable.RepositoryWorkflowTests.test_navigation_incremental_diagnostics_and_no_code_execution
    test_build_snapshot_restores_as_editing_without_runner_authority=portable.RepositoryWorkflowTests.test_build_snapshot_restores_as_editing_without_runner_authority
    test_missing_acceptance_denies_publication=portable.RepositoryWorkflowTests.test_no_development_flag_cannot_enable_native_publication

    def test_navigation_file_and_result_pages_unicode_and_incremental_hashes(self):
        text='raise RuntimeError("source must never execute")\ndef caf\u00e9():\n    pass\n'+'caf\u00e9()\n'*125
        self.code.write('a.py',text,self.code.read('a.py')['sha256'])
        for i in range(140):self.code.write(f'p{i:03}.py',f'def function_{i}():\n    pass\n')
        index=NavigationIndex.for_code(self.code);first=index.query('references','caf\u00e9')
        self.assertEqual(first['total'],126);self.assertEqual(len(first['items']),100)
        second=index.query('references','caf\u00e9',first['next_offset']);self.assertEqual(len(second['items']),26)
        self.assertIsNone(second['next_offset']);self.assertEqual(first['next_file_offset'],128)
        cached=index.cache['a.py'];NavigationIndex.for_code(self.code);self.assertIs(index.cache['a.py'],cached)
        last=NavigationIndex.for_code(self.code,file_offset=128).query('definitions','function_139')
        self.assertEqual(last['total'],1);self.assertIsNone(last['next_file_offset'])
        self.code.delete('p139.py',self.code.read('p139.py')['sha256'])
        self.assertEqual(NavigationIndex.for_code(self.code,file_offset=128).query('definitions','function_139')['total'],0)
        self.assertEqual((self.ref/'a.py').read_bytes(),b'old\n')

    def test_navigation_lexical_languages_partial_files_and_revoked_grant(self):
        for path,text in [('sample.js','function answer() {}'),('sample.ts','interface Answer {}'),('sample.rs','fn answer() {}'),('sample.cpp','struct Answer {};')]:
            self.code.write(path,text)
        self.code.write('large.py','# synthetic large source\n'+'# x\n'*70000)
        index=NavigationIndex.for_code(self.code);result=index.query('symbols')
        lexical=[i for i in result['items'] if i['path'].startswith('sample.')]
        self.assertEqual(len(lexical),4);self.assertTrue(all(i['engine']=='lexical' for i in lexical))
        self.assertIn('large.py',result['partial_files']);self.assertIn('not resolved bindings',result['limitations'])
        with self.assertRaises(AccessDenied):self.code.run('a.py')
        self.workspace.revoke(self.ro.id)
        with self.assertRaises(AccessDenied):NavigationIndex.for_code(self.code)


if __name__=='__main__':unittest.main()
