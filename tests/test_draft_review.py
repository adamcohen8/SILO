import os
from pathlib import Path
import tempfile
import unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtWidgets import QApplication, QWidget
    from local_ai_appliance.draft_review import DraftReview
    from local_ai_appliance.desktop import label
    QT_AVAILABLE=True
except ImportError:
    QT_AVAILABLE=False
from local_ai_appliance.workspace import Workspace
from local_ai_appliance.folders import AccessDenied
import json


if QT_AVAILABLE:
    class Host(QWidget):
        def __init__(self,workspace):
            super().__init__()
            self.workspace=workspace
            self.busy=self.closing=False
            self.status=label('Ready')
        def run_task(self,operation,done,*,failure=None):
            self.busy=True
            try:
                result=operation(lambda text:None)
            except (AccessDenied,RuntimeError) as error:
                self.busy=False
                self.status.setText(str(error))
                if failure: failure()
            else:
                self.busy=False
                done(result)
        def refresh_files(self): pass
        def invalidate_mentions(self): pass


@unittest.skipUnless(QT_AVAILABLE and os.name=='posix','Optional Qt and POSIX broker required')
class DraftReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.ro,self.rw=self.root/'Reference',self.root/'Drafts'
        self.ro.mkdir(); self.rw.mkdir()
        (self.ro/'source.txt').write_bytes(b'Original synthetic text.\n')
        self.workspace=Workspace()
        self.addCleanup(self.workspace.close)
        self.reference=self.workspace.grant(self.ro,'read-only')
        self.destination=self.workspace.grant(self.rw,'editable')
        self.host=Host(self.workspace)
        self.addCleanup(self.host.close)
        source=self.workspace.open_source(self.reference.id,'source.txt')
        proposal=self.workspace.propose(self.destination.id,'new.md','Reviewed synthetic copy.\n',source)
        self.dialog=DraftReview(self.host,proposal)
        self.addCleanup(self.dialog.reject)
        self.dialog.show()
    def test_model_proposal_is_not_review_or_save_and_exact_bytes_single_use(self):
        d=self.dialog
        self.assertFalse(d.save_button.isEnabled())
        self.assertFalse(self.workspace.pending_proposals())
        self.assertFalse((self.rw/'new.md').exists())
        d.review_button.click()
        identifier=d.reviewed.id
        self.assertIn('Original synthetic text.',d.diff.toPlainText())
        self.assertIn('Reviewed synthetic copy.',d.diff.toPlainText())
        self.assertTrue(d.save_button.isEnabled())
        d.save_button.click()
        self.assertEqual((self.rw/'new.md').read_bytes(),b'Reviewed synthetic copy.\n')
        self.assertEqual((self.ro/'source.txt').read_bytes(),b'Original synthetic text.\n')
        with self.assertRaises(AccessDenied): self.workspace.approve(identifier)
    def test_editing_text_filename_or_destination_invalidates_review(self):
        d=self.dialog
        d.review()
        d.text.setPlainText('Changed after review.')
        self.assertFalse(d.save_button.isEnabled())
        self.assertFalse(self.workspace.pending_proposals())
        d.review(); d.filename.setText('another.md')
        self.assertFalse(d.save_button.isEnabled())
        other=self.root/'Other';other.mkdir()
        folder=self.workspace.grant(other,'editable')
        d.destination.addItem('Other',folder.id)
        d.review();d.destination.setCurrentIndex(1)
        self.assertFalse(d.save_button.isEnabled())
        self.assertFalse(list(self.rw.iterdir()))
    def test_source_changes_between_review_and_save_preserve_all_files(self):
        d=self.dialog; d.review()
        (self.ro/'source.txt').write_text('External change.')
        d.save()
        self.assertFalse((self.rw/'new.md').exists())
        self.assertIn('Source changed',d.notice.text())
        self.assertFalse(d.save_button.isEnabled())
    def test_revocation_or_read_only_destination_denies_save(self):
        d=self.dialog; d.review()
        self.workspace.revoke(self.destination.id)
        d.save()
        self.assertFalse((self.rw/'new.md').exists())
        self.assertFalse(d.save_button.isEnabled())
    def test_destination_collision_after_review_is_preserved(self):
        d=self.dialog;d.review()
        (self.rw/'new.md').write_text('Existing document')
        d.save()
        self.assertEqual((self.rw/'new.md').read_text(),'Existing document')
        self.assertFalse(d.save_button.isEnabled())
    def test_cancel_plain_text_and_busy_controls(self):
        d=self.dialog
        d.text.setPlainText('<img src="https://example.invalid">')
        d.review()
        self.assertIn('<img src=',d.diff.toPlainText())
        self.assertTrue(d.diff.isReadOnly())
        d.controls(True); d.reject()
        self.assertIsNotNone(d.reviewed)
        d.controls(False); d.reject()
        self.assertFalse(self.workspace.pending_proposals())
        self.assertFalse(list(self.rw.iterdir()))


@unittest.skipUnless(QT_AVAILABLE and os.name=='posix','Optional Qt and POSIX broker required')
class ArtifactReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        from local_ai_appliance.draft_review import ArtifactReview
        from local_ai_appliance.agent import Source
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.ro,self.rw=self.root/'Reference',self.root/'Drafts'
        self.ro.mkdir();self.rw.mkdir()
        (self.ro/'source.txt').write_text('Capacity is 108 kg.')
        self.workspace=Workspace();self.addCleanup(self.workspace.close)
        reference=self.workspace.grant(self.ro,'read-only')
        self.destination=self.workspace.grant(self.rw,'editable')
        document=self.workspace.open_source(reference.id,'source.txt')
        source=Source('S1',reference.id,'source.txt',document.sha256,1,1,document.text)
        content=json.dumps({'title':'Report','sections':[{'heading':'Capacity','paragraphs':['108 kg. [source:S1]']}]})
        self.proposal=self.workspace.propose_artifact(self.destination.id,'report.docx',content,[source])
        self.host=Host(self.workspace);self.addCleanup(self.host.close)
        self.dialog=ArtifactReview(self.host,self.proposal);self.addCleanup(self.dialog.reject)

    def test_exact_review_save_and_single_use(self):
        self.dialog.save();self.assertFalse((self.rw/'report.docx').exists())
        self.dialog.review();self.assertTrue(self.dialog.save_button.isEnabled())
        self.dialog.save()
        self.assertEqual((self.rw/'report.docx').read_bytes(),self.proposal.data)
        with self.assertRaises(AccessDenied):self.workspace.approve(self.proposal.id)

    def test_source_change_between_review_and_save_is_rejected(self):
        self.dialog.review();(self.ro/'source.txt').write_text('Changed')
        self.dialog.save()
        self.assertFalse((self.rw/'report.docx').exists())
        self.assertIn('Source changed',self.dialog.notice.text())

    def test_collision_and_revocation_preserve_destination(self):
        self.dialog.review();(self.rw/'report.docx').write_bytes(b'Existing')
        self.dialog.save();self.assertEqual((self.rw/'report.docx').read_bytes(),b'Existing')
        self.workspace.revoke(self.destination.id);self.dialog.review()
        self.assertFalse(self.dialog.save_button.isEnabled())

    def test_clear_and_closing_invalidate_or_block_review(self):
        self.host.closing=True;self.dialog.review();self.assertFalse(self.dialog.reviewed)
        self.host.closing=False;self.dialog.review();self.dialog.invalidate()
        self.assertFalse(self.workspace.pending_proposals());self.assertFalse(self.dialog.save_button.isEnabled())
        self.dialog.save();self.assertFalse((self.rw/'report.docx').exists())


if __name__=='__main__': unittest.main()
