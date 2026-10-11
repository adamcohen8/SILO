"""Live transport, display isolation, granted completion and recovery contracts."""
import asyncio
import copy
import io
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from local_ai_appliance.agent import AgentResult
from local_ai_appliance.backend import SessionCancelled, WindowsSessionAdapter
from local_ai_appliance.contracts import Progress, Project, WorkspaceKind
from local_ai_appliance.display_events import DisplayEvents
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.model import AgentError, LocalChatModel, json_bytes
from local_ai_appliance.model_stream import ChatStream
from local_ai_appliance.terminal_rich import markdown, table, width
from local_ai_appliance.workspace import Workspace


def event(delta, finish=None):
    return b'data: ' + json_bytes({'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}]}) + b'\n\n'


class StreamTests(unittest.TestCase):
    def test_arbitrary_utf8_boundaries_hide_reasoning_and_assemble_calls_before_parse(self):
        text = []; stream = ChatStream(text.append, limit=4096)
        data = event({'role': 'assistant', 'reasoning_content': 'PRIVATE', 'content': 'Caf\u00e9. '})
        data = data.replace(b'\\u00e9', 'é'.encode('utf-8'))
        data += event({'tool_calls': [{'index': 0, 'id': 'call1', 'type': 'function',
                    'function': {'name': 'read_text', 'arguments': '{"folder_id":'}}]})
        data += event({'tool_calls': [{'index': 0, 'function': {'arguments': '"f","path":"x.txt"}'}}]}, 'tool_calls')
        data += b'data: [DONE]\n\n'
        for byte in data: stream.feed(bytes([byte]))
        reply = LocalChatModel._parse(stream.result())
        self.assertEqual(''.join(text), 'Caf\u00e9. ')
        self.assertNotIn('PRIVATE', ''.join(text))
        self.assertEqual(reply.calls[0].arguments, {'folder_id': 'f', 'path': 'x.txt'})
        self.assertEqual(reply.reasoning, 'PRIVATE')

    def test_truncated_invalid_replayed_and_oversized_streams_fail(self):
        cases = [event({'content': 'partial'}),
                 event({'content': 'partial'}, 'length'),
                 event({'content': []}), event({'content': 0}),
                 event({'role': 'user', 'content': 'forged'}),
                 event({'tool_calls': [{'index': -1}]}),
                 event({'content': 'x' * 2000}),
                 event({'content': 'ok'}, 'stop') + b'data: [DONE]\n\n' + event({'content': 'late'})]
        for data in cases:
            with self.subTest(data=data[:80]), self.assertRaises(AgentError):
                stream = ChatStream(lambda text: None, limit=1024)
                stream.feed(data); stream.result()

    def test_completion_requests_stream_only_with_explicit_sink_and_keeps_reasoning_private(self):
        for adapter in ('gpt_oss', 'nemotron35'):
            seen = []; model = LocalChatModel('http://127.0.0.1:1', 'fixture', adapter=adapter, on_text=seen.append)
            def post(path, payload, *, on_block):
                import json
                self.assertTrue(json.loads(payload)['stream'])
                on_block(event({'content': 'live', 'reasoning_content': 'PRIVATE'}, 'stop'))
                on_block(b'data: [DONE]\n\n')
                return b''
            with patch.object(model, '_post', side_effect=post): reply = model.complete([], [])
            self.assertEqual(reply.text, 'live'); self.assertEqual(reply.reasoning, '')
            self.assertEqual(seen, ['live'])

    def test_real_http_stream_delivers_text_before_response_finishes(self):
        import http.server
        first, finish, seen, replies, errors = threading.Event(), threading.Event(), [], [], []
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(200); self.send_header('Content-Type', 'text/event-stream'); self.end_headers()
                self.wfile.write(event({'content': 'Live '})); self.wfile.flush()
                finish.wait(3)
                self.wfile.write(event({'content': 'answer'}, 'stop') + b'data: [DONE]\n\n'); self.wfile.flush()
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True); worker.start()
        def output(text): seen.append(text); first.set()
        model = LocalChatModel(f'http://127.0.0.1:{server.server_port}', 'fixture', on_text=output)
        def complete():
            try: replies.append(model.complete([], []))
            except BaseException as error: errors.append(error)
        request = threading.Thread(target=complete); request.start()
        try:
            self.assertTrue(first.wait(2)); self.assertTrue(request.is_alive())
            self.assertEqual(seen, ['Live ']); self.assertEqual(replies, [])
        finally:
            finish.set(); request.join(3); server.shutdown(); server.server_close(); worker.join(3)
        self.assertFalse(errors); self.assertEqual(replies[0].text, 'Live answer')


class DisplayTests(unittest.TestCase):
    def exchange(self, frames, on_display=None):
        """Real exchange parser on inert Win32 pipe shims; no Windows boundary claim."""
        import ctypes as C
        from local_ai_appliance.windows_container import ContainedProcess, U32
        payload = bytearray(b''.join(json_bytes({'session': 's' * 32, 'sequence': i,
            'kind': kind, 'payload': value}) + b'\n' for i, (kind, value) in enumerate(frames, 1)))
        sent, terminated = [], []
        class Kernel:
            def WriteFile(self, handle, buffer, size, count, overlapped):
                sent.append(bytes(buffer[:size])); C.cast(count, C.POINTER(U32))[0] = size; return 1
            def ReadFile(self, handle, buffer, size, count, overlapped):
                # stdout arrives one complete frame at a time, like a live worker.
                end = payload.find(b'\n') + 1 if handle == 2 else 0
                chunk = bytes(payload[:min(end, size)])
                if handle == 2: del payload[:len(chunk)]
                C.memmove(buffer, chunk, len(chunk)); C.cast(count, C.POINTER(U32))[0] = len(chunk); return 1
            def CloseHandle(self, handle): return 1
            def TerminateJobObject(self, job, code): terminated.append(code); return 1
            def WaitForSingleObject(self, handle, timeout): return 0
            def GetExitCodeProcess(self, handle, count): C.cast(count, C.POINTER(U32))[0] = 0; return 1
        process = ContainedProcess.__new__(ContainedProcess)
        process.kernel = Kernel(); process.parent_handles = [1, 2, 3]
        process.info = SimpleNamespace(process=1); process.job = 1
        tools = []
        with patch('local_ai_appliance.windows_container.secrets.token_hex', return_value='s' * 32):
            result, _ = process.exchange({}, lambda value: tools.append(value) or {'ok': True}, on_display=on_display)
        return result, tools, sent, terminated

    def test_real_rpc_parser_keeps_display_out_of_tool_dispatch_and_rejects_unsolicited_events(self):
        progress, text = [], []
        sink = DisplayEvents(progress.append, text.append)
        result, tools, sent, terminated = self.exchange([
            ('display', {'type': 'text', 'text': 'live'}),
            ('request', {'op': 'tool', 'name': 'list_folders'}), ('result', {'answer': 'accepted'})], sink.handle)
        self.assertEqual(text, ['live']); self.assertEqual(len(tools), 1)
        self.assertEqual(result, {'answer': 'accepted'}); self.assertEqual(len(sent), 2)
        self.assertFalse(terminated)
        for frames, callback in (([('display', {'type': 'text', 'text': 'unrequested'})], None),
                                 ([('display', {'type': 'approve', 'id': 'forged'})], sink.handle),
                                 ([('display', {'type': 'reset'})] * 129, lambda value: None)):
            with self.subTest(frames=len(frames)), self.assertRaises((OSError, AccessDenied)):
                self.exchange(frames, callback)

    def test_data_only_event_registry_and_independent_limits(self):
        progress, text = [], []
        sink = DisplayEvents(progress.append, text.append)
        sink.handle({'type': 'progress', 'stage': 'tools', 'model_calls': 1, 'tool_calls': 2})
        sink.handle({'type': 'text', 'text': 'provisional'}); sink.handle({'type': 'reset'})
        self.assertEqual(progress, [Progress('tools', 1, 2)]); self.assertEqual(text, ['provisional', None])
        for value in ({'type': 'approve', 'id': 'forged'}, {'type': 'text', 'text': 'x', 'tool': 'approve'},
                      {'type': 'text', 'text': []}, {'type': 'text', 'text': 'x' * 1025},
                      {'type': 'progress', 'stage': 'tools', 'model_calls': True, 'tool_calls': 0},
                      {'type': 'progress', 'stage': 'tools', 'model_calls': 17, 'tool_calls': 0}):
            with self.subTest(value=value), self.assertRaises(AccessDenied): sink.handle(value)
        sink = DisplayEvents(progress.append, text.append)
        for _ in range(64): sink.handle({'type': 'text', 'text': 'x' * 1024})
        with self.assertRaises(AccessDenied): sink.handle({'type': 'text', 'text': 'x'})
        sink = DisplayEvents(progress.append, text.append)
        for _ in range(128): sink.handle({'type': 'reset'})
        with self.assertRaises(AccessDenied): sink.handle({'type': 'reset'})

    def test_worker_display_frames_are_bounded_and_sequence_bound(self):
        import importlib.util
        path = Path(__file__).resolve().parents[1] / 'scripts/contained_agent_worker.py'
        spec = importlib.util.spec_from_file_location('live_worker_fixture', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        channel = module.Channel.__new__(module.Channel); channel.session = 'test'; channel.sequence = 1
        data = io.BytesIO()
        with patch.object(module.sys, 'stdout', SimpleNamespace(buffer=data)):
            live = module.LiveOutput(channel)
            for _ in range(1000): live.text('x' * 256)
            live.flush()
        import json
        frames = [json.loads(line) for line in data.getvalue().splitlines()]
        self.assertLessEqual(len(frames), 128)
        self.assertEqual([f['sequence'] for f in frames], list(range(1, len(frames) + 1)))
        self.assertTrue(all(f['kind'] == 'display' and f['session'] == 'test' for f in frames))


class RenderingTests(unittest.TestCase):
    def test_markdown_tables_code_citations_and_controls(self):
        rows = markdown('# Heading\n**Bold** and `code` [source:S1:line:2]\n'
                        '| Item | Value |\n| --- | --- |\n| Mass | 108 kg |\n'
                        '```python\nif mass == 108: # checked\n    print("108 kg")\n```\n\x1b[2J\u202e', columns=50)
        text = '\n'.join(row.text for row in rows)
        self.assertIn('108 kg', text); self.assertIn('[source:S1:line:2]', text)
        self.assertNotIn('\x1b', text); self.assertIn('\\u001b', text)
        self.assertEqual(rows[0].tone, 'bold')
        self.assertTrue(any(style == 'class:keyword' for row in rows for style, _ in row.spans))
        self.assertTrue(any(row.tone == 'table' for row in rows))
        for columns in (40, 80):
            self.assertTrue(all(width(row) <= columns for row in table(['File', 'Value'], [['Long name ' * 8, '108 kg']], columns=columns)))


@unittest.skipUnless(__import__('os').name == 'posix', 'Inert POSIX grant identity fixture')
class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.folder = self.root / 'Reference'; self.folder.mkdir()
        class Service:
            made = []
            def __init__(self, root, *, model_manager=None):
                self.root, self.model_manager = root, model_manager
                self.workspace = Workspace(); self.instructions = 'Retain instructions'
                self.closed = False; self.ready = True; self.cleanup_fails = False
                self.code = None; self.conversation = SimpleNamespace(clear=lambda: None)
                self.made.append(self)
            def start(self, progress): progress('loading')
            def clear_chat(self):
                for proposal in self.workspace.pending_proposals(): self.workspace.discard(proposal.id)
            def cancel(self): self.ready = False
            def close(self):
                if self.cleanup_fails: raise OSError('Inert cleanup failure')
                self.closed = True; self.workspace.close()
            def ask(self, prompt, **sinks):
                if sinks:
                    sinks['on_progress'](Progress('tools', 1, 1)); sinks['on_text']('provisional')
                return AgentResult('accepted', (), (), 1, 1)
        self.Service = Service
        self.old = Service(self.root)
        self.backend = WindowsSessionAdapter(Project('fixture', 'Fixture'), self.old)
        self.addCleanup(self.backend.close)
        self.backend.grant(self.folder, WorkspaceKind.REFERENCE)

    def test_display_sinks_follow_adapter_and_recovery_rechecks_folder_identity(self):
        text, progress = [], []
        self.backend.set_display_sinks(progress.append, text.append)
        self.assertEqual(self.backend.ask('synthetic').answer, 'accepted')
        self.assertEqual(text, ['provisional']); self.assertIn('tools', [p.stage for p in progress])
        self.backend.cancel(); self.backend.recover()
        self.assertTrue(self.old.closed); self.assertIsNot(self.backend.service, self.old)
        self.assertEqual(self.backend.service.instructions, 'Retain instructions')
        self.assertEqual(len(self.backend.workspace.broker.folders()), 1)
        self.assertFalse(self.backend._cancelled.is_set())

    def test_changed_folder_is_omitted_and_cleanup_failure_cannot_launch_replacement(self):
        self.folder.rename(self.root / 'old'); self.folder.mkdir()
        self.backend.cancel(); self.backend.recover()
        self.assertFalse(self.backend.workspace.broker.folders())
        self.assertEqual(self.backend._recovery_grants_omitted, 1)
        current = self.backend.service; current.cleanup_fails = True
        self.backend.cancel(); made = len(self.Service.made)
        try:
            with self.assertRaises(OSError): self.backend.recover()
            self.assertEqual(len(self.Service.made), made)
        finally: current.cleanup_fails = False

    def test_cancellation_during_recovery_stops_new_service(self):
        original = self.Service.start
        def cancel_during_start(service, progress):
            original(service, progress); self.backend.cancel()
        self.backend.cancel()
        with patch.object(self.Service, 'start', cancel_during_start):
            with self.assertRaises(SessionCancelled): self.backend.recover()
        self.assertTrue(self.backend.service.closed)
        self.assertTrue(self.backend._cancelled.is_set())

    def test_recovery_reserves_private_trees_before_regranting(self):
        self.backend.cancel()
        original = self.Service.start
        def start(service, progress):
            original(service, progress)
            broker = service.workspace.broker
            reserved = []
            broker.reserve_tree = reserved.append
            grant = broker.grant
            def checked(path, *args, **kwargs):
                if Path(path) in reserved: raise AccessDenied('Reserved storage')
                return grant(path, *args, **kwargs)
            broker.grant = checked
        with patch.object(self.Service, 'start', start):
            self.backend.recover(reserved_paths=[self.folder])
        self.assertFalse(self.backend.workspace.broker.folders())
        self.assertEqual(self.backend._recovery_grants_omitted, 1)


try:
    from prompt_toolkit.document import Document
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    from prompt_toolkit.completion import CompleteEvent
    from local_ai_appliance.terminal_completion import SiloCompleter
    from local_ai_appliance.terminal_fullscreen import FullScreenPreview
    TERMINAL = True
except ImportError:
    TERMINAL = False


@unittest.skipUnless(TERMINAL, 'Terminal extra required')
class CompletionTests(unittest.TestCase):
    def test_command_and_quoted_granted_mentions_never_read_outside_grants(self):
        from local_ai_appliance.mentions import Mention
        completer = SiloCompleter()
        completer.mentions = (Mention('Reference', 'f', 'mass study.txt', 'file'),)
        values = lambda text: list(completer.get_completions(Document(text), CompleteEvent()))
        self.assertIn('/hardware', [c.text for c in values('/hard')])
        self.assertEqual([c.text for c in values('Read @mass')], ['@"Reference/mass study.txt"'])
        completer.valid = lambda: False
        self.assertEqual(values('Read @mass'), [])
        completer.choices = (('1', 'switch', 'Switch model'),)
        self.assertEqual([c.text for c in values('1')], ['switch'])


@unittest.skipUnless(TERMINAL, 'Terminal extra required')
class ScreenTests(unittest.IsolatedAsyncioTestCase):
    async def wait_for(self, predicate):
        async with asyncio.timeout(4):
            while not predicate(): await asyncio.sleep(.01)

    async def screen(self, pipe, host=None):
        screen = FullScreenPreview(input=pipe, output=DummyOutput(), backend=host, plain=True, delay=.5)
        task = asyncio.create_task(screen.app.run_async(pre_run=screen.start))
        await self.wait_for(lambda: screen.app.renderer.last_rendered_screen is not None)
        async def stop():
            if not task.done(): screen.close()
            await asyncio.wait_for(task, 4)
        self.addAsyncCleanup(stop)
        return screen, task

    async def test_busy_composer_preserves_next_message_and_scroll_anchor(self):
        with create_pipe_input() as pipe:
            screen, _ = await self.screen(pipe)
            pipe.send_text('/example\r'); await self.wait_for(lambda: screen.busy)
            pipe.send_text('Next question'); await self.wait_for(lambda: screen.composer.text == 'Next question')
            pipe.send_text('\r'); await asyncio.sleep(.05)
            self.assertEqual(screen.composer.text, 'Next question')
            for i in range(60): screen._append(f'line {i}', 'body')
            screen.follow = False; screen.transcript.buffer.cursor_position = 30
            screen._append('New output', 'body')
            self.assertEqual(screen.transcript.buffer.cursor_position, 30)
            pipe.send_text('\x03'); await self.wait_for(lambda: not screen.busy)
            self.assertEqual(screen.composer.text, 'Next question')

    async def test_enter_accepts_completion_before_dispatch(self):
        with create_pipe_input() as pipe:
            screen, _ = await self.screen(pipe)
            pipe.send_text('/exa\t'); await self.wait_for(lambda: screen.composer.buffer.complete_state is not None)
            pipe.send_text('\r'); await asyncio.sleep(.1)
            self.assertEqual(screen.composer.text, '/example')
            self.assertFalse(screen.busy)

    def rendered_text(self, screen):
        rendered = screen.app.renderer.last_rendered_screen
        size = screen.app.output.get_size()
        return '\n'.join(''.join(rendered.data_buffer[y][x].char for x in range(size.columns))
                         for y in range(size.rows))

    async def test_typing_shows_visible_filtered_menu_and_escape_preserves_input(self):
        with create_pipe_input() as pipe:
            screen, _ = await self.screen(pipe)
            pipe.send_text('/ex')
            await self.wait_for(lambda: self.rendered_text(screen).count('/example') == 2)
            self.assertEqual(screen.composer.text, '/ex')
            self.assertFalse(screen.busy)
            pipe.send_text('\x1b')
            await self.wait_for(lambda: screen.composer.buffer.complete_state is None)
            self.assertEqual(screen.composer.text, '/ex')
            await self.wait_for(lambda: self.rendered_text(screen).count('/example') == 1)
            pipe.send_text('a')
            await self.wait_for(lambda: screen.composer.buffer.complete_state is not None)
            pipe.send_text('\x1b\r')
            await self.wait_for(lambda: screen.composer.text == '/exa\n')
            self.assertFalse(screen.busy)

    async def test_visible_menu_arrow_selection_and_tab_completion_do_not_submit(self):
        with create_pipe_input() as pipe:
            screen, _ = await self.screen(pipe)
            pipe.send_text('/f')
            await self.wait_for(lambda: '/folders' in self.rendered_text(screen)
                                and '/format' in self.rendered_text(screen))
            pipe.send_text('\x1b[B')
            await self.wait_for(lambda: screen.composer.buffer.complete_state.current_completion is not None)
            self.assertEqual(screen.composer.text, '/format')
            pipe.send_text('\x1b[B')
            await self.wait_for(lambda: screen.composer.text == '/folders')
            pipe.send_text('\r')
            await self.wait_for(lambda: screen.composer.buffer.complete_state is None)
            self.assertEqual(screen.composer.text, '/folders')
            self.assertFalse(screen.busy)
            screen.composer.buffer.set_document(Document('/he', 3))
            pipe.send_text('\t')
            await self.wait_for(lambda: screen.composer.text == '/help')
            self.assertFalse(screen.busy)

    async def test_live_progress_and_cancel_recover_without_losing_composed_input(self):
        class Host:
            project = SimpleNamespace(name='Fixture')
            workspace = SimpleNamespace(pending_proposals=lambda: ())
            conversation = SimpleNamespace(display=lambda: ())
            def __init__(self):
                self.release = threading.Event(); self.recovered = False
            def set_display_sinks(self, progress, text): self.progress, self.text = progress, text
            def ask(self, prompt):
                self.progress(Progress('model', 0, 0)); self.text('Unvalidated\x1b[2J')
                self.release.wait(3)
                raise SessionCancelled('Cancelled')
            def cancel(self): self.release.set()
            def recover(self): self.recovered = True
        with create_pipe_input() as pipe:
            host = Host(); screen, _ = await self.screen(pipe, host)
            pipe.send_text('Start\r'); await self.wait_for(lambda: bool(screen.live_text))
            self.assertIn('Unvalidated', screen.live_text); self.assertNotIn('\x1b', screen.live_text)
            self.assertNotIn('Unvalidated', screen.transcript.text)
            pipe.send_text('Next\x03'); await self.wait_for(lambda: not screen.busy)
            self.assertTrue(host.recovered); self.assertEqual(screen.state, 'Ready')
            self.assertEqual(screen.composer.text, 'Next'); self.assertFalse(screen.live_text)
            self.assertNotIn('Unvalidated', screen.transcript.text)
