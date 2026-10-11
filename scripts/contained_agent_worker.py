"""Fixed synthetic-evaluation worker; private framed pipes, no host authority."""
from types import SimpleNamespace
import json
import socket
import subprocess
import sys
import time

from local_ai_appliance.agent import DocumentAgent, Source
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.model import json_bytes, strict_json
from local_ai_appliance.windows_model import WindowsSocketChatModel
from local_ai_appliance.model_adapters import model_adapter
from local_ai_appliance.worker_errors import failure_code

LIMIT = 256*1024


class Channel:
    def __init__(self):
        initial = strict_json(sys.stdin.buffer.readline(LIMIT+1))
        if set(initial) != {'session', 'sequence', 'kind', 'payload'} or initial['sequence'] != 0 or initial['kind'] != 'initial':
            raise ValueError('Invalid initial IPC frame')
        self.session, self.sequence, self.initial = initial['session'], 1, initial['payload']

    def send(self, kind, payload):
        frame = json_bytes({'session': self.session, 'sequence': self.sequence, 'kind': kind, 'payload': payload})
        if len(frame) >= LIMIT:
            raise ValueError('IPC frame exceeds bounds')
        sys.stdout.buffer.write(frame+b'\n')
        sys.stdout.buffer.flush()

    def request(self, payload):
        self.send('request', payload)
        response = strict_json(sys.stdin.buffer.readline(LIMIT+1))
        if (set(response) != {'session', 'sequence', 'kind', 'payload'}
                or response['session'] != self.session or response['sequence'] != self.sequence
                or response['kind'] != 'response'):
            raise ValueError('Invalid IPC response')
        self.sequence += 1
        response = response['payload']
        if response.get('ok') is not True:
            raise AccessDenied(response.get('error', 'Host denied the request'))
        return response['value']

    def display(self, payload):
        self.send('display', payload)
        self.sequence += 1


class LiveOutput:
    """Best-effort display cap never expands the tool request budget."""
    def __init__(self, channel):
        self.channel = channel
        self.events = self.bytes = 0
        self.pending = ''
        self.last = time.monotonic()

    def send(self, value):
        if self.events >= 128:
            return
        self.channel.display(value)
        self.events += 1

    def flush(self):
        while self.pending and self.events < 128 and self.bytes < 64 * 1024:
            text, self.pending = self.pending[:256], self.pending[256:]
            size = len(text.encode('utf-8'))
            if self.bytes + size > 64 * 1024:
                self.pending = ''
                return
            self.send({'type': 'text', 'text': text})
            self.bytes += size
        self.pending = ''
        self.last = time.monotonic()

    def text(self, text):
        if self.events >= 128 or self.bytes >= 64 * 1024:
            return
        self.pending += text
        if len(self.pending) >= 128 or time.monotonic() - self.last >= .05:
            self.flush()

    def progress(self, stage, model_calls, tool_calls):
        self.flush()
        self.send({'type': 'reset'})
        self.send({'type': 'progress', 'stage': stage,
                   'model_calls': model_calls, 'tool_calls': tool_calls})


class RemoteWorkspace:
    def __init__(self, channel):
        self.channel = channel
        self.proposal_paths = {}
        metadata = channel.initial
        self.broker = SimpleNamespace(revision=metadata['permission_revision'],
            folders=lambda: tuple(SimpleNamespace(**f) for f in metadata['folders']))
        self.folder_inventory = metadata.get('folder_inventory')
        self.folder_references = metadata.get('folder_references', [])

    def pending_proposals(self):
        return tuple(SimpleNamespace(id=i, destination_path=self.proposal_paths.get(i, ''))
                     for i in self.channel.request({'op': 'pending'}))

    def discard(self, identifier):
        self.channel.request({'op': 'discard', 'id': identifier})


class RemoteAgent(DocumentAgent):
    def _dispatch(self, name, args, sources):
        self._validate_arguments(name, args)
        value = self.workspace.channel.request({'op': 'tool', 'name': name, 'arguments': args})
        if value['proposal_id']:
            self.workspace.proposal_paths[value['proposal_id']] = args['destination_path']
        return value['result'], Source(**value['source']) if value['source'] else None, value['proposal_id']


class RemoteCodeAgent(RemoteAgent):
    def __init__(self,*args,**kwargs):
        from local_ai_appliance.code_agent import ALL_SCHEMAS,CODE_PROMPT
        super().__init__(*args,system_prompt=CODE_PROMPT,**kwargs)
        self.tool_schemas=ALL_SCHEMAS

    @staticmethod
    def _validate_arguments(name,args):
        from local_ai_appliance.code_agent import CodeAgent
        return CodeAgent._validate_arguments(name,args)


def probe_network(tests):
    result = []
    for test in tests:
        s = socket.socket(test['family'], test['kind'])
        s.settimeout(1)
        try:
            if test['kind'] == socket.SOCK_DGRAM:
                s.sendto(b'local-ai-contained-workflow', (test['address'], test['port']))
            else:
                s.connect((test['address'], test['port']))
            value = {'id': test['id'], 'api_accepted': True}
        except OSError as error:
            value = {'id': test['id'], 'api_accepted': False, 'winerror': getattr(error, 'winerror', None)}
        finally:
            s.close()
        result.append(value)
    return result


def main():
    channel = Channel()
    initial = channel.initial
    boundaries = {}
    if initial.get('check_boundary'):
        for name, request in [('approval', {'op': 'approve', 'id': 'unavailable'}),
                              ('shell', {'op': 'tool', 'name': 'run_command', 'arguments': {}}),
                              ('ungranted_read', {'op': 'tool', 'name': 'read_text',
                               'arguments': {'folder_id': 'ungranted', 'path': 'capacity.txt'}})]:
            try:
                channel.request(request)
                boundaries[name] = False
            except AccessDenied:
                boundaries[name] = True
        try:
            subprocess.run([sys.executable, '-I', '-B', '-c', 'pass'], timeout=5,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=8, check=True)
            boundaries['child_process'] = False
        except OSError as error:
            boundaries['child_process'] = getattr(error, 'winerror', None) == 367
    network_before = probe_network(initial.get('network', []))
    live = LiveOutput(channel) if initial.get('live_output') is True else None
    model = WindowsSocketChatModel(initial['endpoint'], 'contained-synthetic', api_token=initial['token'],
        evaluation=True, **model_adapter(initial.get('model_adapter', 'nemotron3')).client_options(), timeout=60,
        on_text=live.text if live else None)
    workspace = RemoteWorkspace(channel)
    coding = initial.get('code_enabled') is True
    agent = (RemoteCodeAgent if coding else RemoteAgent)(workspace, model, max_model_calls=16 if coding else 8,
                        max_tool_calls=48 if coding else 16, max_context_bytes=96*1024 if coding else 64*1024,
                        max_citation_repairs=1, instructions=initial.get('instructions', ''),
                        progress=live.progress if live else lambda *args: None)
    try:
        result = agent.run(initial['prompt'], history=initial.get('history', []),
                           sources=tuple(Source(**s) for s in initial.get('history_sources', [])))
    except Exception as error:
        channel.send('result', {'failure': failure_code(error)})
        return 0
    if live: live.flush()
    from langsmith.utils import tracing_is_enabled
    channel.send('result', {'answer': result.answer, 'references': [s.reference for s in result.citations],
        'proposal_ids': [p.id for p in result.proposals], 'model_calls': result.model_calls,
        'tool_calls': result.tool_calls, 'boundaries': boundaries,
        'history_dropped': result.history_dropped,
        'network_before': network_before, 'network_after': probe_network(initial.get('network', [])),
        'tracing_enabled': tracing_is_enabled()})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
