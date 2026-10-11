"""Actual sidebar UI with preview state and inert native-project host dispatch."""
import asyncio
from types import SimpleNamespace
import unittest

try:
    from prompt_toolkit.data_structures import Point, Size
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    from prompt_toolkit.mouse_events import MouseEvent, MouseEventType, MouseButton
    from local_ai_appliance.terminal_fullscreen import FullScreenPreview
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


@unittest.skipUnless(AVAILABLE, 'Terminal extra required')
class ProjectSidebarTests(unittest.IsolatedAsyncioTestCase):
    async def wait_for(self, predicate):
        async with asyncio.timeout(4):
            while not predicate(): await asyncio.sleep(.01)

    async def start(self, pipe, *, columns=100, host=None):
        class Output(DummyOutput):
            def get_size(self): return Size(rows=30, columns=columns)
        screen = FullScreenPreview(input=pipe, output=Output(), backend=host, plain=True, delay=.5)
        task = asyncio.create_task(screen.app.run_async(pre_run=screen.start))
        async def stop():
            if not task.done(): screen.close()
            await asyncio.wait_for(task, 4)
        self.addAsyncCleanup(stop)
        await self.wait_for(lambda: screen.app.renderer.last_rendered_screen is not None)
        await self.wait_for(lambda: screen.sidebar.available)
        return screen

    def rows(self, screen):
        rendered = screen.app.renderer.last_rendered_screen
        size = screen.app.output.get_size()
        return [''.join(rendered.data_buffer[y][x].char for x in range(size.columns)) for y in range(size.rows)]

    async def click(self, screen, text):
        await self.wait_for(lambda: any(text in row[:26] for row in self.rows(screen)[3:-2]))
        rows = self.rows(screen)
        y = next(i for i, row in enumerate(rows) if i >= 3 and text in row[:26])
        x = rows[y].index(text) + 1
        screen.app.renderer.mouse_handlers.mouse_handlers[y][x](MouseEvent(
            position=Point(x=x, y=y), event_type=MouseEventType.MOUSE_UP,
            button=MouseButton.LEFT, modifiers=frozenset()))

    async def test_mouse_creates_and_switches_projects_without_losing_input_or_conversation(self):
        with create_pipe_input() as pipe:
            screen = await self.start(pipe)
            pipe.send_text('/example\r')
            await self.wait_for(lambda: not screen.busy and 'D1' in screen.demo.pending)
            await self.wait_for(lambda: '108 kg' in screen.transcript.text)
            pipe.send_text('Next question')
            await self.wait_for(lambda: screen.composer.text == 'Next question')
            await self.click(screen, '+ New project')
            self.assertTrue(screen.sidebar.creating)
            pipe.send_text('New research\r')
            await self.wait_for(lambda: not screen.busy and screen.demo.project_name == 'New research')
            self.assertEqual(screen.composer.text, 'Next question')
            self.assertNotIn('108 kg', screen.transcript.text)
            self.assertFalse(screen.demo.pending)
            await self.click(screen, 'Capacity study')
            await self.wait_for(lambda: not screen.busy and screen.demo.project_id == 'preview-capacity')
            await self.wait_for(lambda: '108 kg' in screen.transcript.text)
            self.assertIn('D1', screen.demo.pending)
            self.assertEqual(screen.composer.text, 'Next question')
            screen.composer.text = ''
            pipe.send_text('/mo')
            await self.wait_for(lambda: screen.composer.buffer.complete_state is not None)
            await asyncio.sleep(.1)
            self.assertTrue(self.rows(screen)[-1].rstrip().endswith(screen.model_label()))

    async def test_keyboard_navigation_and_small_window_project_panel(self):
        with create_pipe_input() as pipe:
            screen = await self.start(pipe, columns=40)
            self.assertFalse(screen.sidebar.visible)
            pipe.send_text('\x10')
            await self.wait_for(lambda: screen.sidebar.focused)
            self.assertTrue(screen.sidebar.visible)
            await self.wait_for(lambda: self.rows(screen)[4].rstrip().endswith('│'))
            self.assertEqual(len(self.rows(screen)[4].rstrip()), 40)
            pipe.send_text('\x1b[B\r')
            await self.wait_for(lambda: not screen.busy and screen.demo.project_id == 'preview-notes')
            self.assertFalse(screen.sidebar.opened)
            self.assertTrue(screen.app.layout.has_focus(screen.composer))
            self.assertIn('Message SILO', '\n'.join(self.rows(screen)))
            self.assertNotIn('Window too small', '\n'.join(self.rows(screen)))
            pipe.send_text('\x10\x0e')
            await self.wait_for(lambda: screen.sidebar.creating)
            pipe.send_text('Keyboard project\r')
            await self.wait_for(lambda: not screen.busy and screen.demo.project_name == 'Keyboard project')
            self.assertFalse(screen.sidebar.opened)

    async def test_busy_work_blocks_project_changes_and_cancel_form_keeps_composer(self):
        with create_pipe_input() as pipe:
            screen = await self.start(pipe)
            pipe.send_text('/example\r')
            await self.wait_for(lambda: screen.busy)
            screen.sidebar.begin_create()
            screen.project_action('open', 'preview-notes')
            self.assertFalse(screen.sidebar.creating)
            self.assertEqual(screen.demo.project_id, 'preview-capacity')
            pipe.send_text('\x03')
            await self.wait_for(lambda: not screen.busy)
            pipe.send_text('Keep this input')
            await self.wait_for(lambda: screen.composer.text == 'Keep this input')
            screen.sidebar.begin_create()
            pipe.send_text('\r')  # Empty project name must not create anything.
            await asyncio.sleep(.05)
            self.assertEqual(len(screen.demo.projects), 2)
            pipe.send_text('Unsaved name\x1b')
            await self.wait_for(lambda: not screen.sidebar.creating)
            self.assertEqual(screen.composer.text, 'Keep this input')

    async def test_old_mouse_row_binds_project_id_after_list_reordering(self):
        with create_pipe_input() as pipe:
            screen = await self.start(pipe)
            handler = screen.sidebar.fragments()[2][2]  # Notes row from the old screen.
            screen.sidebar.rows = tuple(reversed(screen.sidebar.rows))
            handler(MouseEvent(Point(0, 0), MouseEventType.MOUSE_UP, MouseButton.LEFT, frozenset()))
            await self.wait_for(lambda: not screen.busy and screen.demo.project_id == 'preview-notes')

    async def test_native_sidebar_uses_existing_controller_project_operations(self):
        class Host:
            workspace = SimpleNamespace(pending_proposals=lambda: ())
            conversation = SimpleNamespace(display=lambda: ())
            project = SimpleNamespace(id='first', name='First')
            record = None
            def __init__(self):
                self.events = []
                self.entries = [{'id':'first', 'name':'First', 'expired':False},
                                {'id':'second', 'name':'Second', 'expired':False}]
                self.store = SimpleNamespace(listing=lambda: self.entries)
            def create_project(self, name):
                self.events.append(('create', name))
                self.project = SimpleNamespace(id='new', name=name)
                self.entries.append({'id':'new', 'name':name, 'expired':False})
                return self.project
            def open_project(self, identifier):
                self.events.append(('open', identifier))
                row = next(row for row in self.entries if row['id']==identifier)
                self.project = SimpleNamespace(id=identifier, name=row['name'])
                return {}
            def cancel(self): pass
        with create_pipe_input() as pipe:
            host = Host(); screen = await self.start(pipe, host=host)
            screen.controller.managed = lambda: host  # Inert fixture only.
            screen.controller.sources = {'old': 'old project source'}
            await self.click(screen, 'Second')
            await self.wait_for(lambda: not screen.busy and host.project.id=='second')
            self.assertFalse(screen.controller.sources)
            await self.click(screen, '+ New project')
            pipe.send_text('Native project\r')
            await self.wait_for(lambda: not screen.busy and host.project.id=='new')
            self.assertEqual(host.events, [('open','second'), ('create','Native project')])
