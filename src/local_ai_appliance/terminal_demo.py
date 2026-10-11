"""In-memory interaction design fixture. Never reads user files or calls a model."""
import argparse
from dataclasses import dataclass
import hashlib
import threading

from .terminal_ui import TerminalView


POLICY = 'Capacity is quantity times per-item capacity for eligible items only.\nRetired and quarantined items are excluded.\n'
INVENTORY = 'item,quantity,capacity_kg,status\nA,4,12,eligible\nB,3,20,eligible\nC,2,50,retired\nD,1,80,quarantined\n'
REPORT = '''# Synthetic capacity summary

Usable carrying capacity is 108 kg: (4 x 12 kg) + (3 x 20 kg).
Only eligible inventory contributes. Retired and quarantined items are excluded.

Policy: [source:S1:line:1-2]
Inventory: [source:S2:line:2-5]

This is a scripted UI example. No script, tests, or chart were executed.
'''
EXAMPLE = 'Read the capacity policy and inventory, then draft a short cited summary.'
HELP = '''/example          Walk through a cited reply and unsaved draft
/folders          Show the fictional Reference and Draft folders
/sources          Inspect sample citations, locators and source hashes
/drafts           List pending sample drafts
/review D1        Show the full proposed text and destination
/approve D1       Simulate approval after review; writes no file
/discard D1       Discard the pending sample draft
/multiline        Compose several lines; a single . sends
/clear            Reset the demo conversation and pending drafts
/help             Show this list
/quit             Close the preview'''


@dataclass(frozen=True)
class DemoDraft:
    id: str
    destination: str
    text: str


class DemoSession:
    def __init__(self, view, *, delay=0.2):
        self.view, self.delay = view, delay
        self.pending = {}
        self.reviewed = {}
        self.has_sources = False
        self.cancelled = threading.Event()

    def reset(self):
        self.pending.clear()
        self.reviewed.clear()
        self.has_sources = False

    def ask(self, prompt):
        self.reset()
        self.view.user(prompt)
        if prompt != EXAMPLE:
            self.view.answer('This preview uses scripted replies. Use /example to try the capacity workflow. '
                             'Connecting a local model is a separate integration step.')
            return
        try:
            for stage in ('Demo: inspecting policy.txt', 'Demo: inspecting inventory.csv',
                          'Demo: preparing a cited summary'):
                if self.cancelled.is_set():
                    raise InterruptedError
                self.view.activity(stage)
                if self.cancelled.wait(self.delay):
                    raise InterruptedError
        except (KeyboardInterrupt, InterruptedError):
            self.reset()
            self.view.notice('Cancelled. No sample draft retained.')
            return
        self.has_sources = True
        draft = DemoDraft('D1', 'Draft / capacity-summary.md', REPORT)
        self.pending[draft.id] = draft
        self.view.answer('Usable carrying capacity is 108 kg.\n\n'
                         '  4 items x 12 kg = 48 kg\n'
                         '  3 items x 20 kg = 60 kg\n\n'
                         'The policy counts eligible items only; retired and quarantined items are excluded. '
                         '[source:S1:line:1-2]\n'
                         'The inventory supplies the quantities, capacities and status. [source:S2:line:2-5]\n\n'
                         'I have prepared a sample summary for review. This is scripted preview content.')
        self.view.body('2 sample sources  /  /sources for details', tone='muted')
        self.view.draft(draft)

    def handle(self, line):
        command, _, arg = line.partition(' ')
        arg = arg.strip()
        if command in {'/quit', '/exit'}:
            return False
        if command == '/example':
            self.ask(EXAMPLE)
        elif command == '/help':
            self.view.answer(HELP)
        elif command == '/clear':
            self.reset()
            self.view.notice('Demo context and drafts cleared. Terminal scrollback remains visible.')
        elif command == '/folders':
            self.view.answer('Reference  /  Synthetic policy and inventory  /  Read only\n'
                             'Draft      /  Sample output destination       /  Reviewed new copies\n\n'
                             'These are fictional folders. Code access awaits the contained runner.')
        elif command == '/sources':
            if not self.has_sources:
                self.view.notice('No sources in this demo conversation. Try /example.')
            else:
                for name, token, content in (
                        ('policy.txt', '[source:S1:line:1-2]', POLICY),
                        ('inventory.csv', '[source:S2:line:2-5]', INVENTORY)):
                    self.view.line()
                    self.view.body(name+'  '+token, tone='accent')
                    self.view.body('Sample SHA-256: '+hashlib.sha256(content.encode()).hexdigest(), tone='muted')
                    self.view.body(content.rstrip())
        elif command == '/drafts':
            if not self.pending:
                self.view.notice('No pending drafts.')
            for draft in self.pending.values():
                self.view.draft(draft)
        elif command in {'/review', '/approve', '/discard'}:
            draft = self.pending.get(arg)
            if draft is None:
                self.view.notice('Choose a pending draft ID. Use /drafts to list them.', warning=True)
            elif command == '/review':
                self.view.draft(draft, review=True)
                self.reviewed[arg] = draft
            elif command == '/discard':
                self.pending.pop(arg)
                self.reviewed.pop(arg, None)
                self.view.notice('Sample draft discarded.')
            elif self.reviewed.get(arg) != draft:
                self.view.notice(f'Review the current text first: /review {arg}', warning=True)
            else:
                self.pending.pop(arg)
                self.reviewed.pop(arg)
                self.view.notice('Simulated approval complete. No file was saved.')
        elif line.startswith('/'):
            self.view.notice('Unknown command. Use /help. No action was taken.', warning=True)
        elif line.strip():
            self.ask(line)
        return True

    def run(self, *, read=input):
        self.view.header()
        while True:
            self.view.ready(len(self.pending))
            try:
                line = read(self.view.prompt())
                if line == '/multiline':
                    self.view.notice('Compose your request. Enter a single . to send; Ctrl+C discards.')
                    lines = []
                    while (part := read('  ')) != '.':
                        lines.append(part)
                    line = '\n'.join(lines)
                if not self.handle(line):
                    break
            except KeyboardInterrupt:
                self.view.notice('Input cancelled. Ready for another request.')
            except EOFError:
                break
        self.reset()
        self.view.notice('Preview closed.')


def main(argv=None):
    parser = argparse.ArgumentParser(description='SILO terminal design preview; scripted sample data only')
    parser.add_argument('--plain', action='store_true', help='Disable color')
    parser.add_argument('--width', type=int, help='Fixed width for --tour or --scrolling (20-100 columns)')
    parser.add_argument('--tour', action='store_true', help='Print a sample interaction and exit')
    parser.add_argument('--scrolling', action='store_true', help='Use the earlier line-input preview')
    args = parser.parse_args(argv)
    if args.width is not None and not 20 <= args.width <= 100:
        parser.error('--width must be between 20 and 100')
    if not args.tour and not args.scrolling:
        try:
            from .terminal_fullscreen import FullScreenPreview
        except ModuleNotFoundError as error:
            if error.name not in {'prompt_toolkit', 'wcwidth'}:
                raise
            parser.exit(1, 'Full-screen preview requires the terminal extra. Install requirements/terminal-preview.txt\n'
                        'in your development environment, or use --scrolling for the dependency-free preview.\n')
        import sys
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            parser.exit(1, 'Full-screen mode needs an interactive terminal. Use --tour for redirected output.\n')
        FullScreenPreview(plain=args.plain).run()
        return 0
    view = TerminalView(plain=args.plain, width=args.width)
    demo = DemoSession(view, delay=0 if args.tour else 0.2)
    if args.tour:
        view.header()
        for command in ('/example', '/review D1', '/approve D1'):
            if command != '/example':
                view.user(command)
            demo.handle(command)
        view.ready(len(demo.pending))
    else:
        demo.run()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
