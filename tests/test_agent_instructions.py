import os
from pathlib import Path
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from local_ai_appliance.agent_instructions import load_instructions, MAX_INSTRUCTIONS_BYTES


class AgentInstructionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root/'AGENTS.md'

    def tearDown(self):
        self.temp.cleanup()

    def test_utf8_bom_and_empty_configuration(self):
        self.path.write_bytes(b'\xef\xbb\xbfUse concise answers with units.\n')
        self.assertEqual(load_instructions(self.root), 'Use concise answers with units.\n')
        self.path.write_bytes(b'')
        self.assertEqual(load_instructions(self.root), '')

    def test_missing_oversized_and_invalid_text_have_actionable_errors(self):
        with self.assertRaisesRegex(RuntimeError, 'Cannot read AGENTS.md'):
            load_instructions(self.root)
        for data, message in ((b'x'*(MAX_INSTRUCTIONS_BYTES+1), 'exceeds 8 KiB'),
                              (b'\xff', 'UTF-8'), (b'bad\x00text', 'plain UTF-8')):
            with self.subTest(message=message):
                self.path.write_bytes(data)
                with self.assertRaisesRegex(RuntimeError, message):
                    load_instructions(self.root)

    @unittest.skipUnless(os.name == 'nt', 'Native Windows session required')
    def test_startup_snapshot_is_forwarded_until_next_initialization(self):
        from local_ai_appliance.windows_session import WindowsSession
        from local_ai_appliance.windows_folders import WindowsFolderBroker
        from local_ai_appliance.workspace import Workspace
        from local_ai_appliance.conversation import Conversation

        # Stop just before asset verification; no GPU/container is started.
        session = WindowsSession.__new__(WindowsSession)
        session.root = self.root
        session.installation = None
        session.model_profile = None
        session._operation, session._guard = threading.RLock(), threading.RLock()
        session.verify_assets = Mock(side_effect=RuntimeError('asset test stop'))
        session.close = Mock()
        self.path.write_text('Use metric units.', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'asset test stop'):
            session.start()
        self.path.write_text('Use a comparison table.', encoding='utf-8')

        session.ready, session.closed = True, False
        session.cancelled = threading.Event()
        session.drain = SimpleNamespace(failed=threading.Event())
        session.workspace = Workspace(WindowsFolderBroker(validation_mode=True))
        session.conversation = Conversation()
        session.container = Mock()
        session.executable, session.worker = self.root/'python.exe', self.root/'worker.py'
        session.endpoint, session.token = self.root/'test.sock', 'synthetic-token'
        session.evidence = {'worker_tokens': []}
        process = session.container.launch.return_value
        process.exchange.return_value = ({'answer': 'Synthetic response.', 'references': [],
            'proposal_ids': [], 'model_calls': 1, 'tool_calls': 0, 'tracing_enabled': False}, None)
        try:
            session.ask('Hello')
            initial = process.exchange.call_args.args[0]
            self.assertEqual(initial['instructions'], 'Use metric units.')
            self.assertEqual(initial['folders'], [])
            process.close.assert_called_once()
            with self.assertRaisesRegex(RuntimeError, 'asset test stop'):
                session.start()
            self.assertEqual(session.instructions, 'Use a comparison table.')
        finally:
            session.workspace.close()
