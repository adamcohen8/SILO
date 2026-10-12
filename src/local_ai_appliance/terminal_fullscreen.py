"""Full-window design preview; the host backend remains separate."""
import asyncio
import os
import threading

from prompt_toolkit import Application
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.key_binding.bindings.scroll import scroll_page_down, scroll_page_up
from prompt_toolkit.key_binding.bindings.focus import focus_next, focus_previous
from prompt_toolkit.layout import HSplit, Layout, VSplit, Window, ConditionalContainer, Float, FloatContainer, DynamicContainer
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.containers import WindowAlign
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea, Button

from .terminal_demo import DemoSession
from .terminal_ui import TerminalView, literal
from .terminal_completion import SiloCompleter
from .terminal_projects import ProjectSidebar
from .terminal_folder_dialog import FolderDialog


class TranscriptLexer(Lexer):
    def __init__(self, preview):
        self.preview = preview

    def lex_document(self, document):
        lines = document.lines
        tones = list(self.preview.tones)
        spans = list(self.preview.spans)
        def render(number):
            base = 'class:' + tones[number] if number < len(tones) else ''
            if number < len(spans) and spans[number]:
                return [(base + ' ' + style, text) for style, text in spans[number]]
            return [(base, lines[number])]
        return render


class ScreenView(TerminalView):
    def __init__(self, preview):
        self.preview = preview

    @property
    def width(self):
        columns = self.preview.app.output.get_size().columns
        return max(20, columns - 4 - (26 if columns >= 80 else 0))

    def line(self, text='', tone=None):
        self.preview.append(literal(text), tone or 'body')

    def body(self, text, *, indent='  ', tone=None):
        # Leave wrapping to the window so resizing can reflow existing text.
        for line in literal(text).expandtabs(4).split('\n'):
            self.line(indent+line, tone)

    def header(self):
        self.line()
        self.body('What would you like to work on?', tone='bold')
        self.line()
        self.body('Try /example for a cited reply; /format previews Markdown and code.', tone='muted')
        self.body('/help shows commands. All content here is synthetic.', tone='muted')

    def answer(self, text):
        from .terminal_rich import markdown
        self.line(); self.line('SILO', 'accent')
        for row in markdown(text, columns=self.width - 2):
            spans = (('', '  '), *row.spans) if row.spans else ()
            self.preview.append('  ' + row.text, row.tone, spans)


class FullScreenPreview:
    def __init__(self, *, plain=False, input=None, output=None, delay=0.2, backend=None, client_options=None):
        self.lines, self.tones, self.spans = [], [], []
        self.follow = True
        self.recovering = False
        self.recovery_failed = False
        self.live_text = ''
        self.live = TextArea(read_only=True, wrap_lines=True,
                             height=Dimension(min=1, preferred=4, max=6), style='class:muted')
        if backend is None:
            from .mentions import Mention
            self.completer = SiloCompleter({command: 'Synthetic preview' for command in
                ('/example', '/format', '/help', '/folders', '/sources', '/drafts', '/model', '/model switch ',
                 '/model install ', '/model remove ', '/models', '/review D1',
                 '/project new ', '/project list', '/project open ', '/project close',
                 '/approve D1', '/discard D1', '/clear', '/quit')})
            self.completer.mentions = (Mention('Reference', 'preview', 'policy.txt', 'file'),
                                       Mention('Reference', 'preview', 'inventory.csv', 'file'))
        else:
            self.completer = SiloCompleter()
        self.loop = None
        self.busy = False
        self.closing = False
        self.task = None
        self.model_request = False
        self.update_operation = False
        self.state = 'Ready'
        self.transcript = TextArea(read_only=True, scrollbar=True, wrap_lines=True,
                                   focusable=True, lexer=TranscriptLexer(self))
        self.composer = TextArea(multiline=True, wrap_lines=True, prompt='> ',
                                 height=Dimension(min=1, preferred=2, max=4),
                                 completer=self.completer, complete_while_typing=True,
                                 history=InMemoryHistory(), style='class:input')
        self.view = ScreenView(self)
        self.backend = backend
        self.cancelled = threading.Event()
        self.demo = DemoSession(self.view, delay=delay)
        if backend is not None:
            from .terminal_client import TerminalClient
            self.controller = TerminalClient(backend, view=self.view, **(client_options or {}))
        else:
            self.controller = self.demo
        self._project_revision = 0
        self._preview_transcripts = {}
        self.sidebar = ProjectSidebar(self)
        self.folder_dialog = FolderDialog(self)
        projects_button = Button('Projects', handler=self.sidebar.toggle, width=12)
        bindings = KeyBindings()

        composer_focused = Condition(lambda: self.app.layout.has_focus(self.composer) and not self.folder_dialog.opened)

        no_folder_dialog = Condition(lambda: not self.folder_dialog.opened)

        @bindings.add('escape', filter=~no_folder_dialog, eager=True)
        def close_folder(event): self.folder_dialog.cancel()

        @bindings.add(Keys.BracketedPaste, filter=~no_folder_dialog & Condition(lambda: not self.folder_dialog.choosing), eager=True)
        def paste_folder(event): self.folder_dialog.paste(event.data)

        @bindings.add('c-p', filter=no_folder_dialog, eager=True)
        def projects(event): self.sidebar.toggle()

        @bindings.add('c-n', filter=no_folder_dialog & Condition(lambda: self.sidebar.focused), eager=True)
        def new_project(event): self.sidebar.begin_create()

        @bindings.add('tab', filter=~composer_focused)
        def next_control(event): focus_next(event)

        @bindings.add('s-tab', filter=~composer_focused)
        def previous_control(event): focus_previous(event)

        @bindings.add('escape', filter=Condition(lambda: self.sidebar.focused))
        def close_projects(event): self.sidebar.cancel_form()

        @bindings.add('enter', filter=composer_focused, eager=True)
        def send(event):
            completion = self.composer.buffer.complete_state
            if completion is not None and completion.completions:
                self.composer.buffer.apply_completion(completion.current_completion or completion.completions[0])
                return
            self.submit()

        @bindings.add('escape', 'enter', filter=composer_focused, eager=True)
        def newline(event):
            self.composer.buffer.insert_text('\n')

        @bindings.add('escape', filter=composer_focused & Condition(lambda: self.composer.buffer.complete_state is not None))
        def dismiss_completion(event):
            self.composer.buffer.cancel_completion()

        @bindings.add('f2', filter=composer_focused, eager=True)
        def commands(event):
            if self.composer.text:
                self.view.notice('Type / or a command prefix and press Tab. Your input has been kept.')
            else:
                self.composer.text = '/'
                self.composer.buffer.start_completion(select_first=False)

        @bindings.add('f3', filter=composer_focused, eager=True)
        def files(event):
            if self.backend is not None and not self.completer.mentions:
                self.view.notice('No granted files to suggest. Use /reference PATH first.')
                return
            prefix = '' if not self.composer.text or self.composer.text.endswith((' ', '\n')) else ' '
            self.composer.buffer.insert_text(prefix + '@')
            self.composer.buffer.start_completion(select_first=False)

        @bindings.add('c-c', eager=True)
        def cancel(event):
            if self.folder_dialog.opened:
                self.folder_dialog.cancel()
                return
            if self.busy:
                self.cancel_request()
                self.state = 'Cancelling'
                if self.sidebar.opened: self.sidebar.cancel_form()
            else:
                if self.sidebar.focused or self.sidebar.creating:
                    self.sidebar.cancel_form()
                    return
                self.composer.text = ''
                if self.controller.model_menu.pending is not None:
                    self.controller.model_menu.cancel()
                    self.completer.choices = ()
                    self.state = 'Model menu closed'
                else: self.state = 'Input cleared'
            event.app.layout.focus(self.composer)

        @bindings.add('c-d', eager=True)
        def quit_preview(event):
            self.close()

        @bindings.add('c-u', eager=True)
        def update(event):
            if self.folder_dialog.opened: return
            if self.backend is None:
                self.view.notice('Updates require the standalone installation', warning=True)
            elif self.busy:
                self.view.notice('Wait for active work to finish before updating', warning=True)
            elif self.sidebar.creating:
                self.view.notice('Finish or cancel the new project before updating', warning=True)
            elif self.composer.text:
                self.view.notice('Send or clear your input before updating', warning=True)
            elif self.controller.model_menu.pending is not None:
                self.view.notice('Close the model menu before updating', warning=True)
            else:
                self.composer.text = '/update'
                self.submit()

        @bindings.add('pageup', filter=no_folder_dialog & Condition(lambda: not self.sidebar.focused), eager=True)
        def earlier(event):
            self.follow = False
            event.app.layout.focus(self.transcript)
            scroll_page_up(event)
            event.app.layout.focus(self.composer)

        @bindings.add('pagedown', filter=no_folder_dialog & Condition(lambda: not self.sidebar.focused), eager=True)
        def later(event):
            event.app.layout.focus(self.transcript)
            scroll_page_down(event)
            self.follow = self.transcript.buffer.cursor_position >= len(self.transcript.text)
            event.app.layout.focus(self.composer)

        @bindings.add('c-end', filter=no_folder_dialog, eager=True)
        def latest(event):
            if self.sidebar.opened: self.sidebar.cancel_form()
            self.follow = True
            self.transcript.buffer.cursor_position = len(self.transcript.text)
            event.app.layout.focus(self.composer)

        main = FloatContainer(HSplit([
            VSplit([Window(width=1), self.transcript, Window(width=1)]),
            ConditionalContainer(Frame(self.live, title='Live response · provisional until validated'),
                                 filter=Condition(lambda: bool(self.live_text))),
            Window(FormattedTextControl(self.status), height=1, style='class:status'),
            Frame(self.composer, title='Message SILO', style='class:frame'),
        ]), floats=[Float(
            xcursor=True, ycursor=True, attach_to_window=self.composer.window,
            content=CompletionsMenu(max_height=8, scroll_offset=1, display_arrows=True),
        )])
        # Narrow windows can open Projects as a full-width panel with Ctrl+P.
        wide_body = VSplit([self.sidebar.container, main])
        root = HSplit([
            VSplit([Window(FormattedTextControl(self.title), height=1), projects_button]),
            Window(FormattedTextControl('  Design preview · Scripted replies · No file access' if backend is None else '  Contained Windows evaluation · Public / synthetic data · /help'),
                   height=1, style='class:muted'),
            Window(height=1, char='─', style='class:rule'),
            DynamicContainer(lambda: self.folder_dialog.background if self.folder_dialog.opened else
                             wide_body if self.sidebar.wide else self.sidebar.container if self.sidebar.opened else main),
            HSplit([
                ConditionalContainer(VSplit([
                    Window(FormattedTextControl(self.hints), height=1, style='class:muted'),
                    Window(FormattedTextControl(self.model_label), height=1, width=self.model_width,
                           align=WindowAlign.RIGHT, style='class:accent'),
                    Window(width=1, height=1),
                ]), filter=Condition(lambda: self.app.output.get_size().columns >= 80)),
                ConditionalContainer(HSplit([
                    Window(FormattedTextControl(self.hints), height=1, style='class:muted'),
                    Window(FormattedTextControl(lambda: self.model_label() + ' '), height=1,
                           align=WindowAlign.RIGHT, style='class:accent'),
                ]), filter=Condition(lambda: self.app.output.get_size().columns < 80)),
            ]),
        ])
        monochrome = plain or 'NO_COLOR' in os.environ or os.environ.get('TERM') == 'dumb'
        style = Style.from_dict({} if monochrome else {
            '': 'bg:#101318 #dce2eb', 'body': '#dce2eb',
            'accent': '#65d9c6 bold', 'bold': 'bold', 'muted': '#909bad',
            'warning': '#edc779', 'rule': '#354050',
            'input': 'bg:#1a2029 #edf2f8', 'frame': '#66758a',
            'status': '#65d9c6', 'scrollbar.background': 'bg:#1a2029',
            'scrollbar.button': 'bg:#66758a',
            'code': '#dce2eb bg:#1a2029', 'keyword': '#c99bff', 'string': '#a7dba3',
            'number': '#edc779', 'comment': '#909bad', 'citation': '#65d9c6', 'table': '#dce2eb',
            'completion-menu.completion': 'bg:#1a2029 #dce2eb',
            'completion-menu.completion.current': 'bg:#354050 #65d9c6',
            'sidebar': '#dce2eb bg:#1a2029', 'sidebar.selected': 'bg:#354050 #65d9c6 bold',
            'button': '#65d9c6', 'button.focused': '#101318 bg:#65d9c6 bold',
            'dialog': 'bg:#1a2029 #dce2eb', 'dialog.body': 'bg:#1a2029 #dce2eb',
        })
        self.app = Application(layout=Layout(root, focused_element=self.composer),
                               key_bindings=bindings, style=style, full_screen=True,
                               mouse_support=True, input=input, output=output)
        if backend is None:
            self.view.header()
        else:
            sinks = getattr(backend, 'set_display_sinks', None)
            if callable(sinks): sinks(self.progress, self.stream_text)
            self.view.notice('Ready. /reference PATH and /draft PATH grant access. /project new NAME enables encrypted retention.')
            self.view.notice('Tab completes · F2 commands · F3 granted files · /model opens the model menu.')
            conversation = getattr(backend, 'conversation', None)
            if conversation:
                for prompt, answer in conversation.display():
                    self.view.user(prompt); self.view.answer(answer)

    def cancel_request(self):
        self.cancelled.set()
        if self.backend is None:
            self.demo.cancelled.set()
        else:
            if self.update_operation and self.controller.update_manager is not None:
                self.controller.update_manager.cancel_stage.set()
            elif self.model_request: self.controller.model_menu.cancel()
            else: self.backend.cancel()

    def reset_session(self):
        if self.backend is None:
            self.demo.reset()
        else:
            self.backend.clear_chat()

    def status(self):
        try:
            pending = (len(self.demo.pending) if self.backend is None else
                       len(self.backend.workspace.pending_proposals())) if not self.busy else 0
        except Exception:
            pending = 0
        project = literal(self.demo.project_name if self.backend is None else self.backend.project.name)
        updater = getattr(self.controller, 'update_manager', None)
        if updater is not None and updater.available is not None:
            return '  Update available — Ctrl+U to install  /  '+self.state
        state = self.state + (' · reading earlier messages · Ctrl+End latest' if not self.follow else '')
        return f'  {state}  /  {project}  /  {pending} pending draft'+('s' if pending != 1 else '')

    def title(self):
        name = self.demo.project_name if self.backend is None else self.backend.project.name
        return [('class:accent', '  SILO'), ('class:muted', '  /  '+literal(name))]

    def project_action_allowed(self):
        if self.folder_dialog.opened:
            self.view.notice('Finish or cancel Add folder before changing projects.', warning=True)
            return False
        if self.busy or self.closing:
            self.view.notice('Wait for active work to finish before changing projects.', warning=True)
            return False
        if self.recovery_failed or not self.sidebar.available:
            self.view.notice('Project storage or the verified session is unavailable.', warning=True)
            return False
        return True

    def project_action(self, action, value):
        if not self.project_action_allowed(): return
        if action not in {'new', 'open'}: return
        if action == 'open' and value == self.sidebar.active_id:
            self.sidebar.cancel_form()
            return
        self.controller.model_menu.cancel()
        self.completer.choices = ()
        self.composer.buffer.complete_state = None
        self._begin_request('/project '+action+' '+value)

    def restore_project_transcript(self):
        self.lines.clear(); self.tones.clear(); self.spans.clear(); self.follow = True
        self.transcript.buffer.set_document(Document(''), bypass_readonly=True)
        if self.backend is None:
            saved = self._preview_transcripts.get(self.demo.project_id)
            if saved:
                self.lines, self.tones, self.spans = [list(part) for part in saved]
                content = '\n'.join(self.lines)
                self.transcript.buffer.set_document(Document(content, len(content)), bypass_readonly=True)
            else: self.view.header()
        else:
            for prompt, answer in self.backend.conversation.display():
                self.view.user(prompt); self.view.answer(answer)

    def hints(self):
        columns = self.app.output.get_size().columns
        if columns >= 80:
            columns -= self.model_width() + 1
        if columns < 40:
            return ' Enter · Ctrl+D quit'
        if columns < 60:
            return ' Enter send · Alt+Enter · Ctrl+D quit'
        if columns < 80:
            return ' Enter send · Alt+Enter line · PgUp/PgDn · Ctrl+D quit'
        return ' Enter send · Tab complete · Ctrl+C stop · Ctrl+D quit'

    def active_model(self):
        """Current loaded profile, without reading the selected-on-disk setting."""
        if self.backend is None:
            menu = self.demo.model_menu
            profile = next((p for p in menu.profiles if p['id'] == menu.selected), None)
            return 'Preview: ' + profile['display_name'] if profile else 'Preview: no active model'
        service = getattr(self.backend, 'service', None)
        if self.recovering or self.recovery_failed or not getattr(service, 'ready', False) or getattr(service, 'closed', False):
            return 'No active model'
        profile = getattr(service, 'model_profile', None)
        if profile:
            return literal(profile.get('display_name', profile['id']))
        model = getattr(service, 'model', None)
        return literal(getattr(model, 'stem', str(model))) if model else 'No active model'

    def model_width(self):
        from .terminal_rich import width
        return min(width(self.active_model()) + 1, max(1, self.app.output.get_size().columns - 39))

    def model_label(self):
        from .terminal_rich import width, cells
        label = literal(self.active_model()).replace('\n', ' ').replace('\t', ' ')
        columns = self.app.output.get_size().columns
        budget = max(1, self.model_width() if columns >= 80 else columns - 2)
        return label if width(label) <= budget else cells(label, max(1, budget - 1))[0] + '…'

    def append(self, text, tone, spans=()):
        if self.loop is None:
            self._append(text, tone, spans)
        else:
            self.loop.call_soon_threadsafe(self._append, text, tone, spans)

    def _append(self, text, tone, spans=()):
        cursor = self.transcript.buffer.cursor_position
        following = self.follow and cursor >= len(self.transcript.text)
        for line in text.split('\n'):
            self.lines.append(line)
            self.tones.append(tone)
            self.spans.append(spans if '\n' not in text else ())
        if len(self.lines) > 4000:
            removed = len('\n'.join(self.lines[:-4000])) + 1
            cursor = max(0, cursor - removed)
            del self.lines[:-4000]; del self.tones[:-4000]; del self.spans[:-4000]
        content = '\n'.join(self.lines)
        self.transcript.buffer.set_document(Document(content, len(content) if following else min(cursor, len(content))), bypass_readonly=True)
        self.app.invalidate()

    def progress(self, event):
        def update():
            labels = {'starting': 'Loading verified model', 'model': 'Generating', 'tools': 'Reading / preparing draft',
                      'complete': 'Validating complete', 'failed': 'Request stopped', 'cancelled': 'Cancelling', 'closed': 'Closed'}
            self.state = f'{labels[event.stage]} · {event.model_calls} model / {event.tool_calls} tool calls'
            self.app.invalidate()
        if self.loop is None: update()
        else: self.loop.call_soon_threadsafe(update)

    def stream_text(self, text):
        def update():
            self.live_text = '' if text is None else (self.live_text + literal(text))[-64 * 1024:]
            self.live.buffer.set_document(Document(self.live_text, len(self.live_text)), bypass_readonly=True)
            self.app.invalidate()
        try: current_loop = asyncio.get_running_loop()
        except RuntimeError: current_loop = None
        # Request finalization runs on this loop. Clear provisional text before
        # publishing idle state instead of leaving a queued clear behind it.
        if self.loop is None or current_loop is self.loop: update()
        else: self.loop.call_soon_threadsafe(update)

    def completion_valid(self):
        try:
            return self._catalog.revision == self.backend.workspace.broker.revision
        except Exception:
            return False

    async def refresh_completions(self):
        self.completer.choices = ()
        # Drop the previous menu without restoring an already-submitted prompt.
        self.composer.buffer.complete_state = None
        if self.backend is None:
            menu = self.demo.model_menu
            self.completer.ids['/project open '] = [(p['id'], p['name']) for p in self.demo.project_listing()]
            if menu.pending:
                phase, values = menu.pending
                names = {p['id']: p['display_name'] for p in menu.profiles}
                self.completer.choices = (tuple((str(i), value, f'{i}. {names.get(value, value.capitalize())}')
                                               for i, value in enumerate(values, 1)) if phase != 'confirm'
                                         else (('1', 'yes', 'yes — simulate removal'), ('2', 'no', 'no — keep model')))
            self.composer.buffer.complete_state = None
            return
        self.completer.mentions, self.completer.ids = (), {}
        try:
            catalog, ids = await asyncio.to_thread(self.controller.completion_snapshot)
            self._catalog = catalog
            self.completer.mentions, self.completer.ids = tuple(catalog.items), ids
            self.completer.valid = self.completion_valid
        except Exception:
            pass  # Missing/denied inventory never expands a grant or blocks chat.
        menu = self.controller.model_menu.pending
        if menu:
            phase, values = menu
            self.completer.choices = (tuple((str(i), value, f'{i}. {value.capitalize() if phase == "action" else value}') for i, value in enumerate(values, 1))
                                     if phase != 'confirm' else (('1', 'yes', 'yes — delete model'), ('2', 'no', 'no — keep model')))
        self.composer.buffer.complete_state = None

    def submit(self):
        if self.busy:
            self.view.notice('Work is still active. Your next message is kept; press Enter when Ready.')
            return
        request = self.composer.text.strip()
        if not request:
            return
        if self.recovery_failed and request not in {'/quit', '/exit', '/help'}:
            self.view.notice('The verified session is unavailable. Close SILO before continuing.', warning=True)
            return
        self.composer.text = ''
        if request in {'/quit', '/exit'}:
            self.close()
            return
        if request == '/multiline':
            self.view.notice('Use Alt+Enter for a new line in the input box, then Enter to send.')
            return
        if request == '/clear' and self.backend is None:
            self.demo.reset()
            self.lines.clear()
            self.tones.clear()
            self.spans.clear()
            self.transcript.buffer.set_document(Document(''), bypass_readonly=True)
            self.view.header()
            self.state = 'Conversation cleared'
            return
        self._begin_request(request)

    def _begin_request(self, request):
        if request.startswith(('/project new ', '/project open ', '/project close', '/project delete ')):
            self._project_revision += 1
            if self.backend is None:
                self._preview_transcripts[self.demo.project_id] = (list(self.lines), list(self.tones), list(self.spans))
            else:
                self.controller.sources.clear()
        if request.startswith('/') and request != '/example':
            self.view.user(request)
        self.model_request = self.backend is not None and (self.controller.model_menu.pending is not None
                             or request == '/model' or request.startswith('/model '))
        self.update_operation = request == '/update' or request.startswith('/update ')
        self.busy = True
        self.state = 'Working'
        self.demo.cancelled.clear()
        self.cancelled.clear()
        self.task = self.app.create_background_task(self._handle(request))

    async def _handle(self, request):
        project_change = request.startswith(('/project new ', '/project open ', '/project close', '/project delete '))
        try:
            if self.folder_dialog.pending:
                await asyncio.to_thread(self.folder_dialog.apply)
            else:
                await asyncio.to_thread(self.controller.handle, request)
            if self.backend is not None and self.controller.update_request is not None:
                self.closing = True
            self.state = ('Restart failed' if self.recovery_failed else
                          'Cancelled' if (self.cancelled.is_set() or self.demo.cancelled.is_set()) else 'Ready')
            if project_change or (self.backend is not None and request == '/clear'):
                self.restore_project_transcript()
            if project_change:
                self.sidebar.cancel_form()
            if self.folder_dialog.pending:
                if self.backend is None:
                    self._preview_transcripts.pop(self.demo.project_id, None)
                self.restore_project_transcript()
            self.folder_dialog.finish()
        except Exception as error:
            if self.backend is None and not self.folder_dialog.pending: self.reset_session()
            self.state = 'Request stopped'
            if project_change: self.restore_project_transcript()
            if self.folder_dialog.pending and self.backend is not None:
                try: self.restore_project_transcript()
                except Exception: pass  # Already cleared; an unavailable display must not trap the dialog.
            self.view.notice('Request stopped: '+str(error), warning=True)
            self.folder_dialog.finish(error)
        finally:
            self.stream_text(None)
            if self.backend is not None and self.cancelled.is_set() and not self.closing and not self.model_request and not self.update_operation:
                await self.recover_session()
            if not self.closing:
                await self.refresh_completions()
                await self.sidebar.refresh()
            self.busy = False
            self.task = None
            self.model_request = False
            self.update_operation = False
            self.app.invalidate()
            if self.closing:
                if self.backend is None: self.demo.reset()
                self.app.exit()

    async def recover_session(self):
        recover = getattr(self.backend, 'recover', None)
        if not callable(recover): return
        self.recovering = True
        self.state = 'Restarting verified session'
        self.view.notice('Cancelled. Reloading the verified model; old chat, reviews and code authority are cleared.')
        try:
            await asyncio.to_thread(recover)
            self.controller.sources.clear()
            omitted = getattr(getattr(self.backend, 'backend', self.backend), '_recovery_grants_omitted', 0)
            if omitted: self.view.notice(f'{omitted} changed folder grant(s) were omitted. Grant them again explicitly.', warning=True)
            self.state = 'Ready'
            self.view.notice('Ready again. Your next message has been kept.')
            self.recovery_failed = False
        except Exception:
            self.state = 'Restart failed'
            self.recovery_failed = True
            self.view.notice('Verified restart failed. Close SILO and inspect the installation before continuing.', warning=True)
        finally:
            self.recovering = False

    def close(self):
        if self.busy:
            self.closing = True
            self.cancel_request()
            self.state = 'Closing'
        else:
            if self.backend is None: self.demo.reset()
            self.app.exit()

    async def poll_schedules(self):
        from .workflows import ScheduleEngine
        from .project_store import ProjectSession
        if not isinstance(self.backend, ProjectSession): return
        self.controller.scheduler = ScheduleEngine(self.backend)
        while not self.closing:
            await asyncio.sleep(1)
            if self.busy or self.folder_dialog.opened or self.backend.record is None or self.controller.model_menu.pending is not None: continue
            now = self.controller.scheduler.clock()
            candidates = self.controller.scheduler.listing()
            if not any(row['project_id'] == self.backend.project.id and
                       (row['state'] == 'running' or row['enabled'] and row['next_due'] <= now)
                       for row in candidates.values()): continue
            self.busy = True; self.cancelled.clear(); self.state = 'Scheduled task'
            stop_polling = False
            try:
                events = await asyncio.to_thread(self.controller.scheduler.tick)
                for event in events:
                    self.view.notice('Scheduled task '+event['id']+': '+event['state'])
                if events: self.view.notice('Use /project context to inspect retained results and /review to inspect pending artifacts.')
            except Exception as error:
                self.view.notice('Scheduled task stopped: '+str(error), warning=True)
                stop_polling = True
            finally:
                self.stream_text(None)
                if self.cancelled.is_set() and not self.closing:
                    await self.recover_session()
                if not self.closing: await self.refresh_completions()
                self.busy = False
                if not self.recovery_failed: self.state = 'Ready'
                self.app.invalidate()
                if self.closing: self.app.exit()
            if self.closing or stop_polling: return

    def start(self):
        self.loop = asyncio.get_running_loop()
        self.app.create_background_task(self.refresh_completions())
        self.app.create_background_task(self.sidebar.refresh())
        if self.backend is not None:
            self.controller.start_update_checks()
            self.app.create_background_task(self.poll_schedules())

    def run(self):
        self.app.run(pre_run=self.start)
