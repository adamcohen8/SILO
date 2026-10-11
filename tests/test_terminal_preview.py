"""Presentation trust boundary and preview review-state regression checks."""
from dataclasses import replace
import io
import unittest

from local_ai_appliance.terminal_demo import DemoSession, EXAMPLE
from local_ai_appliance.terminal_ui import TerminalView, literal


class TerminalPreviewTests(unittest.TestCase):
    def make_demo(self, width=40):
        output = io.StringIO()
        return DemoSession(TerminalView(output, plain=True, width=width), delay=0), output

    def test_terminal_controls_are_literal_and_narrow_content_remains_visible(self):
        demo, output = self.make_demo()
        hostile = 'policy\x1b[2J\r\x07\u202e.txt'
        demo.view.answer(hostile)
        self.assertNotIn('\x1b', output.getvalue())
        self.assertNotIn('\u202e', output.getvalue())
        self.assertIn('\\u001b[2J\\u000d\\u0007\\u202e', literal(hostile))
        output.seek(0)
        output.truncate()
        demo.ask(EXAMPLE)
        demo.handle('/review D1')
        self.assertTrue(all(len(line) <= 40 for line in output.getvalue().splitlines()))
        self.assertIn('[source:S1:line:1-2]', output.getvalue())

    def test_model_unicode_is_visible_in_legacy_and_utf8_streams(self):
        for encoding in ('ascii', 'cp1252', 'utf-8'):
            with self.subTest(encoding=encoding):
                data = io.BytesIO()
                output = io.TextIOWrapper(data, encoding=encoding, errors='strict')
                view = TerminalView(output, plain=True, width=40)
                answer = '37\u202fcrates \U0001f989 [source:S1:line:2] \x1b[2J'
                view.answer(answer)
                output.flush()
                rendered = data.getvalue().decode(encoding)
                self.assertIn('[source:S1:line:2]', rendered)
                self.assertNotIn('\x1b', rendered)
                self.assertIn('\\u001b[2J', rendered)
                self.assertTrue(all(len(line) <= 40 for line in rendered.splitlines()))
                self.assertIn('37\u202fcrates' if encoding == 'utf-8' else '37\\u202fcrates', rendered)
                self.assertIn('\U0001f989' if encoding == 'utf-8' else '\\U0001f989', rendered)
                output.detach()

    def test_approval_requires_current_review_and_is_only_simulated(self):
        demo, output = self.make_demo()
        demo.ask(EXAMPLE)
        demo.handle('/approve D1')
        self.assertIn('D1', demo.pending)
        demo.handle('/review D1')
        original = demo.pending['D1']
        demo.pending['D1'] = replace(original, text='Changed after review')
        demo.handle('/approve D1')
        self.assertIn('D1', demo.pending)
        demo.handle('/review D1')
        demo.handle('/approve D1')
        self.assertFalse(demo.pending)
        self.assertIn('Simulated approval complete.', output.getvalue())

    def test_new_request_and_clear_invalidate_review(self):
        demo, _ = self.make_demo()
        demo.ask(EXAMPLE)
        demo.handle('/review D1')
        demo.ask(EXAMPLE)
        demo.handle('/approve D1')
        self.assertIn('D1', demo.pending)
        demo.handle('/clear')
        self.assertFalse(demo.pending)
        self.assertFalse(demo.reviewed)
        self.assertFalse(demo.has_sources)

    def test_model_menu_uses_source_profiles_and_only_selects_in_memory(self):
        demo, output = self.make_demo(width=100)
        demo.ask(EXAMPLE)
        draft = demo.pending['D1']
        demo.handle('/model')
        self.assertEqual(demo.model_menu.pending, ('action', ('switch', 'install', 'remove')))
        for label in ('1. Switch', '2. Install', '3. Remove'): self.assertIn(label, output.getvalue())
        demo.handle('99')
        self.assertIsNotNone(demo.model_menu.pending)
        demo.handle('2')
        self.assertEqual(demo.model_menu.pending[0], 'install')
        self.assertEqual(len(demo.model_menu.pending[1]), 7)
        self.assertIn('Nemotron Cascade 2', output.getvalue())
        self.assertIn('Nemotron 3.5 Lightning', output.getvalue())
        demo.handle('1')
        self.assertIn(demo.model_menu.profiles[0]['id'], demo.model_menu.installed)
        demo.handle('/model switch')
        demo.handle('1')
        self.assertIsNone(demo.model_menu.pending)
        self.assertEqual(demo.model_menu.selected, demo.model_menu.profiles[0]['id'])
        self.assertEqual(demo.pending['D1'], draft)
        self.assertIn('No weights were loaded', output.getvalue())

    def test_model_menu_cancel_and_unavailable_operations_keep_selection_unchanged(self):
        demo, output = self.make_demo(width=100)
        original = demo.model_menu.selected
        demo.handle('/model switch')
        demo.handle('/cancel')
        self.assertIsNone(demo.model_menu.pending)
        demo.handle('/model import fixture path')
        self.assertEqual(demo.model_menu.selected, original)
        self.assertIsNone(demo.model_menu.pending)
        self.assertIn('require the contained Windows application', output.getvalue())
        demo.handle('/model remove')
        demo.handle('1')
        self.assertEqual(demo.model_menu.pending, ('confirm', (original,)))
        demo.handle('no')
        self.assertIn(original, demo.model_menu.installed)
        demo.handle('/model remove '+original)
        demo.handle('yes')
        self.assertNotIn(original, demo.model_menu.installed)
        self.assertIsNone(demo.model_menu.selected)
        demo.handle('/model switch')
        self.assertIsNone(demo.model_menu.pending)
        demo.handle('/model install '+original)
        demo.handle('/model switch '+original)
        self.assertEqual(demo.model_menu.selected, original)
        self.assertIn('No model files were deleted', output.getvalue())


if __name__ == '__main__':
    unittest.main()
