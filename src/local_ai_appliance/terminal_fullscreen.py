"""Full-window design preview; the host backend remains separate."""
import asyncio
import os
import threading

from prompt_toolkit import Application
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.bindings.scroll import scroll_page_down, scroll_page_up
from prompt_toolkit.layout import HSplit, Layout, VSplit, Window, ConditionalContainer
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea

from .terminal_demo import DemoSession
from .terminal_ui import TerminalView, literal
from .terminal_completion import SiloCompleter


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
        return max(20, self.preview.app.output.get_size().columns - 4)

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
                ('/example', '/format', '/help', '/folders', '/sources', '/drafts', '/review D1',
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
        bindings = KeyBindings()

        @bindings.add('enter', eager=True)
        def send(event):
            completion = self.composer.buffer.complete_state
            if completion is not None and completion.completions:
                self.composer.buffer.apply_completion(completion.current_completion or completion.completions[0])
                return
            self.submit()

        @bindings.add('escape', 'enter', eager=True)
        def newline(event):
            self.composer.buffer.insert_text('\n')

        @bindings.add('f2', eager=True)
        def commands(event):
            if self.composer.text:
                self.view.notice('Type / or a command prefix and press Tab. Your input has been kept.')
            else:
                self.composer.text = '/'
                self.composer.buffer.start_completion(select_first=False)

        @bindings.add('f3', eager=True)
        def files(event):
            if self.backend is not None and not self.completer.mentions:
                self.view.notice('No granted files to suggest. Use /reference PATH first.')
                return
            prefix = '' if not self.composer.text or self.composer.text.endswith((' ', '\n')) else ' '
            self.composer.buffer.insert_text(prefix + '@')
            self.composer.buffer.start_completion(select_first=False)

        @bindings.add('c-c', eager=True)
        def cancel(event):
            if self.busy:
                self.cancel_request()
                self.state = 'Cancelling'
            else:
                self.composer.text = ''
                if self.backend is not None and self.controller.model_menu.pending is not None:
                    self.controller.model_menu.cancel()
                    self.state = 'Model menu closed'
                else: self.state = 'Input cleared'
            event.app.layout.focus(self.composer)

        @bindings.add('c-d', eager=True)
        def quit_preview(event):
            self.close()

        @bindings.add('c-u', eager=True)
        def update(event):
            if self.backend is None:
                self.view.notice('Updates require the standalone installation', warning=True)
            elif self.busy:
                self.view.notice('Wait for active work to finish before updating', warning=True)
            elif self.composer.text:
                self.view.notice('Send or clear your input before updating', warning=True)
            elif self.controller.model_menu.pending is not None:
                self.view.notice('Close the model menu before updating', warning=True)
            else:
                self.composer.text = '/update'
                self.submit()

        @bindings.add('pageup', eager=True)
        def earlier(event):
            self.follow = False
            event.app.layout.focus(self.transcript)
            scroll_page_up(event)
            event.app.layout.focus(self.composer)

        @bindings.add('pagedown', eager=True)
        def later(event):
            event.app.layout.focus(self.transcript)
            scroll_page_down(event)
            self.follow = self.transcript.buffer.cursor_position >= len(self.transcript.text)
            event.app.layout.focus(self.composer)

        @bindings.add('c-end', eager=True)
        def latest(event):
            self.follow = True
            self.transcript.buffer.cursor_position = len(self.transcript.text)
            event.app.layout.focus(self.composer)

        # Editor shortcuts remain handled by prompt_toolkit's standard bindings.
        root = HSplit([
            Window(FormattedTextControl([('class:accent', '  SILO'),
                                         ('class:muted', '  /  Capacity study' if backend is None else '  /  Local workspace')]), height=1),
            Window(FormattedTextControl('  Design preview · Scripted replies · No file access' if backend is None else '  Contained Windows evaluation · Public / synthetic data · /help'),
                   height=1, style='class:muted'),
            Window(height=1, char='─', style='class:rule'),
            VSplit([Window(width=1), self.transcript, Window(width=1)]),
            ConditionalContainer(Frame(self.live, title='Live response · provisional until validated'),
                                 filter=Condition(lambda: bool(self.live_text))),
            Window(FormattedTextControl(self.status), height=1, style='class:status'),
            Frame(self.composer, title='Message SILO', style='class:frame'),
            Window(FormattedTextControl(self.hints), height=1, style='class:muted'),
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
        project = 'Preview' if self.backend is None else literal(self.backend.project.name)
        updater = getattr(self.controller, 'update_manager', None)
        if updater is not None and updater.available is not None:
            return '  Update available — Ctrl+U to install  /  '+self.state
        state = self.state + (' · reading earlier messages · Ctrl+End latest' if not self.follow else '')
        return f'  {state}  /  {project}  /  {pending} pending draft'+('s' if pending != 1 else '')

    def hints(self):
        columns = self.app.output.get_size().columns
        if columns < 40:
            return ' Enter send · Ctrl+D quit'
        if columns < 60:
            return ' Enter send · Alt+Enter · Ctrl+D quit'
        if columns < 80:
            return ' Enter send · Alt+Enter line · PgUp/PgDn · Ctrl+D quit'
        return ' Enter send · Tab complete · F2 commands · F3 files · Ctrl+C stop · Ctrl+D quit'

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
        if self.loop is None: update()
        else: self.loop.call_soon_threadsafe(update)

    def completion_valid(self):
        try:
            return self._catalog.revision == self.backend.workspace.broker.revision
        except Exception:
            return False

    async def refresh_completions(self):
        self.completer.choices = ()
        if self.backend is None: return
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
            self.completer.choices = (tuple((str(i), value, f'{i}. {value}') for i, value in enumerate(values, 1))
                                     if phase != 'confirm' else (('1', 'yes', 'yes — delete model'), ('2', 'no', 'no — keep model')))

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
        try:
            await asyncio.to_thread(self.controller.handle, request)
            if self.backend is not None and self.controller.update_request is not None:
                self.closing = True
            self.state = ('Restart failed' if self.recovery_failed else
                          'Cancelled' if (self.cancelled.is_set() or self.demo.cancelled.is_set()) else 'Ready')
            if self.backend is not None and request.startswith(('/clear', '/project open', '/project close', '/project delete')):
                self.lines.clear(); self.tones.clear(); self.spans.clear(); self.follow = True
                self.transcript.buffer.set_document(Document(''), bypass_readonly=True)
                for prompt, answer in self.backend.conversation.display():
                    self.view.user(prompt); self.view.answer(answer)
        except Exception as error:
            if self.backend is None: self.reset_session()
            self.state = 'Request stopped'
            self.view.notice('Request stopped: '+str(error), warning=True)
        finally:
            self.stream_text(None)
            if self.backend is not None and self.cancelled.is_set() and not self.closing and not self.model_request and not self.update_operation:
                await self.recover_session()
            if not self.closing:
                await self.refresh_completions()
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
            if self.busy or self.backend.record is None or self.controller.model_menu.pending is not None: continue
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
        if self.backend is not None:
            self.controller.start_update_checks()
            self.app.create_background_task(self.poll_schedules())

    def run(self):
        self.app.run(pre_run=self.start)
