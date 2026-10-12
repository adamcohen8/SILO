"""Completion from an idle host snapshot; keypresses never read documents."""
import re
from prompt_toolkit.completion import Completer, Completion
from .terminal_ui import literal


COMMANDS = {
    **{'/repository '+action:'Review working-copy application' for action in ('prepare ','review ','inspect ','transactions','apply ','reconcile ')},
    **{'/git '+action:'Explicit host Git operation' for action in ('open ','status','diff','prepare ','commit ','discard')},
    '/code-build ':'Open an enrolled offline build environment',
    '/build ':'Run a fixed build or test operation',
    '/navigate ':'Inspect snapshot symbols and diagnostics',
    '/language ':'Query a qualified semantic language service',
    '/environments':'List enrolled offline build environments',
    **{'/repository '+action: 'Inspect isolated repository work' for action in ('import ','status','diff','patch','export ')},
    **{'/task '+action: 'Manage retained task' for action in ('new ','list','show ','resume ','continue','pause','stop','reconcile ')},
    '/help': 'Show commands', '/reference ': 'Grant a Reference folder', '/draft ': 'Grant a Draft folder',
    '/folders': 'List folder grants', '/revoke ': 'Revoke a folder ID', '/clear': 'Clear chat and reviews',
    '/sources': 'Inspect cited sources', '/review ': 'Review a draft ID', '/approve ': 'Save reviewed bytes',
    '/discard ': 'Discard a draft ID', '/model': 'Open the model menu', '/model switch ': 'Switch model',
    '/model install ': 'Download a pinned model', '/model import ': 'Import exact local bytes',
    '/model remove ': 'Confirm model removal', '/models': 'List model profiles', '/hardware': 'Inspect hardware',
    '/project new ': 'Create an encrypted saved project', '/project list': 'List saved projects',
    '/project open ': 'Open project ID', '/project close': 'Close project and grants',
    '/project context': 'Inspect retained conversation', '/project delete ': 'Delete project ID',
    '/project retention ': 'Set retention days', '/project renew ': 'Renew expired project',
    '/project prune': 'Delete expired projects', '/instructions set ': 'Set task instructions',
    '/instructions show': 'Show instructions', '/instructions clear': 'Clear instructions',
    '/workflow save ': 'Save a workflow', '/workflow list': 'List workflows', '/workflow run ': 'Run workflow',
    '/workflow delete ': 'Delete workflow', '/schedule create ': 'Schedule a workflow',
    '/schedule list': 'List schedules', '/schedule cancel ': 'Cancel schedule',
    '/schedule reconcile ': 'Skip interrupted schedule slot', '/schedule tick': 'Check due schedules',
    '/backup ': 'Save encrypted backup', '/restore ': 'Restore encrypted backup',
    '/update check': 'Check published updates', '/update': 'Install available update',
    '/code-save': 'Retain encrypted code files', '/code-restore': 'Restore files into newly qualified workspace',
    '/code-edit': 'Edit files with execution disabled', '/code': 'Request qualified code workspace', '/code-close': 'Close code workspace',
    '/files': 'List code files', '/artifact ': 'Inspect code artifact', '/quit': 'Exit after cleanup',
}


class SiloCompleter(Completer):
    def __init__(self, commands=None):
        self.commands = COMMANDS if commands is None else commands
        self.mentions = ()
        self.choices = ()
        self.ids = {}
        self.valid = lambda: True

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if self.choices:
            for number, value, label in self.choices:
                if not text or value.casefold().startswith(text.casefold()) or number.startswith(text):
                    yield Completion(value, start_position=-len(text), display=literal(label))
            return
        if text.startswith('/') and '\n' not in text:
            for command, label in self.commands.items():
                if command.startswith(text):
                    yield Completion(command, start_position=-len(text), display=command.rstrip(), display_meta=label)
            for prefix, choices in self.ids.items():
                if text.startswith(prefix):
                    query = text[len(prefix):]
                    for value, label in choices:
                        if value.casefold().startswith(query.casefold()):
                            yield Completion(value, start_position=-len(query), display=literal(label))
        match = re.search(r'(?<![\w@/\\:])([@/])("[^"\n]*|[^\s"<>()[\]{};,!?:]*)$', text)
        if match and self.valid():
            sigil, query = match[1], match[2].strip('"').casefold()
            for item in self.mentions:
                if item.kind == ('file' if sigil == '@' else 'directory') and query in item.name.casefold():
                    yield Completion(item.token, start_position=-len(match[0]),
                                     display=literal(item.name), display_meta='Granted ' + item.kind)
