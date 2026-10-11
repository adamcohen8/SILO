"""Windows terminal controller using the shared contained host backend.

Presentation can be tested with a fake backend. Production main never selects a
portable broker/server/runner when Windows containment is unavailable.
"""
import argparse
import os
from pathlib import Path
import sys
import threading

from .backend import WindowsSessionAdapter
from .code_artifacts import png_preview
from .contracts import Project,WorkspaceKind
from .execution_policy import ExecutionPolicy
from .folders import AccessDenied
from .terminal_ui import TerminalView


class TerminalClient:
    def __init__(self,backend,*,view=None,read=input,acceptance=None,acceptance_sha256=None,update_manager=None):
        self.backend=backend; self.view=view or TerminalView(); self.read=read
        self.acceptance,self.acceptance_sha256=acceptance,acceptance_sha256
        self.sources={}
        self.update_manager, self.update_request = update_manager, None
        from .model_menu import ModelMenu
        self.model_menu = ModelMenu(self)

    def request_update(self):
        manager = self.update_manager
        if manager is None: raise AccessDenied('Updates require the standalone installation')
        if self.model_menu.pending is not None: raise AccessDenied('Close the model menu before updating')
        if self.code is not None: raise AccessDenied('Review code artifacts and use /code-close before updating')
        if self.backend.workspace.pending_proposals():
            raise AccessDenied('Approve or discard pending drafts before updating')
        conversation = getattr(self.backend, 'conversation', None)
        if conversation and getattr(conversation, 'turns', ()) and getattr(self.backend, 'record', None) is None:
            raise AccessDenied('This chat is not retained. Use /clear before updating; saved projects resume after restart')
        if hasattr(self.backend, 'persist'): self.backend.persist()
        self.view.notice('Downloading and verifying the update. Ctrl+C cancels before installation.')
        self.update_request = manager.stage()
        self.view.notice('Update verified. Closing owned processes and restarting SILO.')
        return False

    def start_update_checks(self, *, notify=True):
        if self.update_manager is None: return
        from .terminal_updates import CHECK_INTERVAL
        def poll():
            while not self.update_manager.stop.is_set():
                status = self.update_manager.check()
                if notify and not self.update_manager.stop.is_set(): self.view.notice(status)
                if self.update_manager.stop.wait(CHECK_INTERVAL): return
        threading.Thread(target=poll, daemon=True, name='SILO-release-check').start()

    @property
    def code(self): return getattr(getattr(self.backend,'service',None),'code',None)

    def managed(self):
        from .project_store import ProjectSession
        if not isinstance(self.backend,ProjectSession):
            raise AccessDenied('Saved projects require the standalone installation and private host storage')
        return self.backend

    def host_command(self,command,arg):
        from dataclasses import asdict
        from .model import json_bytes
        if command=='/hardware':
            from .model_management import scan_hardware
            hardware=scan_hardware()
            self.view.table(['Hardware', 'Value'], [
                ['CPU threads', hardware.cpu_count or 'Unknown'],
                ['RAM', f'{hardware.ram_mib / 1024:.1f} GiB' if hardware.ram_mib is not None else 'Unknown'],
                *[[f'GPU {i}', f'{gpu["name"]} — {gpu["vram_mib"] / 1024:.1f} GiB']
                  for i, gpu in enumerate(hardware.gpus)]])
            manager=getattr(getattr(self.backend,'service',None),'model_manager',None)
            if manager:
                self.view.table(['Model', 'Capacity', 'RAM / CUDA0 VRAM'],
                    [[r['name'], 'Fits declared floors' if r['fits'] else 'Insufficient or unknown',
                      f'{r["minimum_ram_mib"] / 1024:.0f} / {r["minimum_vram_mib"] / 1024:.0f} GiB']
                     for r in manager.recommendations(hardware)])
                self.view.notice('Capacity estimates only; model quality and native acceptance require testing.')
            return
        session=self.managed(); action,_,rest=arg.partition(' '); rest=rest.strip()
        if command=='/project':
            if action=='new':
                project=session.create_project(rest); self.view.notice('Saved project created: '+project.id)
            elif action=='open': self.view.notice(str(session.open_project(rest)))
            elif action=='close': session.close_project(); self.view.notice('Project closed. Grants removed.')
            elif action=='list': self.view.table(['Project', 'ID', 'Status', 'Turns'],
                [[p['name'], p['id'], 'Expired' if p['expired'] else 'Available', p['turns']]
                 for p in session.store.listing()])
            elif action=='delete': session.delete_project(rest); self.view.notice('Project records deleted. User files preserved.')
            elif action=='retention': session.set_retention(int(rest)); self.view.notice('Retention updated.')
            elif action=='renew':
                identifier,_,days=rest.partition(' '); session.store.renew(identifier,int(days))
                self.view.notice('Project retention renewed; open it to revalidate grants and sources.')
            elif action=='prune':
                # Do not silently retire the active project without closing its context.
                if session.record and session.store.expired(session.record): session.close_project()
                self.view.notice('Expired projects deleted: '+str(session.store.prune()))
            elif action=='context':
                session.persist()
                for t in session.conversation.turns:
                    self.view.user(t.prompt); self.view.answer(t.answer)
                    for source in t.sources: self.view.body(f'{source.citation} {source.path} SHA-256 {source.sha256}', tone='muted')
            else: raise AccessDenied('/project new NAME | open ID | list | context | retention DAYS | renew ID DAYS | close | delete ID | prune')
        elif command=='/instructions':
            if action=='set': session.set_instructions(rest); self.view.notice('Task instructions saved; chat cleared.')
            elif action=='clear': session.set_instructions(''); self.view.notice('Task instructions cleared.')
            elif action=='show': self.view.body(session.record['instructions'] if session.record else '')
            else: raise AccessDenied('/instructions set TEXT | show | clear')
        elif command=='/workflow':
            from .workflows import Workflows
            workflows=Workflows(session)
            if action=='save':
                name,_,prompt=rest.partition(' '); workflows.save(name,prompt); self.view.notice('Workflow saved with current project scope.')
            elif action=='list': self.view.table(['Workflow', 'Prompt'],
                [[name, row['prompt']] for name, row in workflows.listing().items()])
            elif action=='delete': workflows.delete(rest); self.view.notice('Workflow deleted.')
            elif action=='run': self.ask(workflows.prompt(rest))
            else: raise AccessDenied('/workflow save ID PROMPT | list | run ID | delete ID')
        elif command=='/schedule':
            from .workflows import ScheduleEngine
            if not hasattr(self,'scheduler'): self.scheduler=ScheduleEngine(session)
            if action=='create':
                name,_,seconds=rest.partition(' ')
                identifier=self.scheduler.create(name,interval_seconds=int(seconds))
                self.view.notice('Schedule created: '+identifier+'. Runs while this project is open in the full-screen terminal; /schedule tick checks due tasks in scrollback mode.')
            elif action=='list': self.view.table(['Schedule', 'Workflow', 'State', 'Interval (s)'],
                [[name, row['workflow'], row['state'], row['interval_seconds']]
                 for name, row in self.scheduler.listing().items() if row['project_id'] == session.project.id])
            elif action=='tick': self.view.table(['Schedule', 'State'],
                [[row['id'], row['state']] for row in self.scheduler.tick()])
            elif action=='cancel': self.scheduler.cancel(rest); self.view.notice('Schedule cancelled.')
            elif action=='reconcile': self.scheduler.reconcile(rest); self.view.notice('Interrupted slot skipped; future runs reenabled.')
            else: raise AccessDenied('/schedule create WORKFLOW SECONDS | list | tick | cancel ID | reconcile ID')
        elif command in {'/models','/model'}:
            manager=getattr(session.service,'model_manager',None)
            if manager is None: raise AccessDenied('Managed models require the standalone CPython 3.14 installation')
            if command=='/models': self.view.table(['Model', 'Profile ID', 'State'],
                [[p.get('display_name', p['id']), p['id'],
                  'Active' if p['id'] == manager.selected() else 'Installed' if manager.installed(p) else 'Not installed']
                 for p in manager.profiles()])
            elif action in {'select','switch'} and rest:
                self.model_menu.execute('switch',rest)
            elif action=='install' and rest: self.model_menu.execute('install',rest)
            elif action=='remove' and rest: self.model_menu.confirm(rest)
            elif action=='import':
                identifier,_,path=rest.partition(' '); manager.import_model(identifier,path)
                self.view.notice('Offline model imported and hash verified.')
            else: self.model_menu.show(action)
        elif command in {'/backup','/restore'}:
            from .asset_integrity import ordinary
            path=Path(arg)
            if not path.is_absolute(): raise AccessDenied('Choose an absolute local backup path')
            security=getattr(session.service,'security',None)
            if security is not None:
                security.check()
                security.storage.backup(path)
                from .security_events import identifier
                security.audit.emit('backup' if command=='/backup' else 'restore','attempt',object_sha256=identifier(path))
            if command=='/backup':
                ordinary(path.parent,directory=True)
                data=session.store.vault.backup()
                if security:
                    from .data_security import encrypted_archive
                    encrypted_archive(path,security,data=data)
                else:
                    with path.open('xb') as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
                self.view.notice('Encrypted backup saved. Restore requires this account key; vault.key is excluded.')
            else:
                if ordinary(path).st_size>64*1024*1024: raise AccessDenied('Backup exceeds limit')
                if security:
                    from .data_security import encrypted_archive
                    data=encrypted_archive(path,security)
                else:data=path.read_bytes()
                session.store.vault.restore(data); self.view.notice('Backup records restored. Open a project to revalidate grants and sources.')
            if security is not None:
                security.audit.emit('backup' if command=='/backup' else 'restore','success',object_sha256=identifier(path))

    def ask(self,prompt):
        self.view.user(prompt); results=[]; errors=[]
        def request():
            try: results.append(self.backend.ask(prompt))
            except BaseException as error: errors.append(error)
        thread=threading.Thread(target=request); thread.start()
        try:
            while thread.is_alive(): thread.join(.1)
        except KeyboardInterrupt:
            self.backend.cancel()
            self.view.notice('Cancelled. Waiting for owned processes and cleanup.',warning=True)
            while thread.is_alive():
                try: thread.join(.1)
                except KeyboardInterrupt: self.backend.cancel()
            self.sources.clear()
            recover = getattr(self.backend, 'recover', None)
            if callable(recover):
                try:
                    self.view.notice('Reloading the verified model. Old chat, reviews and code authority are cleared.')
                    recover()
                    self.view.notice('Ready again.')
                except Exception:
                    self.view.notice('Verified restart failed. Close SILO and inspect the installation before continuing.', warning=True)
            return
        if errors: raise errors[0]
        result=results[0]; self.view.answer(result.answer)
        self.sources={s.id:s for s in result.citations}
        for source in result.citations:
            self.view.body(f'{source.reference} {source.path} {source.locator} SHA-256 {source.sha256}',tone='muted')
        for proposal in result.proposals:
            self.view.notice(f'Unsaved draft {proposal.id}; /review {proposal.id}')
        if self.code is not None:
            for export in self.code.exports.values():
                self.view.notice(f'Unpublished artifact set {export.id}; /review {export.id}')

    def review(self,identifier):
        item=self.backend.review(identifier)
        if hasattr(item,'files'):
            self.view.notice(f'UNPUBLISHED ZIP {item.destination_path}; SHA-256 {item.sha256}')
            for path,sha,size in item.files:
                self.view.body(f'{path}: {size} bytes; SHA-256 {sha}')
                data=self.code.files[path]
                self.view.body(png_preview(data) if path.endswith('.png') else data.decode('utf-8'))
        else:
            self.view.notice(f'UNSAVED {item.destination_path}'); self.view.body(item.diff)
        self.view.notice(f'/approve {identifier} saves the exact reviewed new copy; /discard {identifier} discards it.')

    def completion_snapshot(self):
        """Bounded name-only inventory from granted folders while the host is idle."""
        from .mentions import MentionCatalog
        catalog = MentionCatalog(self.backend.workspace.broker)
        ids = {}
        for command in ('/revoke ',):
            ids[command] = [(f.id, f.name) for f in self.backend.workspace.broker.folders()]
        pending = [(p.id, p.destination_path) for p in self.backend.workspace.pending_proposals()]
        for command in ('/review ', '/approve ', '/discard '): ids[command] = pending
        service = getattr(self.backend, 'service', None)
        manager = getattr(service, 'model_manager', None)
        if manager:
            profiles = manager.profiles()
            for action in ('switch', 'install', 'remove', 'import'):
                ids['/model ' + action + ' '] = [(p['id'], p.get('display_name', p['id'])) for p in profiles]
        store = getattr(self.backend, 'store', None)
        if store:
            projects = [(p['id'], p['name']) for p in store.listing()]
            for action in ('open', 'delete', 'renew'): ids['/project ' + action + ' '] = projects
        record = getattr(self.backend, 'record', None)
        if record:
            for action in ('run', 'delete'): ids['/workflow ' + action + ' '] = [(key, key) for key in record['workflows']]
        return catalog, ids

    def grant_folder(self, path, kind):
        """Trusted UI selection; keep paths as data without command parsing."""
        folder = self.backend.grant(path, kind)
        self.sources.clear()
        self.view.notice(f'Granted {folder.name}: {folder.access}, ID {folder.id}')
        return folder

    def handle(self,line):
        if self.model_menu.pending is not None and line not in {'/quit','/model','/models'}:
            self.model_menu.choose(line.strip()); return True
        command,_,arg=line.partition(' '); arg=arg.strip()
        if not line.startswith('/'): self.ask(line); return True
        if command=='/quit': return False
        if command=='/update':
            if self.update_manager is None:
                raise AccessDenied('Managed updates require administrator-signed release enrollment; preview updates require the standalone installation')
            if arg=='check': self.view.notice(self.update_manager.check())
            elif not arg: return self.request_update()
            else: raise AccessDenied('/update check | /update installs the available update')
        elif command in {'/project','/instructions','/workflow','/schedule','/models','/model','/hardware','/backup','/restore'}:
            self.host_command(command,arg)
        elif command in {'/reference','/ro','/draft','/editable'}:
            kind=WorkspaceKind.REFERENCE if command in {'/reference','/ro'} else WorkspaceKind.DRAFT
            self.grant_folder(arg, kind)
        elif command=='/folders':
            self.view.table(['Folder', 'Access', 'ID'],
                [[folder.name, folder.access, folder.id] for folder in self.backend.workspace.broker.folders()])
        elif command=='/revoke': self.backend.revoke(arg); self.sources.clear(); self.view.notice('Grant revoked; context invalidated.')
        elif command=='/clear': self.backend.clear_chat(); self.sources.clear(); self.view.notice('Chat and pending reviews cleared.')
        elif command=='/review': self.review(arg)
        elif command=='/approve': self.backend.approve(arg); self.view.notice('Saved the exact reviewed new copy.')
        elif command=='/discard': self.backend.discard(arg); self.view.notice('Discarded.')
        elif command=='/code':
            if arg: raise AccessDenied('Code workspace is disposable and host-created; /code accepts no user path')
            policy=ExecutionPolicy()
            self.view.notice('Requested Code policy: Python only; no network or children; 60 s/run, 512 MiB RAM, 16 MiB fixed disk, 64 KiB output, eight runs.')
            self.backend.create_code(policy,acceptance=self.acceptance,acceptance_sha256=self.acceptance_sha256)
            self.view.notice('Code policy granted. Outputs remain unpublished until reviewed approval.')
        elif command=='/code-close': self.backend.close_code(); self.view.notice('Code workspace and unpublished artifacts removed.')
        elif command in {'/files','/artifact'}:
            if self.code is None: raise AccessDenied('Create an accepted Code workspace first')
            if command=='/files':
                self.view.table(['File', 'Bytes', 'SHA-256'],
                    [[file['path'], file['size'], file['sha256']] for file in self.code.listing()])
            else:
                self.code.check()
                if arg not in self.code.files: raise AccessDenied('Artifact unavailable')
                data=self.code.files[arg]
                self.view.body(png_preview(data) if arg.endswith('.png') else self.code.read(arg)['text'])
        elif command=='/sources':
            for source in self.sources.values(): self.view.body(f'{source.reference} {source.path} {source.locator}\n{source.text}')
        elif command=='/help':
            self.view.notice('Start with /reference PATH, then ask about a file. /draft PATH enables reviewed exports.\n'
                             'Full-screen: Tab completes commands and granted names; F2 opens commands, F3 opens file mentions.\n'
                             'Live text is provisional until the host accepts the completed response.')
            self.view.body('/reference PATH | /draft PATH | /folders | /revoke ID | /clear\n'
                           '/code | /code-close | /files | /artifact PATH | /sources\n'
                           '/review ID | /approve ID | /discard ID | /quit\n'
                           '/project | /instructions | /workflow | /schedule\n'
                           '/models | /model | /hardware | /backup PATH | /restore PATH\n'
                           '/model opens switch/install/remove; numbered choices, /back and /cancel\n'
                           '/update check | /update | Ctrl+U installs an available update\n'
                           'Paths are literal text after the first space; no shell expansion or quoting needed.')
        else: raise AccessDenied('Unknown host command; no model call made')
        return True

    def interact(self):
        self.view.line('SILO',tone='accent')
        self.view.notice('Windows contained evaluation / synthetic data only. Code requires independently reviewed native boundary evidence.')
        self.view.notice('No folders granted. /help lists host commands. Ctrl+C stops active work; reload the model after inference cancellation.')
        interactive = (self.read is input and self.update_manager is not None
                       and sys.stdin.isatty() and sys.stdout.isatty())
        self.start_update_checks(notify=not interactive)
        read = self.read
        if interactive:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.formatted_text import ANSI
            from prompt_toolkit.key_binding import KeyBindings
            bindings = KeyBindings()
            @bindings.add('c-u', eager=True)
            def install(event):
                if event.current_buffer.text:
                    self.view.notice('Send or clear your input before updating', warning=True)
                else: event.app.exit(result='/update')
            prompt = PromptSession(key_bindings=bindings,
                bottom_toolbar=lambda: self.update_manager.status, refresh_interval=1)
            read = lambda value: prompt.prompt(ANSI(value))
        while True:
            try: line=read(self.view.prompt())
            except EOFError: return
            except KeyboardInterrupt:
                if self.model_menu.pending is None: return
                self.model_menu.cancel(); self.view.notice('Model menu closed.'); continue
            if not line.strip(): continue
            try:
                if not self.handle(line): return
            except KeyboardInterrupt:
                self.model_menu.cancel()
                self.view.notice('Model operation cancelled.',warning=True)
            except Exception as error: self.view.notice(str(error),warning=True)


def main(root=None):
    parser=argparse.ArgumentParser(description='Contained SILO Windows terminal, synthetic evaluation only')
    parser.add_argument('--evaluation',action='store_true',help='Explicit synthetic source evaluation on an unprovisioned machine; never overrides managed policy')
    parser.add_argument('--plain',action='store_true')
    parser.add_argument('--required-policy-key-sha256',help='Independent organization launcher trust anchor; denies missing or substituted policy')
    parser.add_argument('--scrollback',action='store_true',help='Use the scrolling interface instead of the full terminal window')
    args=parser.parse_args()
    if os.name!='nt':
        print('Native Windows is required. Use preview_terminal.py for the portable interface preview.',file=sys.stderr)
        return 2
    from .windows_session import WindowsSession
    root=Path(root or Path(__file__).resolve().parents[2])
    view=TerminalView(plain=args.plain)
    def progress(event): view.activity(f'{event.stage}: {event.model_calls} model calls, {event.tool_calls} tool calls')
    service=session=vault=updater=None
    ticket=None
    result=0
    try:
        service=WindowsSession(root,evaluation=args.evaluation)
        session=WindowsSessionAdapter(Project('windows-evaluation','SILO Windows evaluation'),service,progress=progress)
        if args.required_policy_key_sha256 and not service.installation:
            raise AccessDenied('Organization policy requires the standalone CPython 3.14 installation')
        if service.installation:
            from .project_store import LocalVault, project_data_directory
            from .model_management import ModelManager
            vault=LocalVault(project_data_directory(service.state),windows_validation=True)
            service.model_manager=ModelManager(root,vault,required_key_sha256=args.required_policy_key_sha256,
                model_cache=project_data_directory(service.state,name='models'),policy_store=service.security.store)
            view.notice('Managed updates require administrator-signed release enrollment.')
        session.start()
        if vault:
            from .project_store import ProjectSession,ProjectStore
            session=ProjectSession(session,ProjectStore(vault,
                maximum_retention_days=service.security.settings['maximum_retention_days'],audit=service.security.audit))
            active=vault.get('active-project')
            if active:
                try: session.open_project(active['id'])
                except (AccessDenied,OSError): view.notice('Saved project could not resume. Open or delete it explicitly.',warning=True)
        options={'update_manager':updater}
        if args.scrollback:
            client=TerminalClient(session,view=view,**options)
            client.interact()
        else:
            from .terminal_fullscreen import FullScreenPreview
            screen=FullScreenPreview(backend=session,plain=args.plain,client_options=options)
            screen.run()
            client=screen.controller
        ticket=client.update_request
    except KeyboardInterrupt: result=130
    except Exception as error:
        view.notice(str(error),warning=True); result=1
    finally:
        if updater: updater.stop.set()
        try:
            if session: session.close()
            elif service: service.close()
        except Exception as error:
            view.notice('Session cleanup failed; update will not start: '+str(error),warning=True)
            result=1
        finally:
            if vault:
                try: vault.close()
                except Exception as error:
                    view.notice('Private storage cleanup failed; update will not start: '+str(error),warning=True)
                    result=1
    if ticket is not None and result==0:
        try: updater.launch(ticket)
        except Exception as error: view.notice('Update could not start: '+str(error),warning=True); return 1
    return result
