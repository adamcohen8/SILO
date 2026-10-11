"""Portable Qt integration fixtures; no native Windows qualification."""
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtWidgets import QApplication
    from local_ai_appliance.windows_desktop import WindowsAssistantWindow
    from local_ai_appliance.project_dialog import ProjectDialog
    QT_AVAILABLE=True
except ImportError:
    QT_AVAILABLE=False

from local_ai_appliance.conversation import Conversation
from local_ai_appliance.project_store import LocalVault,ProjectStore
from local_ai_appliance.workspace import Workspace


class FixtureService:
    def __init__(self):
        self.workspace=Workspace()
        self.conversation=Conversation()
        self.closed=False;self.ready=True;self.instructions=''
        self.model_profile={'id':'synthetic-alternate-model'}

    def clear_chat(self):
        self.conversation.clear()
        for proposal in self.workspace.pending_proposals():self.workspace.discard(proposal.id)

    def cancel(self):self.ready=False;self.clear_chat()
    def close(self):self.clear_chat();self.workspace.close();self.closed=True


@unittest.skipUnless(QT_AVAILABLE and os.name=='posix','Optional Qt portable project fixture')
class ProjectDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.state=self.root/'state';self.state.mkdir(mode=0o700)
        self.service=FixtureService()
        repository=Path(__file__).resolve().parents[1]
        self.window=WindowsAssistantWindow(repository,self.service,autostart=False)
        self.window.project_vault=LocalVault(self.state)
        self.window.model_ready(None)
        self.window.show()
        self.addCleanup(self.stop)

    def idle(self):
        deadline=time.monotonic()+10
        self.app.processEvents()
        while self.window.busy or self.window.jobs:
            self.app.processEvents();time.sleep(.005)
            if time.monotonic()>deadline:self.fail('Portable Qt operation timed out')

    def stop(self):
        self.window.close();self.idle();self.app.processEvents()

    def test_idle_close_persists_before_cancellation_clears_conversation(self):
        backend=self.window.project_backend
        project=backend.create_project('Retained desktop project')
        backend.conversation.append('Synthetic prompt','Synthetic answer',[],self.window.workspace.broker.revision)
        self.window.close();self.idle()
        self.assertTrue(self.window.cleaned);self.assertFalse(self.service.conversation.turns)
        vault=LocalVault(self.state)
        try:
            record=ProjectStore(vault).load(project.id)
            self.assertEqual(record['turns'][0]['prompt'],'Synthetic prompt')
            self.assertEqual(vault.get('active-project')['id'],project.id)
        finally:vault.close()

    def test_project_dialog_routes_to_shared_backend_and_reports_selected_model(self):
        self.assertIn('synthetic-alternate-model',self.window.status.text())
        dialog=ProjectDialog(self.window);self.addCleanup(dialog.close)
        with patch('local_ai_appliance.project_dialog.QInputDialog.getText',return_value=('Desktop project',True)):
            dialog.create();self.idle()
        self.assertEqual(self.window.project_backend.project.name,'Desktop project')
        self.assertEqual(dialog.items.count(),1)
        with patch('local_ai_appliance.project_dialog.QInputDialog.getMultiLineText',return_value=('Use units.',True)):
            dialog.instructions();self.idle()
        self.assertIn('Use units.',self.service.instructions)
        dialog.close_project();self.idle()
        self.assertIsNone(self.window.project_backend.record)
        self.assertEqual(dialog.items.count(),1)


if __name__=='__main__':unittest.main()
