"""Portable, scrolling terminal presentation. No model or authority imports."""
import os
import shutil
import sys
import textwrap
import unicodedata


def literal(text):
    """Never allow document/model text to emit terminal or bidi controls."""
    return ''.join(c if c in '\n\t' or not unicodedata.category(c).startswith('C')
                   else f'\\u{ord(c):04x}' for c in str(text))


def enable_color(stream):
    if not stream.isatty() or 'NO_COLOR' in os.environ or os.environ.get('TERM') == 'dumb':
        return False
    if os.name != 'nt':
        return True
    # Windows consoles need virtual-terminal processing; fall back to plain text.
    try:
        import ctypes
        import msvcrt
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel.SetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        handle = msvcrt.get_osfhandle(stream.fileno())
        mode = ctypes.c_ulong()
        return bool(kernel.GetConsoleMode(handle, ctypes.byref(mode)) and
                    kernel.SetConsoleMode(handle, mode.value | 0x0004))
    except (OSError, ValueError, AttributeError):
        return False


class TerminalView:
    COLORS = {'accent': '36', 'muted': '90', 'good': '32', 'warning': '33', 'bold': '1'}

    def __init__(self, output=None, *, plain=False, width=None):
        self.output = sys.stdout if output is None else output
        self.color = not plain and enable_color(self.output)
        self.fixed_width = width

    @property
    def width(self):
        return max(20, min(self.fixed_width or shutil.get_terminal_size((88, 24)).columns, 100))

    def _text(self, text):
        safe = literal(text)
        encoding = getattr(self.output, 'encoding', None)
        return safe.encode(encoding, 'backslashreplace').decode(encoding) if encoding else safe

    def style(self, text, tone):
        safe = self._text(text)
        return f'\033[{self.COLORS[tone]}m{safe}\033[0m' if self.color else safe

    def line(self, text='', tone=None):
        print(self.style(text, tone) if tone else self._text(text), file=self.output, flush=True)

    def body(self, text, *, indent='  ', tone=None):
        for line in self._text(text).expandtabs(4).split('\n'):
            for part in textwrap.wrap(line, width=max(1, self.width-len(indent)),
                                      replace_whitespace=False, drop_whitespace=False) or ['']:
                self.line(indent+part, tone)

    def header(self):
        self.line()
        self.line('SILO', 'accent')
        self.body('Super Intelligence for Local Offline Operations', tone='muted')
        self.line('-' * self.width, 'muted')
        self.body('Capacity study  /  Terminal design preview', tone='bold')
        self.body('Scripted replies. Sample data. No model or file access.', tone='warning')
        self.line()
        self.body('Try /example for a sample conversation, or /help for commands.', tone='muted')

    def user(self, text):
        self.line()
        self.line('YOU', 'muted')
        self.body(text)

    def activity(self, text):
        self.body('· '+text, tone='muted')

    def answer(self, text):
        self.line()
        self.line('SILO', 'accent')
        self.body(text)

    def notice(self, text, *, warning=False):
        self.line()
        self.body(text, tone='warning' if warning else 'muted')

    def ready(self, pending):
        self.line()
        self.body(f'Ready  /  Preview  /  {pending} pending draft'+('s' if pending != 1 else ''), tone='muted')
        self.body('Enter sends  ·  /multiline composes  ·  Ctrl+C cancels  ·  /quit exits', tone='muted')

    def prompt(self):
        return self.style('> ', 'accent')

    def draft(self, draft, *, review=False):
        self.line()
        self.line(('REVIEW' if review else 'UNSAVED DRAFT')+'  '+literal(draft.id), 'warning')
        self.body('Destination: '+draft.destination)
        self.body('Preview only: this destination is fictional; nothing is saved.', tone='muted')
        if review:
            self.line('-' * self.width, 'muted')
            self.body(draft.text)
            self.line('-' * self.width, 'muted')
            self.body('New file. All content above is proposed.', tone='muted')
            self.body(f'/approve {draft.id} simulates approval  /  /discard {draft.id} discards')
        else:
            self.body(f'/review {draft.id} to inspect the complete proposed text')
