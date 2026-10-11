"""Exercise the actual full-screen event loop, layout, editing, and cancellation."""
import asyncio
import unittest

try:
    from prompt_toolkit.data_structures import Size
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    from local_ai_appliance.terminal_fullscreen import FullScreenPreview
    AVAILABLE = True
except ModuleNotFoundError:
    AVAILABLE = False


if AVAILABLE:
    class SizedOutput(DummyOutput):
        size = Size(rows=24, columns=80)

        def get_size(self):
            return self.size


@unittest.skipUnless(AVAILABLE, 'Terminal preview extra required')
class FullScreenTests(unittest.IsolatedAsyncioTestCase):
    async def wait_for(self, predicate):
        async with asyncio.timeout(3):
            while not predicate():
                await asyncio.sleep(0.01)

    async def start_preview(self, pipe, output, delay=0):
        preview = FullScreenPreview(input=pipe, output=output, delay=delay, plain=True)
        task = asyncio.create_task(preview.app.run_async(pre_run=preview.start))
        await self.wait_for(lambda: preview.app.renderer.last_rendered_screen is not None)
        self.addAsyncCleanup(self.stop_preview, preview, task)
        return preview, task

    async def stop_preview(self, preview, task):
        if not task.done():
            preview.close()
        await asyncio.wait_for(task, 3)

    def screen_lines(self, preview):
        screen = preview.app.renderer.last_rendered_screen
        size = preview.app.output.get_size()
        return [''.join(screen.data_buffer[y][x].char for x in range(size.columns)).rstrip()
                for y in range(size.rows)]

    async def test_fills_window_and_reflows_on_resize_with_fixed_composer(self):
        with create_pipe_input() as pipe:
            output = SizedOutput()
            preview, _ = await self.start_preview(pipe, output)
            lines = self.screen_lines(preview)
            self.assertIn('SILO', lines[0])
            self.assertIn('Ctrl+D', lines[-1])
            self.assertIn('Message SILO', '\n'.join(lines[-7:]))
            output.size = Size(rows=38, columns=110)
            preview.app.invalidate()
            await asyncio.sleep(0.1)
            lines = self.screen_lines(preview)
            self.assertEqual(len(lines), 38)
            self.assertIn('Ctrl+D', lines[-1])
            self.assertIn('Message SILO', '\n'.join(lines[-7:]))
            output.size = Size(rows=20, columns=40)
            preview.app.invalidate()
            await asyncio.sleep(0.1)
            lines = self.screen_lines(preview)
            self.assertIn('SILO', lines[0])
            self.assertIn('Ctrl+D', lines[-1])
            self.assertNotIn('Window too small', '\n'.join(lines))

    async def test_preview_model_command_menu_selection_and_cancel_are_visible(self):
        with create_pipe_input() as pipe:
            preview, _ = await self.start_preview(pipe, SizedOutput())
            pipe.send_text('/model\r')
            await self.wait_for(lambda: preview.demo.model_menu.pending is not None and not preview.busy)
            self.assertTrue(preview.completer.choices)
            self.assertIn('No model is installed or running', preview.transcript.text)
            pipe.send_text('1\r')
            await self.wait_for(lambda: preview.demo.model_menu.selected is not None and not preview.busy)
            self.assertIn('No weights were loaded', preview.transcript.text)
            pipe.send_text('/model\r')
            await self.wait_for(lambda: preview.demo.model_menu.pending is not None and not preview.busy)
            pipe.send_text('\x03')
            await self.wait_for(lambda: preview.demo.model_menu.pending is None)
            self.assertFalse(preview.completer.choices)
            self.assertEqual(preview.state, 'Model menu closed')

    async def test_commands_review_and_scrolling_keep_input_focus(self):
        with create_pipe_input() as pipe:
            preview, _ = await self.start_preview(pipe, SizedOutput())
            pipe.send_text('/example\r')
            await self.wait_for(lambda: 'D1' in preview.demo.pending and not preview.busy)
            pipe.send_text('/review D1\r')
            await self.wait_for(lambda: 'D1' in preview.demo.reviewed and not preview.busy)
            await asyncio.sleep(0.1)
            old_cursor = preview.transcript.buffer.cursor_position
            pipe.send_text('\x1b[5~')
            await asyncio.sleep(0.1)
            self.assertLess(preview.transcript.buffer.cursor_position, old_cursor)
            self.assertTrue(preview.app.layout.has_focus(preview.composer))
            pipe.send_text('/approve D1\r')
            await self.wait_for(lambda: not preview.demo.pending and not preview.busy)
            self.assertIn('Simulated approval complete.', preview.transcript.text)
            pipe.send_text('/clear\r')
            await self.wait_for(lambda: preview.state == 'Conversation cleared')
            await asyncio.sleep(0.05)
            self.assertNotIn('108 kg', preview.transcript.text)

    async def test_cancellation_discards_draft_and_next_request_recovers(self):
        with create_pipe_input() as pipe:
            preview, _ = await self.start_preview(pipe, SizedOutput(), delay=0.5)
            pipe.send_text('/example\r')
            await self.wait_for(lambda: preview.busy)
            pipe.send_text('\x03')
            await self.wait_for(lambda: not preview.busy)
            self.assertEqual(preview.state, 'Cancelled')
            self.assertFalse(preview.demo.pending)
            preview.demo.delay = 0
            pipe.send_text('/example\r')
            await self.wait_for(lambda: 'D1' in preview.demo.pending and not preview.busy)

    async def test_multiline_and_controls_are_displayed_literally(self):
        with create_pipe_input() as pipe:
            preview, _ = await self.start_preview(pipe, SizedOutput())
            pipe.send_text('first\x1b\rsecond')
            await self.wait_for(lambda: preview.composer.text == 'first\nsecond')
            pipe.send_text('\r')
            await self.wait_for(lambda: 'first\n  second' in preview.transcript.text and not preview.busy)
            preview.view.answer('source\x1b[2J\u202e')
            await self.wait_for(lambda: '\\u001b[2J\\u202e' in preview.transcript.text)

    async def test_quit_during_work_joins_cancelled_request(self):
        with create_pipe_input() as pipe:
            preview, task = await self.start_preview(pipe, SizedOutput(), delay=0.5)
            pipe.send_text('/example\r')
            await self.wait_for(lambda: preview.busy)
            pipe.send_text('\x04')
            await self.wait_for(task.done)
            self.assertFalse(preview.busy)
            self.assertFalse(preview.demo.pending)


@unittest.skipUnless(AVAILABLE, 'Terminal extra required')
class ProductionScreenTests(unittest.IsolatedAsyncioTestCase):
    wait_for = FullScreenTests.wait_for
    stop_preview = FullScreenTests.stop_preview
    screen_lines = FullScreenTests.screen_lines
    """Real controller and event loop with an inert host backend, not inference."""
    def backend(self):
        import threading
        from types import SimpleNamespace
        from local_ai_appliance.agent import AgentResult
        class Host:
            project=SimpleNamespace(name='Fixture project')
            workspace=SimpleNamespace(pending_proposals=lambda:())
            conversation=SimpleNamespace(display=lambda:())
            cleared=0
            def __init__(self):self.entered=threading.Event();self.release=threading.Event();self.cancelled=threading.Event();self.slow=False
            def ask(self,prompt):
                self.entered.set()
                if self.slow:self.release.wait(3)
                if self.cancelled.is_set():
                    from local_ai_appliance.backend import SessionCancelled
                    raise SessionCancelled('Cancelled by host')
                return AgentResult('Real controller fixture reply',(),(),1,0)
            def clear_chat(self):self.cleared+=1
            def cancel(self):self.cancelled.set();self.release.set()
        return Host()

    async def start_host(self,pipe,host,**options):
        preview=FullScreenPreview(backend=host,input=pipe,output=SizedOutput(),plain=True,client_options=options)
        task=asyncio.create_task(preview.app.run_async(pre_run=preview.start))
        await self.wait_for(lambda:preview.app.renderer.last_rendered_screen is not None)
        self.addAsyncCleanup(self.stop_preview,preview,task)
        return preview,task

    async def test_ctrl_u_stages_update_and_exits_without_model_call(self):
        import threading
        from unittest.mock import Mock
        manager = Mock(stop=threading.Event(), cancel_stage=threading.Event())
        manager.check.return_value = 'Update available — Ctrl+U to install'
        manager.stage.return_value = 'private-request.json'
        with create_pipe_input() as pipe:
            host = self.backend()
            preview, task = await self.start_host(pipe, host, update_manager=manager)
            self.addCleanup(manager.stop.set)
            pipe.send_text('\x15')
            await self.wait_for(task.done)
            manager.stage.assert_called_once()
            self.assertEqual(preview.controller.update_request, 'private-request.json')
            self.assertFalse(host.entered.is_set())

    async def test_ctrl_u_preserves_unsent_input_and_waits_for_active_work(self):
        import threading
        from unittest.mock import Mock
        manager = Mock(stop=threading.Event(), cancel_stage=threading.Event())
        manager.check.return_value = 'No newer compatible release'
        with create_pipe_input() as pipe:
            host = self.backend(); host.slow = True
            preview, task = await self.start_host(pipe, host, update_manager=manager)
            self.addCleanup(manager.stop.set)
            pipe.send_text('unsent\x15')
            await self.wait_for(lambda: 'Send or clear' in preview.transcript.text)
            self.assertEqual(preview.composer.text, 'unsent')
            pipe.send_text('\r'); await self.wait_for(host.entered.is_set)
            pipe.send_text('\x15')
            await self.wait_for(lambda: 'Wait for active work' in preview.transcript.text)
            manager.stage.assert_not_called()
            host.release.set()
            await self.wait_for(lambda: not preview.busy)

    async def test_update_cancellation_keeps_app_open(self):
        import threading
        from unittest.mock import Mock
        from local_ai_appliance.folders import AccessDenied
        entered = threading.Event()
        manager = Mock(stop=threading.Event(), cancel_stage=threading.Event())
        manager.check.return_value = 'Update available — Ctrl+U to install'
        def stage():
            entered.set()
            manager.cancel_stage.wait(3)
            raise AccessDenied('Update download cancelled')
        manager.stage.side_effect = stage
        with create_pipe_input() as pipe:
            preview, task = await self.start_host(pipe, self.backend(), update_manager=manager)
            self.addCleanup(manager.stop.set)
            pipe.send_text('\x15'); await self.wait_for(entered.is_set)
            pipe.send_text('\x03'); await self.wait_for(lambda: not preview.busy)
            self.assertIsNone(preview.controller.update_request)
            self.assertFalse(task.done())

    async def test_scrollback_ctrl_u_uses_real_prompt_binding(self):
        import io
        import threading
        from unittest.mock import Mock, patch
        from prompt_toolkit import PromptSession
        from local_ai_appliance.terminal_client import TerminalClient
        from local_ai_appliance.terminal_ui import TerminalView
        manager = Mock(stop=threading.Event(), cancel_stage=threading.Event())
        manager.status = 'Update available — Ctrl+U to install'
        manager.check.return_value = manager.status
        manager.stage.return_value = 'scrollback-request.json'
        self.addCleanup(manager.stop.set)
        created = []
        with create_pipe_input() as pipe:
            def prompt(**options):
                value = PromptSession(input=pipe, output=SizedOutput(), **options)
                created.append(value)
                return value
            host = self.backend()
            client = TerminalClient(host, view=TerminalView(io.StringIO(), plain=True), update_manager=manager)
            with patch('prompt_toolkit.PromptSession', side_effect=prompt), \
                 patch('sys.stdin.isatty', return_value=True), \
                 patch('sys.stdout.isatty', return_value=True):
                task = asyncio.create_task(asyncio.to_thread(client.interact))
                await self.wait_for(lambda: bool(created))
                pipe.send_text('\x15')
                await asyncio.wait_for(task, 3)
            self.assertEqual(client.update_request, 'scrollback-request.json')
            manager.stage.assert_called_once()
            self.assertFalse(host.entered.is_set())

    async def test_production_layout_calls_backend_and_clear_removes_context(self):
        with create_pipe_input() as pipe:
            host=self.backend();preview,_=await self.start_host(pipe,host)
            self.assertNotIn('Scripted replies', '\n'.join(self.screen_lines(preview)))
            pipe.send_text('A real controller request\r')
            await self.wait_for(lambda:'Real controller fixture reply' in preview.transcript.text and not preview.busy)
            pipe.send_text('/clear\r');await self.wait_for(lambda:host.cleared==1 and not preview.busy)
            self.assertNotIn('Real controller fixture reply',preview.transcript.text)

    async def test_production_ctrl_d_cancels_and_joins_host_request_before_exit(self):
        with create_pipe_input() as pipe:
            host=self.backend();host.slow=True;preview,task=await self.start_host(pipe,host)
            pipe.send_text('Slow request\r');await self.wait_for(host.entered.is_set)
            pipe.send_text('\x04');await self.wait_for(task.done)
            self.assertTrue(host.cancelled.is_set());self.assertFalse(preview.busy)
            self.assertNotIn('Real controller fixture reply',preview.transcript.text)

    async def test_unknown_host_command_preserves_existing_context(self):
        with create_pipe_input() as pipe:
            host=self.backend();preview,_=await self.start_host(pipe,host)
            pipe.send_text('/shell whoami\r')
            await self.wait_for(lambda:preview.state=='Request stopped' and not preview.busy)
            self.assertEqual(host.cleared,0);self.assertFalse(host.entered.is_set())

    async def test_model_menu_choice_and_ctrl_c_stay_in_host_ui(self):
        from types import SimpleNamespace
        with create_pipe_input() as pipe:
            host = self.backend(); preview, _ = await self.start_host(pipe, host)
            manager = SimpleNamespace(profiles=lambda: [], selected=lambda: None)
            preview.controller.managed = lambda: SimpleNamespace(service=SimpleNamespace(model_manager=manager))
            pipe.send_text('/model\r')
            await self.wait_for(lambda: preview.controller.model_menu.pending is not None and not preview.busy)
            self.assertIn('1. switch', preview.transcript.text)
            self.assertIn('2. install', preview.transcript.text)
            self.assertIn('3. remove', preview.transcript.text)
            pipe.send_text('2\r')
            await self.wait_for(lambda: 'No models available for install' in preview.transcript.text and not preview.busy)
            self.assertFalse(host.entered.is_set())
            pipe.send_text('/model\r')
            await self.wait_for(lambda: preview.controller.model_menu.pending is not None and not preview.busy)
            pipe.send_text('\x03')
            await self.wait_for(lambda: preview.controller.model_menu.pending is None)
            self.assertFalse(host.cancelled.is_set())
