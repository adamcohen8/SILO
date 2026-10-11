"""Project navigation from host snapshots; render and keypresses perform no I/O."""
from prompt_toolkit.data_structures import Point
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, VSplit, Window, ConditionalContainer, DynamicContainer
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.mouse_events import MouseEventType
from prompt_toolkit.widgets import Button, Frame, TextArea

from .contracts import Project
from .terminal_ui import literal


class ProjectSidebar:
    def __init__(self, screen):
        self.screen = screen
        self.rows, self.index = (), 0
        self.available = screen.backend is None
        self.creating = self.opened = False
        self.active_id = None
        self.message = 'Loading projects…'
        self.name = TextArea(multiline=False, height=1, prompt='Name: ',
                             accept_handler=lambda _: self.create())
        self.new = Button('+ New project', handler=self.begin_create, width=20)
        self.create_button = Button('Create', handler=self.create, width=9)
        self.cancel_button = Button('Cancel', handler=self.cancel_form, width=9)
        keys = KeyBindings()
        @keys.add('up')
        def previous(event): self.move(-1)
        @keys.add('down')
        def following(event): self.move(1)
        @keys.add('pageup')
        def page_up(event): self.move(-6)
        @keys.add('pagedown')
        def page_down(event): self.move(6)
        @keys.add('enter')
        def choose(event): self.open_selected()
        self.control = FormattedTextControl(self.fragments, focusable=True, key_bindings=keys,
            get_cursor_position=lambda: Point(x=0, y=self.index * 2))
        body = HSplit([
            self.new,
            ConditionalContainer(HSplit([
                self.name,
                Window(FormattedTextControl('Uses current grants'), height=1, style='class:muted'),
                VSplit([self.create_button, self.cancel_button]),
            ]), filter=Condition(lambda: self.creating)),
            Window(height=1, char='─', style='class:rule'),
            Window(self.control, wrap_lines=False, style='class:sidebar'),
            Window(FormattedTextControl(' ↑↓ select · Enter open'), height=1, style='class:muted'),
            Window(FormattedTextControl('Ctrl+N new · Ctrl+P back'), height=1, style='class:muted'),
        ], width=lambda: 24 if self.wide else self.screen.app.output.get_size().columns - 2)
        wide = Frame(body, title='Projects', width=26)
        compact = Frame(body, title='Projects')
        self.container = DynamicContainer(lambda: wide if self.wide else compact)

    @property
    def wide(self):
        output = getattr(getattr(self.screen, 'app', None), 'output', None)
        return output is None or output.get_size().columns >= 80

    @property
    def visible(self): return self.wide or self.opened

    @property
    def focused(self):
        return any(self.screen.app.layout.has_focus(control) for control in
                   (self.control, self.new, self.name, self.create_button, self.cancel_button))

    def snapshot(self):
        if self.screen.backend is None:
            demo = self.screen.demo
            return demo.project_listing(), demo.project_id
        backend = self.screen.backend
        return backend.store.listing(), backend.project.id

    async def refresh(self):
        import asyncio
        selected = self.rows[self.index]['id'] if self.rows else None
        revision = self.screen._project_revision
        try:
            rows, active = await asyncio.to_thread(self.snapshot)
            if revision != self.screen._project_revision: return
            self.rows = tuple(rows[:64])
            target = active if active != self.active_id else selected or active
            self.active_id, self.available = active, True
            indices = {row['id']: i for i, row in enumerate(self.rows)}
            self.index = indices.get(target, indices.get(active, 0))
            self.message = 'No saved projects.'
        except Exception:
            if revision != self.screen._project_revision: return
            self.rows, self.index, self.available = (), 0, False
            self.message = 'Project storage unavailable.'
        self.screen.app.invalidate()

    def fragments(self):
        if not self.rows: return [('class:muted', literal(self.message))]
        fragments = []
        for i, row in enumerate(self.rows):
            def click(event, identifier=row['id']):
                if event.event_type == MouseEventType.SCROLL_DOWN:
                    self.move(3); return
                if event.event_type == MouseEventType.SCROLL_UP:
                    self.move(-3); return
                if event.event_type == MouseEventType.MOUSE_UP:
                    index = next((i for i, row in enumerate(self.rows) if row['id'] == identifier), None)
                    if index is None:
                        self.screen.view.notice('That project is no longer listed. Choose a current project.', warning=True)
                        return
                    self.index = index
                    self.open_selected()
            tone = 'class:sidebar.selected' if i == self.index and self.focused else 'class:sidebar'
            mark = '* ' if row['id'] == self.active_id else '  '
            from .terminal_rich import width, cells
            name = literal(row['name'])
            budget = 20 if self.wide else max(1, self.screen.app.output.get_size().columns - 6)
            if width(name) > budget: name = cells(name, max(1, budget - 1))[0] + '…'
            fragments.append((tone, mark + name + '\n', click))
            suffix = ' · expired' if row.get('expired') else ''
            fragments.append(('class:muted', '  ' + literal(row['id'][-8:]) + suffix + '\n', click))
        return fragments

    def move(self, count):
        if self.rows: self.index = max(0, min(len(self.rows)-1, self.index + count))
        self.screen.app.invalidate()

    def toggle(self):
        if self.focused or self.creating:
            self.cancel_form()
            return
        self.opened = True
        self.screen.app.layout.focus(self.control if self.rows else self.new)
        self.screen.app.invalidate()

    def begin_create(self):
        if not self.screen.project_action_allowed(): return
        self.opened = self.creating = True
        self.screen.app.layout.focus(self.name)
        self.screen.app.invalidate()

    def cancel_form(self):
        self.creating = self.opened = False
        self.name.text = ''
        self.screen.app.layout.focus(self.screen.composer)
        self.screen.app.invalidate()

    def create(self):
        name = self.name.text.strip()
        try: Project('validation', name)
        except ValueError:
            self.screen.view.notice('Enter a project name of 1–128 characters, without control characters.', warning=True)
            return True
        self.screen.project_action('new', name)
        return True  # Keep the name if persistence fails.

    def open_selected(self):
        if self.rows:
            self.screen.project_action('open', self.rows[self.index]['id'])
