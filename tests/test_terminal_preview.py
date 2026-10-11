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


if __name__ == '__main__':
    unittest.main()
