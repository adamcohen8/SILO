"""Native Windows long-work contracts using NTFS, DPAPI, CNG and held handles.

Reuse the portable assertions with native storage/broker fixtures. Model replies
are scripted; execution is disabled. No managed-session, model-quality, LPAC or
ordinary-user generated-code acceptance is established by these tests.
"""
import os
from pathlib import Path
import tempfile
import unittest
import test_long_work as portable
from local_ai_appliance.project_store import LocalVault, project_data_directory
from local_ai_appliance.windows_folders import WindowsFolderBroker
from local_ai_appliance.workspace import Workspace
from local_ai_appliance.code_workspace import CodeWorkspace
from local_ai_appliance.execution_policy import DisabledExecutionService
from local_ai_appliance.tasks import TaskStore

@unittest.skipUnless(os.name == 'nt', 'Native Windows task/storage/broker fixture')
class WindowsLongWorkTests(portable.LongWorkTests):
    __unittest_skip__ = False  # Reset the inherited POSIX-only class marker.
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='silo-native-long-work-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        state = self.root/'state'; state.mkdir()
        self.private = project_data_directory(state)
        self.reference = self.root/'repo'; self.reference.mkdir()
        self.drafts = self.root/'drafts'; self.drafts.mkdir()
        self.vault = LocalVault(self.private, windows_validation=True)
        self.addCleanup(self.vault.close)
        self.workspace = Workspace(WindowsFolderBroker(validation_mode=True))
        self.addCleanup(self.workspace.close)
        self.ro = self.workspace.grant(self.reference, 'read-only')
        self.rw = self.workspace.grant(self.drafts, 'editable')
        self.code = CodeWorkspace(self.workspace, DisabledExecutionService())
        self.addCleanup(self.code.close)
        self.project = 'a'*32; self.scope = 'b'*64
        self.tasks = TaskStore(self.vault)
