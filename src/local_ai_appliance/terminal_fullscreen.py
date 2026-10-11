"""Full-window design preview; the host backend remains separate."""
import asyncio
import os
import threading

from prompt_toolkit import Application
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.bindings.scroll import scroll_page_down, scroll_page_up
from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea

from .terminal_demo import DemoSession
from .terminal_ui import TerminalView, literal


class TranscriptLexer(Lexer):
    def __init__(self, preview):
        self.preview = preview

    def lex_document(self, document):
        lines = document.lines
        tones = list(self.preview.tones)
        return lambda number: [('class:'+tones[number] if number < len(tones) else '', lines[number])]


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
        self.body('Try /example to explore a cited reply and draft review.', tone='muted')
        self.body('/help shows commands. All content here is synthetic.', tone='muted')


class FullScreenPreview:
    def __init__(self, *, plain=False, input=None, output=None, delay=0.2, backend=None, client_options=None):
        self.lines, self.tones = [], []
        self.loop = None
        self.busy = False
        self.closing = False
        self.task = None
        self.model_request = False
        self.state = 'Ready'
        self.transcript = TextArea(read_only=True, scrollbar=True, wrap_lines=True,
                                   focusable=True, lexer=TranscriptLexer(self))
        self.composer = TextArea(multiline=True, wrap_lines=True, prompt='> ',
                                 height=Dimension(min=1, preferred=2, max=4),
                                 read_only=Condition(lambda: self.busy), style='class:input')
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
            self.submit()

        @bindings.add('escape', 'enter', eager=True)
        def newline(event):
            if not self.busy:
                self.composer.buffer.insert_text('\n')

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

        @bindings.add('pageup', eager=True)
        def earlier(event):
            event.app.layout.focus(self.transcript)
            scroll_page_up(event)
            event.app.layout.focus(self.composer)

        @bindings.add('pagedown', eager=True)
        def later(event):
            event.app.layout.focus(self.transcript)
            scroll_page_down(event)
            event.app.layout.focus(self.composer)

        @bindings.add('c-end', eager=True)
        def latest(event):
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
        })
        self.app = Application(layout=Layout(root, focused_element=self.composer),
                               key_bindings=bindings, style=style, full_screen=True,
                               mouse_support=True, input=input, output=output)
        if backend is None:
            self.view.header()
        else:
            self.view.notice('Ready. /reference PATH and /draft PATH grant access. /project new NAME enables encrypted retention.')
            conversation = getattr(backend, 'conversation', None)
            if conversation:
                for prompt, answer in conversation.display():
                    self.view.user(prompt); self.view.answer(answer)

    def cancel_request(self):
        self.cancelled.set()
        if self.backend is None:
            self.demo.cancelled.set()
        else:
            if self.model_request: self.controller.model_menu.cancel()
            else: self.backend.cancel()

    def reset_session(self):
        if self.backend is None:
            self.demo.reset()
        else:
            self.backend.clear_chat()

    def status(self):
        pending = (len(self.demo.pending) if self.backend is None else
                   len(self.backend.workspace.pending_proposals())) if not self.busy else 0
        project = 'Preview' if self.backend is None else literal(self.backend.project.name)
        return f'  {self.state}  /  {project}  /  {pending} pending draft'+('s' if pending != 1 else '')

    def hints(self):
        columns = self.app.output.get_size().columns
        if columns < 40:
            return ' Enter send · Ctrl+D quit'
        if columns < 60:
            return ' Enter send · Alt+Enter · Ctrl+D quit'
        if columns < 80:
            return ' Enter send · Alt+Enter line · PgUp/PgDn · Ctrl+D quit'
        return ' Enter send · Alt+Enter line · PgUp/PgDn scroll · Ctrl+C cancel · Ctrl+D quit'

    def append(self, text, tone):
        if self.loop is None:
            self._append(text, tone)
        else:
            self.loop.call_soon_threadsafe(self._append, text, tone)

    def _append(self, text, tone):
        for line in text.split('\n'):
            self.lines.append(line)
            self.tones.append(tone)
        if len(self.lines) > 4000:
            del self.lines[:-4000]; del self.tones[:-4000]
        content = '\n'.join(self.lines)
        self.transcript.buffer.set_document(Document(content, len(content)), bypass_readonly=True)
        self.app.invalidate()

    def submit(self):
        if self.busy:
            return
        request = self.composer.text.strip()
        if not request:
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
            self.transcript.buffer.set_document(Document(''), bypass_readonly=True)
            self.view.header()
            self.state = 'Conversation cleared'
            return
        if request.startswith('/') and request != '/example':
            self.view.user(request)
        self.model_request = self.backend is not None and (self.controller.model_menu.pending is not None
                             or request == '/model' or request.startswith('/model '))
        self.busy = True
        self.state = 'Working'
        self.demo.cancelled.clear()
        self.cancelled.clear()
        self.task = self.app.create_background_task(self._handle(request))

    async def _handle(self, request):
        try:
            await asyncio.to_thread(self.controller.handle, request)
            self.state = 'Cancelled' if (self.cancelled.is_set() or self.demo.cancelled.is_set()) else 'Ready'
            if self.backend is not None and request.startswith(('/clear', '/project open', '/project close', '/project delete')):
                self.lines.clear(); self.tones.clear()
                self.transcript.buffer.set_document(Document(''), bypass_readonly=True)
                for prompt, answer in self.backend.conversation.display():
                    self.view.user(prompt); self.view.answer(answer)
        except Exception as error:
            if self.backend is None: self.reset_session()
            self.state = 'Request stopped'
            self.view.notice('Request stopped: '+str(error), warning=True)
        finally:
            self.busy = False
            self.task = None
            self.model_request = False
            self.app.invalidate()
            if self.closing:
                if self.backend is None: self.demo.reset()
                self.app.exit()

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
                self.busy = False; self.state = 'Ready'; self.app.invalidate()
                if self.closing: self.app.exit()
            if self.closing or stop_polling: return

    def start(self):
        self.loop = asyncio.get_running_loop()
        if self.backend is not None: self.app.create_background_task(self.poll_schedules())

    def run(self):
        self.app.run(pre_run=self.start)
