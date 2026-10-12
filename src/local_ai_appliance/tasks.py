"""Encrypted host-owned task journals. Checkpoints confer no execution authority."""
import hashlib
import re
import secrets
import time
from .folders import AccessDenied
from .model import json_bytes

KINDS = {'directive','tool_intent','tool_result','answer','pause','stop','resume','failure','reconcile','continuation'}

STATES = {'ready', 'running', 'paused', 'stopped', 'complete', 'blocked', 'unknown'}


class TaskStore:
    def __init__(self, vault, *, clock=time.time):
        self.vault, self.clock = vault, clock

    @staticmethod
    def key(identifier):
        if not isinstance(identifier, str) or not re.fullmatch('[a-f0-9]{32}', identifier):
            raise AccessDenied('Invalid task identity')
        return 'task-' + identifier

    def create(self, project_id, objective, scope):
        if not isinstance(objective, str) or not objective.strip() or len(objective.encode()) > 16384:
            raise AccessDenied('Task objective must be nonempty and at most 16 KiB; attach larger source material')
        if (not isinstance(project_id,str) or not re.fullmatch('[a-f0-9]{32}',project_id)
                or not isinstance(scope,str) or not re.fullmatch('[a-f0-9]{64}',scope)):
            raise AccessDenied('Task requires a saved project and current scope digest')
        identifier = secrets.token_hex(16)
        self.vault.put(self.key(identifier), {'format': 1, 'id': identifier, 'project_id': project_id,
            'objective': objective, 'scope': scope, 'state': 'ready', 'sequence': 0,
            'digest': '0'*64, 'updated': self.clock(), 'inflight': False})
        return identifier

    def load(self, identifier):
        value = self.vault.get(self.key(identifier))
        if (not isinstance(value, dict) or set(value) != {'format','id','project_id','objective','scope',
                'state','sequence','digest','updated','inflight'} or value['format'] != 1 or value['id'] != identifier
                or not isinstance(value['state'], str) or value['state'] not in STATES or type(value['sequence']) is not int or value['sequence'] < 0
                or type(value['inflight']) is not bool or type(value['format']) is not int
                or not isinstance(value['digest'], str) or not re.fullmatch('[a-f0-9]{64}', value['digest'])
                or not isinstance(value['scope'], str) or not re.fullmatch('[a-f0-9]{64}', value['scope'])
                or not isinstance(value['project_id'], str) or not re.fullmatch('[a-f0-9]{32}', value['project_id'])
                or not isinstance(value['objective'], str) or not value['objective'].strip()
                or len(value['objective'].encode()) > 16384):
            raise AccessDenied('Invalid or missing retained task')
        return value

    def append(self, identifier, kind, data, *, state=None):
        if kind not in KINDS:
            raise AccessDenied('Unknown task event')
        if len(json_bytes(data)) > 1024*1024:
            raise AccessDenied('Task event exceeds its storage frame; page large content')
        if state is not None and state not in STATES:
            raise AccessDenied('Unknown task state')
        with self.vault.transaction():
            head = self.load(identifier)
            if kind == 'tool_intent' and head['inflight']:
                raise AccessDenied('Prior tool outcome is unknown; no overlapping or replayed intent')
            number = head['sequence'] + 1
            name = f'taskevent-{identifier}-{number:020d}'
            if self.vault.get(name) is not None:
                raise AccessDenied('Interrupted checkpoint needs reconciliation; no automatic replay')
            event = {'sequence': number, 'previous': head['digest'], 'kind': kind, 'data': data}
            digest = hashlib.sha256(json_bytes(event)).hexdigest()
            self.vault.put(name, event)
            head.update(sequence=number, digest=digest, updated=self.clock())
            if kind == 'tool_intent': head['inflight'] = True
            if kind == 'tool_result': head['inflight'] = False
            if state is not None: head['state'] = state
            self.vault.put(self.key(identifier), head)
            return head

    def events(self, identifier, *, start=1, limit=20):
        if type(start) is not int or start < 1 or type(limit) is not int or not 1 <= limit <= 100:
            raise AccessDenied('Use a paginated task history')
        head = self.load(identifier)
        result = []
        # Authenticate continuity through the requested page, including head.
        previous = '0'*64
        for number in range(1, head['sequence'] + 1):
            event = self.vault.get(f'taskevent-{identifier}-{number:020d}')
            if (not isinstance(event, dict) or set(event) != {'sequence','previous','kind','data'}
                    or type(event['sequence']) is not int or event['sequence'] != number
                    or event['previous'] != previous or not isinstance(event['kind'],str) or event['kind'] not in KINDS):
                raise AccessDenied('Task journal is incomplete or changed')
            previous = hashlib.sha256(json_bytes(event)).hexdigest()
            if start <= number < start + limit: result.append(event)
        if previous != head['digest']:
            raise AccessDenied('Task head differs from its journal')
        return result

    def listing(self, project_id):
        return [value for name in self.vault.names('task-')
                if (value := self.load(name[5:]))['project_id'] == project_id]

    def resume(self, identifier, scope):
        head = self.load(identifier)
        self.events(identifier)  # Check full journal before restoring anything.
        orphan = self.vault.get(f"taskevent-{identifier}-{head['sequence']+1:020d}")
        if orphan is not None:
            self.vault.put(self.key(identifier), dict(head, state='unknown'))
            raise AccessDenied('Interrupted checkpoint has an unknown outcome; reconcile before resuming')
        if head['scope'] != scope:
            raise AccessDenied('Task permissions, sources or model changed; create a new task with current authority')
        if head['state'] == 'running' or head['inflight']:
            self.vault.put(self.key(identifier), dict(head, state='unknown'))
            raise AccessDenied('Interrupted work has an unknown outcome; reconcile owned execution before resuming')
        if head['state'] in {'stopped', 'unknown'}:
            raise AccessDenied('Stopped or unknown tasks require explicit reconciliation or a new task')
        return self.append(identifier, 'resume', {}, state='ready')

    def reconcile(self, identifier):
        # Host command only. Never replay an intent or restore a pending approval.
        with self.vault.transaction():
            head = self.load(identifier)
            if head['state'] not in {'unknown', 'running'} and not head['inflight']:
                raise AccessDenied('Task has no uncertain action to reconcile')
            self.events(identifier)
            orphan = f"taskevent-{identifier}-{head['sequence']+1:020d}"
            quarantined = None
            if (partial := self.vault.get(orphan)) is not None:
                quarantined = f"taskorphan-{identifier}-{head['sequence']+1:020d}"
                previous = self.vault.get(quarantined)
                if previous is not None and previous != partial:
                    raise AccessDenied('Conflicting interrupted checkpoint evidence; inspect before reconciliation')
                if previous is None: self.vault.put(quarantined, partial)
                self.vault.delete(orphan)
            head.update(state='paused', inflight=False)
            self.vault.put(self.key(identifier), head)
            return self.append(identifier, 'reconcile', {'action': 'operator-inspected; uncertain action not replayed', 'quarantined_record': quarantined}, state='paused')

    def delete_project(self, project_id):
        for head in self.listing(project_id):
            for prefix in ('taskevent-','taskorphan-'):
                for name in self.vault.names(prefix+head['id']+'-'): self.vault.delete(name)
            self.vault.delete(self.key(head['id']))
