"""Folder selection through terminal input and the existing host grant path."""
import asyncio
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

try:
    from prompt_toolkit.data_structures import Point, Size
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    from prompt_toolkit.mouse_events import MouseEvent, MouseEventType, MouseButton
    from local_ai_appliance.terminal_fullscreen import FullScreenPreview
    from local_ai_appliance.terminal_folder_dialog import dropped_folder_path
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


@unittest.skipUnless(AVAILABLE, 'Terminal extra required')
class FolderPathTests(unittest.TestCase):
    def test_terminal_quotes_spaces_and_windows_backslashes_are_literal(self):
        for incoming, expected in [
            ('"C:\\Users\\Ada\\Project Docs" ', 'C:\\Users\\Ada\\Project Docs'),
            ('C:\\Docs', 'C:\\Docs'),
            ("'/Users/Ada/Project Docs'", '/Users/Ada/Project Docs'),
            ('/Users/Ada/Project\\ Docs ', '/Users/Ada/Project Docs'),
            ('/Users/Ada/Project Docs', '/Users/Ada/Project Docs'),
            ("'/tmp/Trailing space '", '/tmp/Trailing space '),
            ('/tmp/$(echo secret)', '/tmp/$(echo secret)'),
        ]:
            with self.subTest(incoming=incoming): self.assertEqual(dropped_folder_path(incoming), expected)

    def test_multiple_paths_controls_drive_roots_and_relative_paths_are_rejected(self):
        for incoming in ['', 'Documents', '~/Documents', '/', 'C:\\',
                         '"C:\\One" "C:\\Two"', "'/tmp/one' '/tmp/two'", '/tmp/one /tmp/two',
                         '/tmp/one\n/draft /tmp/two', '/tmp/one\r', '/tmp/a\x1b',
                         '//server/share', '\\\\server\\share', 'C:\\one\\..\\two', '/tmp/../one',
                         '"/tmp/unfinished', '/tmp/'+('a'*4096)]:
            with self.subTest(incoming=incoming), self.assertRaises(ValueError): dropped_folder_path(incoming)


@unittest.skipUnless(AVAILABLE, 'Terminal extra required')
class FolderDialogTests(unittest.IsolatedAsyncioTestCase):
    async def wait_for(self, predicate):
        async with asyncio.timeout(4):
            while not predicate(): await asyncio.sleep(.01)

    async def start(self, pipe, *, columns=100, host=None):
        class Output(DummyOutput):
            def get_size(self): return Size(rows=30, columns=columns)
        screen = FullScreenPreview(input=pipe, output=Output(), backend=host, plain=True, delay=.4)
        task = asyncio.create_task(screen.app.run_async(pre_run=screen.start))
        async def stop():
            if not task.done(): screen.close()
            await asyncio.wait_for(task, 4)
        self.addAsyncCleanup(stop)
        await self.wait_for(lambda: screen.app.renderer.last_rendered_screen is not None)
        return screen

    def rows(self, screen):
        rendered, size = screen.app.renderer.last_rendered_screen, screen.app.output.get_size()
        return [''.join(rendered.data_buffer[y][x].char for x in range(size.columns)) for y in range(size.rows)]

    async def click(self, screen, text):
        def matches(row): return text in row and (text not in {'Grant', 'Back', 'Cancel'} or '<' in row)
        await self.wait_for(lambda: any(matches(row) for row in self.rows(screen)))
        y = next(i for i, row in enumerate(self.rows(screen)) if matches(row))
        x = self.rows(screen)[y].index(text) + 1
        screen.app.renderer.mouse_handlers.mouse_handlers[y][x](MouseEvent(
            Point(x=x, y=y), MouseEventType.MOUSE_UP, MouseButton.LEFT, frozenset()))
        await asyncio.sleep(.05)

    def paste(self, pipe, text): pipe.send_text('\x1b[200~'+text+'\x1b[201~')

    async def test_mouse_drop_and_explicit_drafts_grant_preserves_composer(self):
        with create_pipe_input() as pipe:
            screen = await self.start(pipe)
            pipe.send_text('Keep my message')
            await self.wait_for(lambda: screen.composer.text == 'Keep my message')
            await self.click(screen, '+ Add folder')
            self.paste(pipe, '"C:\\Users\\Ada\\Project Docs"')
            await self.wait_for(lambda: screen.folder_dialog.choosing)
            self.assertFalse(screen.demo.folder_grants)
            self.assertEqual(screen.folder_dialog.project_name, 'Capacity study')
            await self.click(screen, 'Drafts')
            self.assertEqual(screen.folder_dialog.access.current_value, 'draft')
            await self.click(screen, 'Grant')
            await self.wait_for(lambda: not screen.busy and not screen.folder_dialog.opened)
            self.assertEqual(screen.demo.folder_grants, {'C:\\Users\\Ada\\Project Docs': 'Drafts'})
            self.assertEqual(screen.composer.text, 'Keep my message')
            self.assertIn('No real folder access was granted', screen.transcript.text)
            screen.project_action('open', 'preview-notes')
            await self.wait_for(lambda: not screen.busy)
            self.assertFalse(screen.demo.folder_grants)
            screen.project_action('open', 'preview-capacity')
            await self.wait_for(lambda: not screen.busy)
            self.assertEqual(screen.demo.folder_grants['C:\\Users\\Ada\\Project Docs'], 'Drafts')

    async def test_narrow_dialog_back_escape_and_manual_path(self):
        with create_pipe_input() as pipe:
            screen = await self.start(pipe, columns=40)
            screen.composer.text = 'Unsent question'
            pipe.send_text('\x10')
            await self.wait_for(lambda: screen.sidebar.opened)
            await self.click(screen, '+ Add folder')
            pipe.send_text('/tmp/Folder with spaces\r')
            await self.wait_for(lambda: screen.folder_dialog.choosing)
            self.assertEqual(screen.folder_dialog.path, '/tmp/Folder with spaces')
            self.assertNotIn('Window too small', '\n'.join(self.rows(screen)))
            self.assertIn('Reference', '\n'.join(self.rows(screen)))
            await self.click(screen, 'Back')
            self.assertFalse(screen.folder_dialog.choosing)
            self.assertEqual(screen.folder_dialog.input.text, '/tmp/Folder with spaces')
            pipe.send_text('\x1b')
            await self.wait_for(lambda: not screen.folder_dialog.opened)
            self.assertFalse(screen.demo.folder_grants)
            self.assertEqual(screen.composer.text, 'Unsent question')
            self.assertTrue(screen.app.layout.has_focus(screen.composer))

    async def test_non_bracketed_terminal_drop_advances_after_complete_quotes(self):
        with create_pipe_input() as pipe:
            screen = await self.start(pipe)
            screen.folder_dialog.begin()
            pipe.send_text("'/tmp/Folder with spaces' ")
            await self.wait_for(lambda: screen.folder_dialog.choosing)
            self.assertEqual(screen.folder_dialog.path, '/tmp/Folder with spaces')
            self.assertFalse(screen.demo.folder_grants)

    async def test_keyboard_access_selection_requires_explicit_grant(self):
        with create_pipe_input() as pipe:
            screen = await self.start(pipe)
            screen.folder_dialog.begin()
            self.paste(pipe, '/tmp/Drafts')
            await self.wait_for(lambda: screen.folder_dialog.choosing)
            pipe.send_text('\x1b[B ')
            await self.wait_for(lambda: screen.folder_dialog.access.current_value == 'draft')
            self.assertFalse(screen.demo.folder_grants)
            pipe.send_text('\t\r')
            await self.wait_for(lambda: not screen.busy and not screen.folder_dialog.opened)
            self.assertEqual(screen.demo.folder_grants, {'/tmp/Drafts': 'Drafts'})

    async def test_invalid_drop_cannot_inject_a_command_or_switch_projects(self):
        with create_pipe_input() as pipe:
            screen = await self.start(pipe)
            screen.folder_dialog.begin()
            self.paste(pipe, '/tmp/One\n/project open preview-notes')
            await self.wait_for(lambda: bool(screen.folder_dialog.error))
            self.assertFalse(screen.folder_dialog.choosing)
            self.assertEqual(screen.demo.project_id, 'preview-capacity')
            screen.project_action('open', 'preview-notes')
            pipe.send_text('\x10\x1b[1;5F')
            await asyncio.sleep(.05)
            self.assertTrue(screen.folder_dialog.opened)
            self.assertEqual(screen.demo.project_id, 'preview-capacity')
            self.assertFalse(screen.demo.folder_grants)

    async def test_busy_work_and_changed_project_block_add_folder(self):
        with create_pipe_input() as pipe:
            screen = await self.start(pipe)
            pipe.send_text('/example\r')
            await self.wait_for(lambda: screen.busy)
            screen.folder_dialog.begin()
            self.assertFalse(screen.folder_dialog.opened)
            await self.wait_for(lambda: not screen.busy)
            screen.folder_dialog.begin()
            self.paste(pipe, '/tmp/Reference')
            await self.wait_for(lambda: screen.folder_dialog.choosing)
            screen.demo.project_id = 'preview-notes'  # Out-of-band context drift fixture.
            screen.folder_dialog.grant()
            self.assertIn('project changed', screen.folder_dialog.error)
            self.assertFalse(screen.demo.folder_grants)

    @unittest.skipUnless(os.name == 'posix', 'Portable broker fixture requires POSIX')
    async def test_host_grants_both_access_types_and_rejects_files_and_overlap(self):
        from local_ai_appliance.contracts import Project, WorkspaceKind
        from local_ai_appliance.workspace import Workspace
        class Host:
            def __init__(self):
                self.workspace = Workspace()
                self.project = Project('fixture', 'Broker fixture')
                self.events = []
                self.conversation = SimpleNamespace(display=lambda: ())
            def grant(self, path, kind):
                self.events.append((path, kind))
                folder = self.workspace.grant(path, 'read-only' if kind is WorkspaceKind.REFERENCE else 'editable')
                if getattr(self, 'persist_error', False): raise OSError('Fixture persistence failure')
                return folder
            def cancel(self): pass
        host = Host()
        self.addCleanup(host.workspace.close)
        with tempfile.TemporaryDirectory() as temporary, create_pipe_input() as pipe:
            root = Path(temporary).resolve()  # macOS /var is a symlink; broker forbids reparse paths.
            reference, drafts, file = root/'Reference space ', root/r'Draft\literal', root/'File.txt'
            reference.mkdir(); drafts.mkdir(); file.write_text('Synthetic fixture')
            screen = await self.start(pipe, host=host)
            screen.composer.text = 'Keep this'
            for path, access in [(reference, 'reference'), (drafts, 'draft')]:
                screen.controller.sources = {'old': 'old source'}
                screen.folder_dialog.begin()
                self.paste(pipe, '"'+str(path)+'"')
                await self.wait_for(lambda: screen.folder_dialog.choosing)
                self.assertFalse(screen.folder_dialog.pending)
                screen.folder_dialog.access.current_value = access
                screen.folder_dialog.grant()
                screen.folder_dialog.grant()  # Double action must not grant twice.
                await self.wait_for(lambda: not screen.busy and not screen.folder_dialog.opened)
                self.assertFalse(screen.controller.sources)
            self.assertEqual(host.events, [(str(reference), WorkspaceKind.REFERENCE), (str(drafts), WorkspaceKind.DRAFT)])
            self.assertEqual({f.name: f.access for f in host.workspace.broker.folders()},
                             {'Reference space ': 'read-only', r'Draft\literal': 'editable'})
            for invalid in (file, reference):
                screen.folder_dialog.begin()
                self.paste(pipe, '"'+str(invalid)+'"')
                await self.wait_for(lambda: screen.folder_dialog.choosing)
                screen.folder_dialog.grant()
                await self.wait_for(lambda: not screen.busy)
                self.assertTrue(screen.folder_dialog.opened)
                self.assertIn('Folder action stopped', screen.folder_dialog.error)
                self.assertEqual(len(host.workspace.broker.folders()), 2)
                screen.folder_dialog.cancel()
            partial = root/'Partial grant'; partial.mkdir()
            host.persist_error = True
            screen.controller.sources = {'old': 'old source'}
            screen.folder_dialog.begin()
            self.paste(pipe, str(partial))
            await self.wait_for(lambda: screen.folder_dialog.choosing)
            screen.folder_dialog.grant()
            await self.wait_for(lambda: not screen.busy)
            self.assertIn('Folder access changed', screen.folder_dialog.error)
            self.assertEqual(len(host.workspace.broker.folders()), 3)
            self.assertFalse(screen.controller.sources)
            screen.folder_dialog.cancel()
            self.assertEqual(screen.composer.text, 'Keep this')
