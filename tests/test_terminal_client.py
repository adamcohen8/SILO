"""Real terminal controller and adapter with a fake host, no code execution."""
import io
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from local_ai_appliance.agent import AgentResult
from local_ai_appliance.backend import WindowsSessionAdapter
from local_ai_appliance.code_workspace import CodeWorkspace
from local_ai_appliance.contracts import Project
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.terminal_client import TerminalClient
from local_ai_appliance.terminal_ui import TerminalView
from local_ai_appliance.workspace import Workspace
from test_code_workspace import SimulatedRunner


class HostFixture:
    def __init__(self,workspace): self.workspace=workspace; self.code=None; self.questions=[]; self.cancelled=False
    def start(self,progress): pass
    def ask(self,prompt):
        self.questions.append(prompt)
        if self.code: self.code.exports.clear(); self.code.reviewed.clear()
        return AgentResult('Fixture answer \x1b[2J',(),(),1,0)
    def create_code(self,policy,**kwargs):
        self.code=CodeWorkspace(self.workspace,SimulatedRunner(),policy=policy)
        return self.code
    def close_code(self):
        if self.code: self.code.close(); self.code=None
    def clear_chat(self):
        if self.code: self.code.exports.clear(); self.code.reviewed.clear()
    def cancel(self):
        self.cancelled=True
        if self.code: self.code.cancel()
    def close(self): self.close_code(); self.workspace.close()


@unittest.skipUnless(os.name=='posix','Portable fixture uses POSIX broker')
class TerminalClientTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve(); self.dest=self.root/'destination with spaces'; self.dest.mkdir()
        self.host=HostFixture(Workspace()); self.backend=WindowsSessionAdapter(Project('test','Synthetic fixture'),self.host)
        self.addCleanup(self.backend.close); self.backend.start()
        self.output=io.StringIO(); self.client=TerminalClient(self.backend,view=TerminalView(self.output,plain=True,width=100))

    def test_literal_folder_path_review_publication_and_replay(self):
        self.client.handle('/draft '+str(self.dest)); self.client.handle('/code')
        code=self.host.code; code.write('analyze.py','# inert fixture'); code.run('analyze.py')
        folder=next(iter(self.backend.workspace.broker.folders()))
        identifier=code.prepare_export(folder.id,'reviewed.zip')['export_id']
        with self.assertRaises(AccessDenied): self.client.handle('/approve '+identifier)
        self.client.handle('/review '+identifier)
        self.assertFalse((self.dest/'reviewed.zip').exists())
        self.assertIn('UNPUBLISHED ZIP',self.output.getvalue()); self.assertIn('108',self.output.getvalue())
        self.client.handle('/approve '+identifier)
        self.assertTrue((self.dest/'reviewed.zip').is_file())
        with self.assertRaises(AccessDenied): self.client.handle('/approve '+identifier)

    def test_unknown_commands_and_paths_never_invoke_model_or_grant_code(self):
        for command in ('/shell whoami','/approve forged','/code C:\\Users','/artifact missing.py'):
            with self.assertRaises(AccessDenied): self.client.handle(command)
        self.assertEqual(self.host.questions,[]); self.assertIsNone(self.host.code)

    def test_model_text_escaped_and_new_question_clears_export(self):
        self.client.handle('/draft '+str(self.dest)); self.client.handle('/code')
        code=self.host.code; code.write('test.py','# inert'); code.run('test.py')
        folder=next(iter(self.backend.workspace.broker.folders()))
        identifier=code.prepare_export(folder.id,'reviewed.zip')['export_id']; self.client.handle('/review '+identifier)
        self.client.handle('Follow up')
        self.assertNotIn('\x1b',self.output.getvalue()); self.assertIn('\\u001b',self.output.getvalue())
        with self.assertRaises(AccessDenied): self.client.handle('/approve '+identifier)

    def test_permission_change_closes_disposable_workspace(self):
        self.client.handle('/draft '+str(self.dest)); self.client.handle('/code'); code=self.host.code
        folder=next(iter(self.backend.workspace.broker.folders()))
        self.client.handle('/revoke '+folder.id)
        self.assertIsNone(self.host.code); self.assertTrue(code.closed)

    def test_keyboard_cancel_reaches_host_and_drains_request(self):
        entered=threading.Event(); release=threading.Event()
        def ask(prompt): entered.set(); release.wait(3); return AgentResult('late',(),(),1,0)
        self.host.ask=ask
        original_cancel=self.host.cancel
        def cancel(): original_cancel(); release.set()
        self.host.cancel=cancel
        original_join=threading.Thread.join; first=[True]
        def join(thread,timeout=None):
            if first[0]:
                first[0]=False; self.assertTrue(entered.wait(2)); raise KeyboardInterrupt
            return original_join(thread,timeout)
        with patch('threading.Thread.join',join): self.client.ask('Start')
        self.assertTrue(self.host.cancelled); self.assertNotIn('late',self.output.getvalue())
        self.assertIn('Cancelled',self.output.getvalue())


if __name__=='__main__': unittest.main()
