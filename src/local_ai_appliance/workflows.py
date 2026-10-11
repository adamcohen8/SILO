"""Project-scoped reusable tasks and host-owned, opt-in schedules.

No scheduler grants folders, approves drafts, executes shell commands or restarts
models. A due task runs only in its already-open project with the same scope.
Crash-interrupted attempts become unknown and require explicit reconciliation.
"""
import hashlib
import re
import secrets
import threading
import time

from .folders import AccessDenied
from .model import json_bytes


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-z0-9_-]{1,64}',value):
        raise AccessDenied('Use an ID with lowercase letters, numbers, underscores or hyphens')
    return value


def scope(record,model_id=None):
    grants = [{key:grant[key] for key in ('path','access','volume','index')} for grant in record['grants']]
    return hashlib.sha256(json_bytes({'project':record['project'],'grants':grants,
        'instructions':record['instructions'],'configuration_id':model_id or record['configuration_id']})).hexdigest()


class Workflows:
    def __init__(self,session): self.session = session

    def _record(self):
        self.session._idle()
        if self.session.record is None:
            raise AccessDenied('Open a saved project first')
        self.session.persist()
        return self.session.record

    def save(self,name,prompt):
        identifier(name)
        if not isinstance(prompt,str) or not prompt.strip() or len(prompt.encode('utf-8')) > 16*1024:
            raise AccessDenied('Workflow prompt must be nonempty and at most 16 KiB')
        record = self._record()
        if name not in record['workflows'] and len(record['workflows']) >= 32:
            raise AccessDenied('Project workflow limit reached')
        record['workflows'][name] = {'prompt':prompt,'scope':scope(record)}
        self.session.persist()

    def listing(self): return self._record()['workflows'].copy()

    def delete(self,name):
        record = self._record()
        if name not in record['workflows']: raise AccessDenied('Unknown workflow')
        del record['workflows'][name]; self.session.persist()

    def prompt(self,name):
        record = self._record(); workflow = record['workflows'].get(name)
        if workflow is None or workflow['scope'] != scope(record):
            raise AccessDenied('Workflow scope changed; review and save the workflow again')
        return workflow['prompt']


class ScheduleEngine:
    def __init__(self,session,*,clock=time.time):
        self.session,self.vault,self.clock = session,session.store.vault,clock
        self.security=getattr(getattr(session,'service',None),'security',None)
        self.workflows = Workflows(session)
        self._guard = threading.Lock()
        self.active = None

    def listing(self): return self.vault.get('schedules',{'format':1,'items':{}})['items']

    def _save(self,items): self.vault.put('schedules',{'format':1,'items':items})

    def create(self,workflow,*,interval_seconds,first_due=None):
        self._authorize()
        workflow_prompt=self.workflows.prompt(workflow)
        if type(interval_seconds) is not int or not 60 <= interval_seconds <= 365*86400:
            raise AccessDenied('Schedule interval must be 60 seconds to 365 days')
        due = int(self.clock())+interval_seconds if first_due is None else first_due
        if type(due) is not int or due < int(self.clock()):
            raise AccessDenied('First due time must be an integer UTC timestamp in the future')
        with self._guard, self.vault.transaction():
            items = self.listing()
            if len(items) >= 64: raise AccessDenied('Schedule limit reached')
            name = secrets.token_hex(16)
            items[name] = {'project_id':self.session.project.id,'workflow':workflow,
                'scope':scope(self.session.record),'workflow_sha256':hashlib.sha256(workflow_prompt.encode('utf-8')).hexdigest(),
                'interval_seconds':interval_seconds,
                'next_due':due,'enabled':True,'state':'ready','last':None,'attempts':0}
            self._save(items)
            return name

    def cancel(self,name):
        with self._guard, self.vault.transaction():
            items = self.listing()
            if name not in items: raise AccessDenied('Unknown schedule')
            items[name]['enabled'] = False
            items[name]['state'] = 'cancelled'
            self._save(items)
            if self.active == name: self.session.cancel()

    def reconcile(self,name):
        """Acknowledge unknown outcome; skip its slot rather than replaying it."""
        self._authorize()
        if '.schedule-runner-lock' in self.vault.store.names():
            raise AccessDenied('A schedule runner is active or requires crash recovery; reconciliation denied')
        with self.vault.store.lock('.schedule-runner-lock'), self._guard, self.vault.transaction():
            items = self.listing(); item = items.get(name)
            if item is None or item['state'] not in {'unknown','running'} or self.active == name:
                raise AccessDenied('Only an interrupted, inactive attempt can be reconciled')
            item['state']='ready'; item['enabled']=True
            item['next_due']=int(self.clock())+item['interval_seconds']
            self._save(items)

    def tick(self):
        self._authorize()
        if '.schedule-runner-lock' in self.vault.store.names(): return []
        try:
            with self.vault.store.lock('.schedule-runner-lock'):
                return self._tick()
        except FileExistsError:
            # Another portable client won the claim. Native lock failures also
            # prevent execution; they propagate for explicit host inspection.
            return []

    def _tick(self):
        if self.active is not None: return []
        events = []
        for name in list(self.listing()):
            with self._guard, self.vault.transaction():
                items = self.listing(); item = items.get(name)
                if item is None: continue
                if item['state'] == 'running':
                    item['state']='unknown'; item['enabled']=False; self._save(items)
                    events.append({'id':name,'state':'unknown'}); continue
                if (not item['enabled'] or item['next_due'] > self.clock() or self.session.record is None
                        or item['project_id'] != self.session.project.id): continue
                self.session._idle(); self.session.persist()
                if item['scope'] != scope(self.session.record):
                    item['enabled']=False; item['state']='scope_changed'; self._save(items)
                    events.append({'id':name,'state':'scope_changed'}); continue
                try:
                    prompt = self.workflows.prompt(item['workflow'])
                except AccessDenied:
                    item['enabled']=False; item['state']='workflow_changed'; self._save(items)
                    events.append({'id':name,'state':'workflow_changed'}); continue
                if hashlib.sha256(prompt.encode('utf-8')).hexdigest()!=item['workflow_sha256']:
                    item['enabled']=False; item['state']='workflow_changed'; self._save(items)
                    events.append({'id':name,'state':'workflow_changed'}); continue
                # Coalesce missed deadlines: one run, never a backlog of duplicate actions.
                skipped = max(0,(int(self.clock())-item['next_due'])//item['interval_seconds'])
                slot = item['next_due'] + skipped*item['interval_seconds']
                attempt = name+':'+str(slot)
                item.update(state='running',attempts=item['attempts']+1,
                    last={'idempotency_key':attempt,'due':slot,'skipped_slots':skipped,'state':'running'})
                self._save(items); self.active=name
            try:
                result = self.session.ask(prompt)
                outcome = {'state':'complete','answer_sha256':hashlib.sha256(result.answer.encode('utf-8')).hexdigest(),
                           'model_calls':result.model_calls,'tool_calls':result.tool_calls,
                           'pending_reviews':len(result.proposals)}
            except BaseException:
                outcome = {'state':'failed'}
            finally:
                with self._guard, self.vault.transaction():
                    items = self.listing(); current = items[name]
                    cancelled = not current['enabled']
                    current['last'].update(outcome)
                    current['state']='cancelled' if cancelled else outcome['state']
                    current['next_due']=slot+current['interval_seconds']
                    self._save(items); self.active=None
                    events.append({'id':name,**current['last']})
        return events

    def _authorize(self):
        if self.security:
            self.security.check()
            if not self.security.settings['allow_schedules']:
                raise AccessDenied('Administrator policy disables scheduled work')
            self.security.audit.emit('schedule','attempt')
