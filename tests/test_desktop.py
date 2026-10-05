import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
    from PySide6.QtGui import QDragEnterEvent, QDropEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from local_ai_appliance.desktop import WorkspaceWindow, local_drop_paths
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False


@unittest.skipUnless(QT_AVAILABLE and os.name == "posix", "Install the optional UI dependencies on POSIX")
class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.ro = self.base / "reference"
        self.rw = self.base / "drafts"
        self.ro.mkdir()
        self.rw.mkdir()
        (self.ro / "source.md").write_text("Original text.\n")
        self.window = WorkspaceWindow()
        self.window.show()
        self.application.processEvents()

    def tearDown(self):
        self.window.close()
        self.application.processEvents()
        self.temp.cleanup()

    def load_source(self):
        self.window.add_folder(str(self.ro), "read-only")
        self.window.add_folder(str(self.rw), "editable")
        folder = self.window.workspace.broker.folders()[0]
        self.window.select_folder(folder.id)
        self.window.open_entry(self.window.files.item(0))
        return folder

    def test_empty_start_and_disabled_save(self):
        self.assertEqual(self.window.workspace.broker.folders(), [])
        self.assertEqual(self.window.destination.count(), 0)
        self.assertFalse(self.window.save.isEnabled())

    def test_folder_picker_grants_selected_category(self):
        with patch("local_ai_appliance.desktop.QFileDialog.getExistingDirectory", return_value=str(self.ro)):
            self.window.read_only._pick()
        folders = self.window.workspace.broker.folders()
        self.assertEqual(len(folders), 1)
        self.assertEqual(folders[0].access, "read-only")
        self.assertEqual(self.window.destination.count(), 0)

    def test_native_drop_grants_only_local_folder(self):
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(self.rw))])
        enter = QDragEnterEvent(self.window.editable.rect().center(), Qt.DropAction.CopyAction, mime,
                               Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.application.sendEvent(self.window.editable, enter)
        self.assertTrue(enter.isAccepted())
        drop = QDropEvent(QPointF(self.window.editable.rect().center()), Qt.DropAction.CopyAction, mime,
                          Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.application.sendEvent(self.window.editable, drop)
        self.assertTrue(drop.isAccepted())
        self.assertEqual(self.window.workspace.broker.folders()[0].access, "editable")

    def test_remote_or_mixed_drops_denied(self):
        for urls in ([QUrl("https://example.com/folder")],
                     [QUrl.fromLocalFile(str(self.ro)), QUrl("https://example.com")],
                     [QUrl("file://server/share")],
                     [QUrl.fromLocalFile(str(self.ro / "source.md"))]):
            mime = QMimeData()
            mime.setUrls(urls)
            self.assertEqual(local_drop_paths(mime), [])
        self.assertEqual(self.window.workspace.broker.folders(), [])

    def test_review_save_flow_preserves_source(self):
        self.load_source()
        self.window.draft.setPlainText("Reviewed revision.\n")
        QTest.mouseClick(self.window.review, Qt.MouseButton.LeftButton)
        self.assertTrue(self.window.save.isEnabled())
        self.assertIn("+Reviewed revision.", self.window.diff_view.toPlainText())
        self.assertFalse((self.rw / "source-revised.md").exists())
        QTest.mouseClick(self.window.save, Qt.MouseButton.LeftButton)
        self.assertEqual((self.rw / "source-revised.md").read_text(), "Reviewed revision.\n")
        self.assertEqual((self.ro / "source.md").read_text(), "Original text.\n")
        self.assertFalse(self.window.save.isEnabled())

    def test_changing_text_or_destination_invalidates_review(self):
        self.load_source()
        self.window.review_draft()
        self.assertTrue(self.window.save.isEnabled())
        self.window.draft.setPlainText("changed after review")
        self.assertFalse(self.window.save.isEnabled())
        self.assertIsNone(self.window.proposal)
        self.window.review_draft()
        self.window.filename.setText("different.md")
        self.assertFalse(self.window.save.isEnabled())
        self.assertEqual(list(self.rw.iterdir()), [])

    def test_revocation_clears_loaded_content_and_proposal(self):
        folder = self.load_source()
        self.window.review_draft()
        self.window.revoke_folder(folder.id)
        self.assertEqual(self.window.source_view.toPlainText(), "")
        self.assertEqual(self.window.draft.toPlainText(), "")
        self.assertEqual(self.window.diff_view.toPlainText(), "")
        self.assertFalse(self.window.save.isEnabled())
        self.assertIsNone(self.window.source)

    def test_markup_is_displayed_literally(self):
        self.load_source()
        payload = '<img src="https://example.com/beacon"><script>alert(1)</script>'
        self.window.draft.setPlainText(payload)
        self.window.review_draft()
        self.assertIn(payload, self.window.diff_view.toPlainText())
        self.assertEqual(self.window.draft.toPlainText(), payload)

    def test_source_changed_after_review_reports_error_without_save(self):
        self.load_source()
        self.window.review_draft()
        (self.ro / "source.md").write_text("Updated original")
        self.window.save_reviewed()
        self.assertIn("Source changed", self.window.status.text())
        self.assertEqual(list(self.rw.iterdir()), [])
        self.assertFalse(self.window.save.isEnabled())


if __name__ == "__main__":
    unittest.main()
