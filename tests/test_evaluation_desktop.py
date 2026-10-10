"""Actual Qt host/save integration with scripted replies and public fixtures."""
import os
from pathlib import Path
import tempfile
import time
import unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtWidgets import QApplication
    from local_ai_appliance.windows_desktop import WindowsAssistantWindow
    from local_ai_appliance.agent import AgentResult
    from local_ai_appliance.workspace import Workspace
    from local_ai_appliance.conversation import Conversation
    QT_AVAILABLE=True
except ImportError:
    QT_AVAILABLE=False

ROOT=Path(__file__).resolve().parents[1]


class Service:
    def __init__(self):
        self.workspace=Workspace()
        self.ready=True;self.closed=False
        self.conversation=Conversation()
    def clear_chat(self):
        self.conversation.clear()
        for proposal in self.workspace.pending_proposals(): self.workspace.discard(proposal.id)
    def cancel(self): self.ready=False
    def close(self): self.workspace.close();self.closed=True


@unittest.skipUnless(QT_AVAILABLE and os.name=='posix','Optional Qt and POSIX test adapter required')
class EvaluationDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name).resolve()
        self.ro,self.rw=self.root/'Reference',self.root/'Drafts'
        self.ro.mkdir();self.rw.mkdir()
        (self.ro/'source.txt').write_text('Original synthetic text.\n')
        self.window=WindowsAssistantWindow(ROOT,Service(),autostart=False)
        self.window.show()
        self.window.grant(str(self.ro),'read-only');self.window.grant(str(self.rw),'editable')
        self.folders={f.name:f for f in self.window.workspace.broker.folders()}
    def idle(self):
        end=time.monotonic()+10
        self.app.processEvents()
        while self.window.busy or self.window.jobs:
            if time.monotonic()>end: self.fail('Background operation did not finish.')
            self.app.processEvents();time.sleep(.005)
    def tearDown(self):
        self.window.close()
        self.idle()
        self.app.processEvents()
        self.temp.cleanup()
    def draft(self, name='new.md'):
        source=self.window.workspace.open_source(self.folders['Reference'].id,'source.txt')
        proposal=self.window.workspace.propose(self.folders['Drafts'].id,name,'Synthetic reviewed draft.\n',source)
        self.window.show_answer(AgentResult('Unsaved draft.',(),(proposal,),1,1))
        self.window.controls()
        return proposal
    def test_actual_window_async_review_save_receipt_and_clear(self):
        self.assertTrue(self.window.windowTitle().startswith('SILO'))
        self.assertFalse(self.window.windowIcon().pixmap(32,32).isNull())
        self.draft()
        self.window.review_draft_button.click()
        dialog=self.window.review_dialog
        self.assertIn(str(self.ro),dialog.source_notice.text())
        self.assertIn(str(self.rw),dialog.destination_notice.text())
        self.assertFalse(dialog.save_button.isEnabled())
        dialog.review_button.click()
        self.assertTrue(self.window.busy)
        self.assertFalse(self.window.ask_button.isEnabled())
        self.idle()
        self.assertTrue(dialog.save_button.isEnabled())
        dialog.save_button.click();self.idle()
        self.assertEqual((self.rw/'new.md').read_bytes(),b'Synthetic reviewed draft.\n')
        self.assertIn('Saved new copy',self.window.status.text())
        self.assertEqual(self.window.drafts.count(),0)
        self.assertFalse(self.window.workspace.pending_proposals())
    def test_revocation_closes_review_and_erases_pending_authority(self):
        self.draft();self.window.open_draft_review()
        dialog=self.window.review_dialog
        dialog.review();self.idle()
        self.window.revoke(self.folders['Reference'].id)
        self.assertIsNone(self.window.review_dialog)
        self.assertFalse(self.window.workspace.pending_proposals())
        self.assertFalse(list(self.rw.iterdir()))
    def test_unreturned_or_stale_proposal_cannot_be_approved_from_window(self):
        proposal=self.draft()
        self.window.workspace.discard(proposal.id)
        self.window.open_draft_review()
        self.assertIsNone(self.window.review_dialog)
        self.assertIn('no longer available',self.window.status.text())
        self.assertFalse(list(self.rw.iterdir()))


if __name__=='__main__': unittest.main()
