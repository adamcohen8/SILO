"""Explicit folder selection UI. Paths are data, never shell commands."""
import asyncio
import ntpath
import re
import shlex

from prompt_toolkit.filters import Condition
from prompt_toolkit.document import Document
from prompt_toolkit.layout import ConditionalContainer, DynamicContainer, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.widgets import Box, Button, Dialog, RadioList, TextArea

from .terminal_ui import literal
from .contracts import WorkspaceKind


def dropped_folder_path(text):
    """Normalize one terminal-quoted absolute path without expansion or I/O."""
    if not isinstance(text, str) or len(text) > 4096 or any(ord(c) < 32 or ord(c) == 127 for c in text):
        raise ValueError('Drop one folder, without newlines or control characters.')
    value = text.strip()
    windows = bool(re.match(r'^[\"\']?[A-Za-z]:[\\/]', value))
    if windows:
        if value[:1] in {'"', "'"}:
            if len(value) < 2 or value[-1] != value[0]: raise ValueError('Finish the quoted folder path.')
            value = value[1:-1]
        if '"' in value or re.search(r'\s+[A-Za-z]:[\\/]', value):
            raise ValueError('Add one folder at a time.')
        if not ntpath.isabs(value) or '..' in re.split(r'[\\/]', value):
            raise ValueError('Select an absolute local folder path.')
    else:
        if value.startswith(('"', "'")) or '\\' in value:
            try: parts = shlex.split(value)
            except ValueError: raise ValueError('Finish the quoted folder path.') from None
            if len(parts) != 1: raise ValueError('Add one folder at a time.')
            value = parts[0]
        if not value.startswith('/') or value.startswith('//') or '..' in value.split('/'):
            raise ValueError('Select an absolute local folder path.')
        if ' /' in value: raise ValueError('Add one folder at a time.')
    if value in {'/', '\\'} or re.fullmatch(r'[A-Za-z]:[\\/]?', value):
        raise ValueError('Select a folder, rather than a whole drive.')
    return value


class FolderDialog:
    def __init__(self, screen):
        self.screen = screen
        self.opened = self.choosing = self.pending = False
        self.path = self.error = ''
        self.project_id = self.project_name = None
        self._grant_selection = None
        self._before_grant_revision = None
        self._revision = 0
        self.input = TextArea(multiline=False, height=2, wrap_lines=True,
                              prompt='Folder: ', accept_handler=lambda _: self.continue_path())
        self.input.buffer.on_text_changed += self.path_changed
        self.access = RadioList([('reference', 'Reference'), ('draft', 'Drafts')])
        self.path_display = TextArea(read_only=True, wrap_lines=True, scrollbar=True,
                                     height=Dimension(min=1, preferred=2, max=3))
        error = Window(FormattedTextControl(lambda: literal(self.error)), wrap_lines=True,
                       height=Dimension(min=1, preferred=2, max=3), style='class:warning')
        project = Window(FormattedTextControl(lambda: 'Project: '+literal(self.project_name or '')),
                         wrap_lines=True, height=Dimension(min=1, max=2))
        path_body = HSplit([
            project,
            Window(FormattedTextControl('Drop a folder here, or paste its full path.\nPress Continue / Enter if needed.'), height=2),
            self.input, error,
        ])
        access_body = HSplit([
            project,
            self.path_display,
            ConditionalContainer(self.access, filter=Condition(lambda: not self.pending)),
            ConditionalContainer(Window(FormattedTextControl(lambda: 'Granting '+self._grant_selection[1]+' access…'), height=1),
                                 filter=Condition(lambda: self.pending)),
            Window(FormattedTextControl('Reference: read and cite.\nDrafts: read and save reviewed new copies.'),
                   wrap_lines=True, height=Dimension(min=2, max=4)),
            Window(FormattedTextControl('↑↓ then Space to choose · Tab to Grant'),
                   wrap_lines=True, height=Dimension(min=1, max=2), style='class:muted'),
            Window(FormattedTextControl(lambda: 'Preview only: no real access is granted.'
                       if screen.backend is None else 'Changing access clears chat and pending reviews.'),
                   wrap_lines=True, height=Dimension(min=1, max=3), style='class:muted'),
            error,
        ])
        size = lambda: max(20, min(68, screen.app.output.get_size().columns - 2))
        self.entry_dialog = Dialog(title='Add folder', body=path_body, width=size,
            buttons=[Button('Continue', handler=self.continue_path, width=10), Button('Cancel', handler=self.cancel, width=8)])
        self.grant_button = Button('Grant', handler=self.grant, width=8)
        self.access_dialog = Dialog(title='Folder access', body=access_body, width=size,
            buttons=[self.grant_button, Button('Back', handler=self.back, width=8),
                     Button('Cancel', handler=self.cancel, width=8)])
        self.container = DynamicContainer(lambda: self.access_dialog if self.choosing else self.entry_dialog)
        self.background = Box(self.container, style='class:dialog')

    def focus(self):
        self.screen.app.layout.focus(self.grant_button if self.pending else self.access if self.choosing else self.input)

    def active_project(self):
        backend = self.screen.backend
        return ((self.screen.demo.project_id, self.screen.demo.project_name) if backend is None
                else (backend.project.id, backend.project.name))

    def begin(self):
        if self.screen.busy or self.screen.closing or self.screen.recovery_failed:
            self.screen.view.notice('Wait until SILO is ready before adding a folder.', warning=True)
            return
        if self.opened: return
        self.screen.sidebar.cancel_form()
        self.project_id, self.project_name = self.active_project()
        self.path = self.error = self.input.text = ''
        self.access.current_value = 'reference'
        self.opened, self.choosing = True, False
        self.screen.app.layout.focus(self.input)
        self.screen.app.invalidate()

    def path_changed(self, buffer):
        self._revision += 1
        if not self.opened or self.choosing: return
        value = buffer.text
        # Terminal drops often end with a closing quote or a space. A quiet
        # complete selection can advance; incomplete manual paths stay editable.
        complete = value.endswith(' ') or (len(value) > 2 and value[0] in {'"', "'"} and value[-1] == value[0])
        if not complete: return
        revision = self._revision
        async def advance():
            await asyncio.sleep(.25)
            if self.opened and not self.choosing and revision == self._revision:
                self.continue_path()
        self.screen.app.create_background_task(advance())

    def continue_path(self):
        if not self.opened or self.pending: return True
        try: self.path = dropped_folder_path(self.input.text)
        except ValueError as error:
            self.error = str(error); self.screen.app.invalidate(); return True
        self.choosing, self.error = True, ''
        self.path_display.buffer.set_document(Document(literal(self.path)), bypass_readonly=True)
        self.screen.app.layout.focus(self.access)
        self.screen.app.invalidate()
        return True

    def paste(self, text):
        # Keep the entire selection so invalid multi-path input is rejected.
        self.input.text = text
        self.continue_path()

    def back(self):
        if self.pending: return
        self.choosing, self.error = False, ''
        self.screen.app.layout.focus(self.input)
        self.screen.app.invalidate()

    def cancel(self):
        if self.pending:
            self.error = 'Checking folder access. Please wait.'
            self.screen.app.invalidate(); return
        self.opened = self.choosing = False
        self._revision += 1
        self.input.text = self.path = self.error = ''
        self.screen.app.layout.focus(self.screen.composer)
        self.screen.app.invalidate()

    def grant(self):
        if not self.opened or not self.choosing or self.pending: return
        if self.screen.busy or self.screen.closing or self.screen.recovery_failed:
            self.error = 'Wait until SILO is ready.'
        elif self.active_project()[0] != self.project_id:
            self.error = 'The active project changed. Cancel and add the folder again.'
        elif self.access.current_value not in {'reference', 'draft'}:
            self.error = 'Choose Reference or Drafts.'
        else:
            self.screen.controller.model_menu.cancel()
            self._grant_selection = (self.path, self.access.current_value, self.project_name)
            if self.screen.backend is not None:
                self.screen.controller.sources.clear()
                self._before_grant_revision = getattr(self.screen.backend.workspace.broker, 'revision', None)
            self.pending, self.error = True, 'Checking folder access…'
            self.screen.app.layout.focus(self.grant_button)
            self.screen._begin_request('/'+self.access.current_value+' '+self.path)
        self.screen.app.invalidate()

    def finish(self, error=None):
        if not self.pending: return
        self.pending = False
        if error is None:
            path, access, project = self._grant_selection
            self.cancel()
            label = 'Reference' if access == 'reference' else 'Drafts'
            self.screen.view.notice(('Preview only: ' if self.screen.backend is None else '')+
                label+' access for '+literal(path)+' in '+literal(project)+
                ('. No real folder access was granted.' if self.screen.backend is None else '.'))
        else:
            changed = (self.screen.backend is not None and
                       getattr(self.screen.backend.workspace.broker, 'revision', None) != self._before_grant_revision)
            self.error = ('Folder access changed, but the action stopped: ' if changed else 'Folder action stopped: ')+literal(str(error))
            if changed: self.error += ' Cancel and check /folders before retrying.'
            self.screen.app.layout.focus(self.access)
            self.screen.app.invalidate()

    def apply(self):
        if self.active_project()[0] != self.project_id:
            raise ValueError('The active project changed. Add the folder again.')
        path, access, _ = self._grant_selection
        return self.screen.controller.grant_folder(path, WorkspaceKind.REFERENCE if access == 'reference' else WorkspaceKind.DRAFT)
