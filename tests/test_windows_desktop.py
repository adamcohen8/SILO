"""Native Qt authority tests; scripted replies never claim model qualification."""
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PySide6.QtWidgets import QApplication, QMessageBox, QLabel
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    from local_ai_appliance.agent import AgentResult, Source
    from local_ai_appliance.windows_desktop import WindowsAssistantWindow, configure_fonts
    from local_ai_appliance.windows_folders import WindowsFolderBroker
    from local_ai_appliance.workspace import Workspace
    from local_ai_appliance.windows_workspace import BrokerSession
    from local_ai_appliance.model import json_bytes
    from local_ai_appliance.conversation import Conversation
    from local_ai_appliance.folder_settings import FolderSettings
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

ROOT = Path(__file__).resolve().parents[1]


class Service:
    def __init__(self):
        self.workspace = Workspace(WindowsFolderBroker(validation_mode=True))
        self.ready, self.closed = True, False
        self.evidence = {}
        self.conversation = Conversation()

    def clear_chat(self):
        self.conversation.clear()
        for proposal in self.workspace.pending_proposals():
            self.workspace.discard(proposal.id)

    def cancel(self):
        self.ready = False
        self.conversation.clear()

    def close(self):
        self.conversation.clear()
        self.workspace.close()
        self.closed = True


@unittest.skipUnless(os.name == 'nt' and QT_AVAILABLE, 'Native Windows and optional Qt dependencies required')
class WindowsDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        configure_fonts(cls.app)
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'artifacts/windows-ui', prefix='qt-test-')
        self.root = Path(self.temp.name)
        self.reference, self.drafts = self.root/'Reference', self.root/'Drafts'
        self.reference.mkdir()
        self.drafts.mkdir()
        (self.reference/'source.txt').write_text('Original synthetic text.\n', encoding='utf-8')
        self.window = WindowsAssistantWindow(ROOT, Service(), autostart=False)
        self.window.show()
        self.window.grant(str(self.reference), 'read-only')
        self.window.grant(str(self.drafts), 'editable')
        self.folders = {f.name: f for f in self.window.workspace.broker.folders()}

    def idle(self):
        started = time.monotonic()
        self.app.processEvents()
        while self.window.busy or self.window.jobs:
            self.app.processEvents()
            time.sleep(.005)
            if time.monotonic()-started > 10:
                self.fail('GUI operation did not finish: '+self.window.status.text())

    def tearDown(self):
        self.window.close()
        started = time.monotonic()
        while not self.window.cleaned or self.window.jobs:
            self.app.processEvents()
            time.sleep(.005)
            if time.monotonic()-started > 10:
                self.fail('Close cleanup timed out')
        self.assertTrue(self.window.cleaned)
        self.temp.cleanup()

    def test_review_exact_save_and_single_use(self):
        workspace = self.window.workspace
        proposal = workspace.propose(self.folders['Drafts'].id, 'new.md', 'Reviewed synthetic copy.\n')
        self.window.show_answer(AgentResult('Unsaved draft.', (), (proposal,), 1, 1))
        self.window.controls()
        self.window.review_draft_button.click()
        dialog = self.window.review_dialog
        self.assertFalse((self.drafts/'new.md').exists())
        self.assertFalse(dialog.save_button.isEnabled())
        dialog.review_button.click(); self.idle()
        identifier = dialog.reviewed.id
        dialog.save_button.click(); self.idle()
        self.assertEqual((self.drafts/'new.md').read_bytes(), proposal.text.encode())
        from local_ai_appliance.folders import AccessDenied
        with self.assertRaises(AccessDenied):
            workspace.approve(identifier)

    def test_agents_button_opens_fixed_file_in_external_text_editor(self):
        with patch('local_ai_appliance.windows_desktop.subprocess.Popen') as launch:
            self.window.agents_button.click()
            args = launch.call_args.args[0]
            self.assertEqual(Path(args[0]).name, 'notepad.exe')
            self.assertEqual(Path(args[1]), ROOT/'AGENTS.md')
            self.assertEqual(len(args), 2)
            self.assertNotIn('shell', launch.call_args.kwargs)
            self.assertIn('restart the model', self.window.status.text())
        self.assertTrue(self.window.restart_button.isEnabled())
        self.window.busy = True
        self.window.controls()
        self.assertFalse(self.window.restart_button.isEnabled())
        self.assertTrue(self.window.agents_button.isEnabled())
        self.window.busy = False
        self.window.controls()

    def test_editor_launch_error_is_visible(self):
        with patch('local_ai_appliance.windows_desktop.subprocess.Popen', side_effect=OSError('test')):
            self.window.agents_button.click()
        self.assertIn('Could not open Notepad', self.window.status.text())

    def test_revoke_clears_stale_answers_and_proposals(self):
        self.window.workspace.propose(self.folders['Drafts'].id, 'new.md', 'Synthetic draft.')
        self.window.answer.setPlainText('Previously read synthetic answer.')
        self.window.revoke(self.folders['Reference'].id)
        self.assertFalse(self.window.answer.toPlainText())
        self.assertFalse(self.window.workspace.pending_proposals())

    def test_source_change_denies_save(self):
        workspace = self.window.workspace
        source = workspace.open_source(self.folders['Reference'].id, 'source.txt')
        proposal = workspace.propose(self.folders['Drafts'].id, 'new.md', 'Revised.\n', source)
        (self.reference/'source.txt').write_text('External change.\n')
        from local_ai_appliance.folders import AccessDenied
        with self.assertRaisesRegex(AccessDenied, 'Source changed'):
            workspace.approve(proposal.id)
        self.assertFalse((self.drafts/'new.md').exists())

    def test_existing_destination_is_preserved(self):
        (self.drafts/'new.md').write_bytes(b'Existing.\n')
        from local_ai_appliance.folders import AccessDenied
        with self.assertRaises(AccessDenied):
            self.window.workspace.propose(self.folders['Drafts'].id, 'new.md', 'Replacement.\n')
        self.assertEqual((self.drafts/'new.md').read_bytes(), b'Existing.\n')

    def test_markup_is_plain_and_multiple_proposals_need_review(self):
        w = self.window
        first = w.workspace.propose(self.folders['Drafts'].id, 'one.md', '<img src="https://example.invalid">')
        second = w.workspace.propose(self.folders['Drafts'].id, 'two.md', 'Another draft.')
        source = Source('S1', self.folders['Reference'].id, '<b>source.txt</b>', '0'*64, 1, 1,
                        '<script>not code</script>', cited_start=1, cited_end=1)
        w.show_answer(AgentResult('<b>answer</b> [source:S1:line:1]', (source,), (first, second), 1, 1))
        self.assertIn('<b>answer</b> [source:S1:line:1]', w.answer.toPlainText())
        self.assertEqual(w.excerpt.toPlainText(), '<script>not code</script>')
        self.assertIn('<img src="https://example.invalid">', w.answer.toPlainText())
        self.assertIn('Another draft.', w.answer.toPlainText())
        self.assertTrue(w.answer.isReadOnly())
        self.assertEqual(len(w.workspace.pending_proposals()), 2)
        self.assertEqual(w.drafts.count(), 2)
        self.assertEqual(list(self.drafts.iterdir()), [])

    def test_background_task_disables_authority_and_handles_failure(self):
        def slow(progress):
            time.sleep(.2)
            raise RuntimeError('Synthetic rejection')
        self.window.run_task(slow, lambda value: self.fail('Unexpected success'))
        self.assertFalse(self.window.read_zone.isEnabled())
        self.app.processEvents()
        self.idle()
        self.assertEqual(self.window.status.text(), 'Synthetic rejection')
        self.assertTrue(self.window.read_zone.isEnabled())

    def test_picker_project_folder_requires_confirmed_replacement(self):
        w = self.window
        revision = w.workspace.broker.revision
        with patch('local_ai_appliance.desktop.QFileDialog.getExistingDirectory', return_value=str(ROOT)):
            w.read_zone._pick()
        self.assertEqual(w.workspace.broker.revision, revision)
        self.assertEqual(w.read_zone.list.count(), 1)
        self.assertEqual(w.edit_zone.list.count(), 1)
        self.assertIn('overlaps', w.folder_notice.text())
        self.assertEqual(w.folder_notice.textFormat(), Qt.TextFormat.PlainText)
        replace = next(button for button in w.folder_notice.buttons() if button.text() == 'Replace folder access')
        replace.click()
        self.app.processEvents()
        self.assertEqual(w.read_zone.list.count(), 1)
        self.assertEqual(w.edit_zone.list.count(), 0)
        self.assertEqual(w.read_zone.list.currentItem().text(), ROOT.name)
        self.assertEqual(w.browser_title.text(), ROOT.name)
        self.assertEqual(len(w.workspace.broker.folders()), 1)
        self.assertEqual(w.workspace.broker.folders()[0].access, 'read-only')

    def test_overlap_cancel_preserves_existing_grants_and_pending_draft(self):
        proposal = self.window.workspace.propose(self.folders['Drafts'].id, 'new.md', 'Synthetic draft.')
        pending = proposal.id
        revision = self.window.workspace.broker.revision
        self.window.grant(str(ROOT), 'read-only')
        self.window.folder_notice.button(QMessageBox.StandardButton.Cancel).click()
        self.app.processEvents()
        self.assertEqual(self.window.workspace.broker.revision, revision)
        self.assertIn(pending, {p.id for p in self.window.workspace.pending_proposals()})

    def test_folder_rejection_is_visible_and_adds_no_authority(self):
        revision = self.window.workspace.broker.revision
        self.window.grant('C:/', 'read-only')
        self.assertEqual(self.window.workspace.broker.revision, revision)
        self.assertEqual(self.window.folder_notice.windowTitle(), 'Folder could not be added')
        self.assertTrue(self.window.folder_notice.isVisible())
        self.window.folder_notice.button(QMessageBox.StandardButton.Ok).click()

    def test_inventory_contains_children_without_reading_document_contents(self):
        nested = self.reference/'nested'
        nested.mkdir()
        (nested/'README.md').write_text('Private fixture content must not be preloaded.\n')
        with patch.object(self.window.workspace, 'open_text', side_effect=AssertionError('Inventory read file contents')):
            preview = BrokerSession(self.window.workspace).inventory()
        reference = next(p for p in preview if p['folder_id'] == self.folders['Reference'].id)
        self.assertIn({'name': 'nested', 'kind': 'directory'}, reference['entries'])
        self.assertNotIn('Private fixture content', json_bytes(preview).decode())
        result = BrokerSession(self.window.workspace).handle({'op': 'tool', 'name': 'read_text',
            'arguments': {'folder_id': self.folders['Reference'].id, 'path': 'nested/README.md'}})
        self.assertTrue(result['ok'])
        self.assertIn('Private fixture content', result['value']['result']['text'])

    def test_inventory_is_bounded_and_refreshed_after_revocation(self):
        for i in range(35):
            (self.reference/('fixture-'+str(i)+'.txt')).write_text('Synthetic.\n')
        session = BrokerSession(self.window.workspace)
        preview = session.inventory(max_bytes=400)
        self.assertLessEqual(len(json_bytes(preview)), 400)
        self.assertTrue(preview[0]['truncated'])
        revoked = self.folders['Reference'].id
        self.window.revoke(revoked)
        self.assertNotIn(revoked, [p['folder_id'] for p in BrokerSession(self.window.workspace).inventory()])

    def test_wrapper_inventory_exposes_docs_path_without_reading_files(self):
        wrapper = self.drafts/'project'
        docs = wrapper/'docs'
        docs.mkdir(parents=True)
        (docs/'guide.md').write_text('Contents must not be preloaded.\n', encoding='utf-8')
        with patch.object(self.window.workspace.broker, 'read_file', side_effect=AssertionError('Read file')):
            session = BrokerSession(self.window.workspace)
            preview = session.inventory()
            project = next(p for p in preview if p['folder_id'] == self.folders['Drafts'].id and p['path'] == 'project')
            self.assertEqual(project['entries'], [{'name': 'docs', 'kind': 'directory'}])
            result = session.handle({'op': 'tool', 'name': 'list_files',
                'arguments': {'folder_id': self.folders['Drafts'].id, 'path': 'project/docs'}})
        self.assertTrue(result['ok'])
        listing = result['value']['result']
        self.assertEqual(listing['path'], 'project/docs')
        self.assertEqual(listing['entries'], [{'name': 'guide.md', 'kind': 'file'}])
        self.assertFalse(listing['truncated'])
        self.assertNotIn('Contents must not be preloaded', json_bytes(preview).decode())
        self.assertEqual(session.validate({'answer': 'project/docs: guide.md', 'references': [], 'proposal_ids': []}), ())

    def test_wrapper_inventory_depth_is_bounded(self):
        nested = self.drafts
        for _ in range(8):
            nested /= 'nested'
            nested.mkdir()
        preview = BrokerSession(self.window.workspace).inventory()
        paths = [p['path'] for p in preview if p['folder_id'] == self.folders['Drafts'].id]
        self.assertEqual(paths, ['', 'nested', 'nested/nested', 'nested/nested/nested'])

    def test_clear_chat_clears_memory_transcript_and_pending_drafts_without_restarting(self):
        w = self.window
        folders = tuple(w.workspace.broker.folders())
        session = w.session
        w.session.conversation.append('Remember ORION-27.', 'Noted.', (), w.workspace.broker.revision)
        w.show_answer(AgentResult('Noted.', (), (), 1, 0, conversation=w.session.conversation.display()))
        self.assertIn('You\nRemember ORION-27.', w.answer.toPlainText())
        w.workspace.propose(self.folders['Drafts'].id, 'pending.md', 'Synthetic pending text.')
        w.prompt.setPlainText('Follow-up text')
        w.clear_chat_button.click()
        self.assertEqual(w.session.conversation.display(), ())
        self.assertFalse(w.answer.toPlainText())
        self.assertFalse(w.prompt.toPlainText())
        self.assertFalse(w.workspace.pending_proposals())
        self.assertIs(w.session, session)
        self.assertTrue(session.ready)
        self.assertEqual(tuple(w.workspace.broker.folders()), folders)

    def test_chat_clear_is_disabled_during_a_request(self):
        self.window.run_task(lambda progress: time.sleep(.1), lambda result: None)
        self.assertFalse(self.window.clear_chat_button.isEnabled())
        self.idle()
        self.assertTrue(self.window.clear_chat_button.isEnabled())

    def test_chat_composer_enter_sends_and_shift_enter_adds_newline(self):
        composer = self.window.prompt
        sent = []
        composer.submitted.disconnect(self.window.ask)
        composer.submitted.connect(lambda: sent.append(composer.toPlainText()))
        composer.setPlainText('First line')
        QTest.keyClick(composer, Qt.Key.Key_End)
        QTest.keyClick(composer, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(composer.toPlainText(), 'First line\n')
        QTest.keyClick(composer, Qt.Key.Key_Return)
        self.assertEqual(sent, ['First line\n'])

    def test_chat_bubbles_preserve_roles_and_display_markup_literally(self):
        payload = '<img src="https://example.com/beacon"><script>alert(1)</script>'
        self.window.answer.set_conversation((('Summarize this.', payload), ('Follow-up?', 'Second reply.')))
        self.app.processEvents()
        self.assertEqual(self.window.answer._messages, [('user', 'Summarize this.'), ('assistant', payload),
                                                      ('user', 'Follow-up?'), ('assistant', 'Second reply.')])
        content = next(child for child in self.window.answer.body.findChildren(QLabel) if child.text() == payload)
        self.assertEqual(content.textFormat(), Qt.TextFormat.PlainText)
        self.assertTrue(self.window.answer.isReadOnly())

    def reopen(self, settings, before_open=None):
        self.window.close()
        started = time.monotonic()
        while not self.window.cleaned or self.window.jobs:
            self.app.processEvents()
            time.sleep(.005)
            self.assertLess(time.monotonic()-started, 10)
        if before_open:
            before_open()
        self.window = WindowsAssistantWindow(ROOT, Service(), autostart=False, folder_settings=settings)
        self.window.show()
        self.window.model_ready(None)
        self.app.processEvents()

    def remember_folders(self):
        settings = FolderSettings(self.root/'folders.json')
        self.window.folder_settings = settings
        self.assertTrue(self.window.save_folders())
        return settings

    def test_reopen_restores_folder_access_with_fresh_ids_and_empty_chat(self):
        settings = self.remember_folders()
        previous = {folder.id for folder in self.window.workspace.broker.folders()}
        self.window.session.conversation.append('Fictional message.', 'Fictional answer.', (), 0)
        self.reopen(settings)
        folders = {folder.name: folder for folder in self.window.workspace.broker.folders()}
        self.assertEqual({name: folder.access for name, folder in folders.items()},
                         {'Reference': 'read-only', 'Drafts': 'editable'})
        self.assertFalse(previous & {folder.id for folder in folders.values()})
        self.assertEqual(self.window.read_zone.list.count(), 1)
        self.assertEqual(self.window.edit_zone.list.count(), 1)
        self.assertEqual(self.window.workspace.broker.read_file(folders['Reference'].id, 'source.txt'),
                         (self.reference/'source.txt').read_bytes())
        self.assertFalse(self.window.session.conversation.turns)
        self.assertNotIn('Fictional', settings.path.read_text())

    def test_removed_folder_does_not_return_after_reopen(self):
        settings = self.remember_folders()
        self.window.revoke(self.folders['Drafts'].id)
        self.reopen(settings)
        self.assertEqual([f.name for f in self.window.workspace.broker.folders()], ['Reference'])
        self.assertEqual(self.window.edit_zone.list.count(), 0)

    def test_replaced_directory_is_skipped_without_restoring_access(self):
        settings = self.remember_folders()
        def replace_directory():
            self.reference.rename(self.root/'original-reference')
            self.reference.mkdir()
            (self.reference/'source.txt').write_bytes(b'Replacement directory.\n')
        self.reopen(settings, replace_directory)
        self.assertEqual([f.name for f in self.window.workspace.broker.folders()], ['Drafts'])
        self.assertIn('1 unavailable or changed', self.window.status.text())
        self.assertEqual(self.window.read_zone.list.count(), 0)

    def test_invalid_folder_settings_grant_nothing_and_report_problem(self):
        settings = self.remember_folders()
        settings.path.write_text('{"version":1,"folders":[{"path":"https://example.com"}]}', encoding='utf-8')
        self.reopen(settings)
        self.assertEqual(self.window.workspace.broker.folders(), [])
        self.assertIn('could not be loaded', self.window.status.text())

    def test_failed_first_message_stays_visible_with_the_actual_error(self):
        w = self.window
        w.prompt.setPlainText('Find the radio bandwidth.')
        with patch.object(w.session, 'ask', create=True, side_effect=RuntimeError('The request exceeded its context limits.')):
            w.ask_button.click()
            self.idle()
        self.assertIn('You\nFind the radio bandwidth.', w.answer.toPlainText())
        self.assertIn('The request exceeded its context limits.', w.answer.toPlainText())
        self.assertEqual(w.prompt.toPlainText(), 'Find the radio bandwidth.')
        self.assertFalse(w.session.conversation.turns)
        self.assertIsNone(w.last_result)

    def test_failed_follow_up_preserves_prior_memory_and_clears_stale_result(self):
        w = self.window
        w.session.conversation.append('Earlier question.', 'Earlier answer.', (), w.workspace.broker.revision)
        previous = w.session.conversation.display()
        w.show_answer(AgentResult('Earlier answer.', (), (), 1, 0, conversation=previous))
        w.prompt.setPlainText('A failed follow-up.')
        with patch.object(w.session, 'ask', create=True, side_effect=RuntimeError('Synthetic failed request.')):
            w.ask_button.click()
            self.idle()
        self.assertEqual(w.session.conversation.display(), previous)
        self.assertIn('Earlier answer.', w.answer.toPlainText())
        self.assertIn('Synthetic failed request.', w.answer.toPlainText())
        self.assertIsNone(w.last_result)

    def test_folder_and_file_autocomplete_keyboard_and_mouse_selection(self):
        w = self.window
        sent = []
        w.prompt.submitted.disconnect(w.ask)
        w.prompt.submitted.connect(lambda: sent.append(w.prompt.toPlainText()))
        w.prompt.setFocus()
        w.prompt.setPlainText('List /')
        QTest.keyClick(w.prompt, Qt.Key.Key_End)
        self.idle()
        self.assertTrue(w.prompt.popup.isVisible())
        original_row = w.prompt.popup.currentRow()
        QTest.keyClick(w.prompt, Qt.Key.Key_Down)
        self.assertNotEqual(w.prompt.popup.currentRow(), original_row)
        self.assertEqual(w.prompt.toPlainText(), 'List /')
        row = next(i for i in range(w.prompt.popup.count()) if w.prompt.popup.item(i).text() == '/Reference')
        w.prompt.popup.setCurrentRow(row)
        QTest.keyClick(w.prompt, Qt.Key.Key_Tab)
        self.assertEqual(w.prompt.toPlainText(), 'List /Reference ')
        self.assertFalse(sent)
        w.prompt.setPlainText('Summarize @so')
        QTest.keyClick(w.prompt, Qt.Key.Key_End)
        self.app.processEvents()
        self.assertTrue(w.prompt.popup.isVisible())
        self.assertEqual(w.prompt.popup.count(), 1)
        item = w.prompt.popup.item(0)
        QTest.mouseClick(w.prompt.popup.viewport(), Qt.MouseButton.LeftButton,
                         pos=w.prompt.popup.visualItemRect(item).center())
        self.assertEqual(w.prompt.toPlainText(), 'Summarize @Reference/source.txt ')

    def test_quoted_file_completion_after_emoji_and_revocation_refresh(self):
        w = self.window
        (self.reference/'Radio specs.pdf').write_bytes(b'Metadata fixture only.')
        w.prompt.setFocus()
        w.prompt.setPlainText('😀 Summarize @Rad')
        QTest.keyClick(w.prompt, Qt.Key.Key_End)
        self.idle()
        self.assertTrue(w.prompt.popup.isVisible())
        QTest.keyClick(w.prompt, Qt.Key.Key_Return)
        self.assertEqual(w.prompt.toPlainText(), '😀 Summarize @"Reference/Radio specs.pdf" ')
        w.prompt.setPlainText('@')
        QTest.keyClick(w.prompt, Qt.Key.Key_End)
        self.app.processEvents()
        self.assertTrue(w.prompt.popup.isVisible())
        w.revoke(self.folders['Reference'].id)
        self.idle()
        self.assertFalse(w.prompt.popup.isVisible())
        self.assertTrue(w.prompt.catalog is None or not w.prompt.catalog.suggestions('@', ''))
