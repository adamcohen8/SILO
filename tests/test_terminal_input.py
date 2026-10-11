"""Scrolling terminal input works with redirected streams and keeps console keys."""
import io
import sys
import threading
import unittest
from unittest.mock import Mock, patch

from local_ai_appliance.terminal_client import TerminalClient
from local_ai_appliance.terminal_ui import TerminalView


class Stream(io.StringIO):
    def __init__(self, text='', *, tty=False):
        super().__init__(text)
        self.tty = tty

    def isatty(self):
        return self.tty


class TerminalInputTests(unittest.TestCase):
    def client(self):
        client = TerminalClient(Mock(), view=TerminalView(io.StringIO(), plain=True),
                                update_manager=Mock(stop=threading.Event()))
        client.start_update_checks = Mock()
        client.handle = Mock(return_value=False)
        return client

    def test_redirected_stream_uses_builtin_input_without_console_prompt(self):
        for input_tty, output_tty in ((False, False), (False, True), (True, False)):
            with self.subTest(input_tty=input_tty, output_tty=output_tty):
                client = self.client()
                with patch.object(sys, 'stdin', Stream('/quit\n', tty=input_tty)), \
                     patch.object(sys, 'stdout', Stream(tty=output_tty)), \
                     patch('prompt_toolkit.PromptSession') as prompt:
                    client.interact()
                prompt.assert_not_called()
                client.handle.assert_called_once_with('/quit')
                client.start_update_checks.assert_called_once_with(notify=True)

    def test_console_keeps_prompt_session_and_update_key_binding(self):
        client = self.client()
        with patch.object(sys, 'stdin', Stream(tty=True)), \
             patch.object(sys, 'stdout', Stream(tty=True)), \
             patch('prompt_toolkit.PromptSession') as prompt:
            prompt.return_value.prompt.return_value = '/quit'
            client.interact()
        prompt.assert_called_once()
        self.assertTrue(any(binding.keys == ('c-u',)
                            for binding in prompt.call_args.kwargs['key_bindings'].bindings))
        client.handle.assert_called_once_with('/quit')
        client.start_update_checks.assert_called_once_with(notify=False)


if __name__ == '__main__':
    unittest.main()
