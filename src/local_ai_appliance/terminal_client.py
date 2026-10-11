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
    def __init__(self,backend,*,view=None,read=input,acceptance=None,acceptance_sha256=None):
        self.backend=backend; self.view=view or TerminalView(); self.read=read
        self.acceptance,self.acceptance_sha256=acceptance,acceptance_sha256
        self.sources={}

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
            hardware=scan_hardware(); self.view.body(json_bytes(asdict(hardware)).decode())
            manager=getattr(getattr(self.backend,'service',None),'model_manager',None)
            if manager: self.view.body(json_bytes(manager.recommendations(hardware)).decode())
            return
        session=self.managed(); action,_,rest=arg.partition(' '); rest=rest.strip()
        if command=='/project':
            if action=='new':
                project=session.create_project(rest); self.view.notice('Saved project created: '+project.id)
            elif action=='open': self.view.notice(str(session.open_project(rest)))
            elif action=='close': session.close_project(); self.view.notice('Project closed. Grants removed.')
            elif action=='list': self.view.body(json_bytes(session.store.listing()).decode())
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
                session.persist(); self.view.body(json_bytes([{'prompt':t.prompt,'answer':t.answer,
                    'sources':[{'path':s.path,'sha256':s.sha256,'citation':s.citation} for s in t.sources]}
                    for t in session.conversation.turns]).decode())
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
            elif action=='list': self.view.body(json_bytes(workflows.listing()).decode())
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
            elif action=='list': self.view.body(json_bytes(self.scheduler.listing()).decode())
            elif action=='tick': self.view.body(json_bytes(self.scheduler.tick()).decode())
            elif action=='cancel': self.scheduler.cancel(rest); self.view.notice('Schedule cancelled.')
            elif action=='reconcile': self.scheduler.reconcile(rest); self.view.notice('Interrupted slot skipped; future runs reenabled.')
            else: raise AccessDenied('/schedule create WORKFLOW SECONDS | list | tick | cancel ID | reconcile ID')
        elif command in {'/models','/model'}:
            manager=getattr(session.service,'model_manager',None)
            if manager is None: raise AccessDenied('Managed models require the standalone CPython 3.14 installation')
            if command=='/models': self.view.body(json_bytes(manager.profiles()).decode())
            elif action=='select':
                manager.select(rest,data_scope=session.project.data_scope)
                if session.record:
                    session.record['configuration_id']=rest; session.persist()
                self.view.notice('Model selected. Restart SILO; the saved project retains its verified grants.')
            elif action=='import':
                identifier,_,path=rest.partition(' '); manager.import_model(identifier,path)
                self.view.notice('Offline model imported and hash verified.')
            else: raise AccessDenied('/models | /model select ID | /model import ID PATH')
        elif command in {'/backup','/restore'}:
            from .asset_integrity import ordinary
            path=Path(arg)
            if not path.is_absolute(): raise AccessDenied('Choose an absolute local backup path')
            if command=='/backup':
                ordinary(path.parent,directory=True)
                data=session.store.vault.backup()
                with path.open('xb') as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
                self.view.notice('Encrypted backup saved. Restore requires this account key; vault.key is excluded.')
            else:
                if ordinary(path).st_size>64*1024*1024: raise AccessDenied('Backup exceeds limit')
                session.store.vault.restore(path.read_bytes()); self.view.notice('Backup records restored. Open a project to revalidate grants and sources.')

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
            self.view.notice('Cancelled. Waiting for owned processes and cleanup. Restart the session before continuing.',warning=True)
            while thread.is_alive():
                try: thread.join(.1)
                except KeyboardInterrupt: self.backend.cancel()
            self.sources.clear(); return
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

    def handle(self,line):
        command,_,arg=line.partition(' '); arg=arg.strip()
        if not line.startswith('/'): self.ask(line); return True
        if command=='/quit': return False
        if command in {'/project','/instructions','/workflow','/schedule','/models','/model','/hardware','/backup','/restore'}:
            self.host_command(command,arg)
        elif command in {'/reference','/ro','/draft','/editable'}:
            kind=WorkspaceKind.REFERENCE if command in {'/reference','/ro'} else WorkspaceKind.DRAFT
            folder=self.backend.grant(arg,kind); self.sources.clear()
            self.view.notice(f'Granted {folder.name}: {folder.access}, ID {folder.id}')
        elif command=='/folders':
            for folder in self.backend.workspace.broker.folders(): self.view.body(f'{folder.id} {folder.access} {folder.name}')
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
                for file in self.code.listing(): self.view.body(str(file))
            else:
                self.code.check()
                if arg not in self.code.files: raise AccessDenied('Artifact unavailable')
                data=self.code.files[arg]
                self.view.body(png_preview(data) if arg.endswith('.png') else self.code.read(arg)['text'])
        elif command=='/sources':
            for source in self.sources.values(): self.view.body(f'{source.reference} {source.path} {source.locator}\n{source.text}')
        elif command=='/help':
            self.view.body('/reference PATH | /draft PATH | /folders | /revoke ID | /clear\n'
                           '/code | /code-close | /files | /artifact PATH | /sources\n'
                           '/review ID | /approve ID | /discard ID | /quit\n'
                           '/project | /instructions | /workflow | /schedule\n'
                           '/models | /model | /hardware | /backup PATH | /restore PATH\n'
                           'Paths are literal text after the first space; no shell expansion or quoting needed.')
        else: raise AccessDenied('Unknown host command; no model call made')
        return True

    def interact(self):
        self.view.line('SILO',tone='accent')
        self.view.notice('Windows contained evaluation / synthetic data only. Code requires independently reviewed native boundary evidence.')
        self.view.notice('No folders granted. /help lists host commands. Ctrl+C stops active work; restart after cancellation.')
        while True:
            try: line=self.read(self.view.prompt())
            except (EOFError,KeyboardInterrupt): return
            if not line.strip(): continue
            try:
                if not self.handle(line): return
            except Exception as error: self.view.notice(str(error),warning=True)


def main(root=None):
    parser=argparse.ArgumentParser(description='Contained SILO Windows terminal, synthetic evaluation only')
    parser.add_argument('--acceptance',type=Path)
    parser.add_argument('--acceptance-sha256')
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
    service=session=vault=None
    try:
        service=WindowsSession(root)
        session=WindowsSessionAdapter(Project('windows-evaluation','SILO Windows evaluation'),service,progress=progress)
        if args.required_policy_key_sha256 and not service.installation:
            raise AccessDenied('Organization policy requires the standalone CPython 3.14 installation')
        if service.installation:
            from .project_store import LocalVault, project_data_directory
            from .model_management import ModelManager
            vault=LocalVault(project_data_directory(service.state),windows_validation=True)
            service.model_manager=ModelManager(root,vault,required_key_sha256=args.required_policy_key_sha256,
                model_cache=project_data_directory(service.state,name='models'))
        session.start()
        if vault:
            from .project_store import ProjectSession,ProjectStore
            session=ProjectSession(session,ProjectStore(vault))
            active=vault.get('active-project')
            if active:
                try: session.open_project(active['id'])
                except (AccessDenied,OSError): view.notice('Saved project could not resume. Open or delete it explicitly.',warning=True)
        options={'acceptance':args.acceptance,'acceptance_sha256':args.acceptance_sha256}
        if args.scrollback:
            TerminalClient(session,view=view,**options).interact()
        else:
            from .terminal_fullscreen import FullScreenPreview
            FullScreenPreview(backend=session,plain=args.plain,client_options=options).run()
        return 0
    except KeyboardInterrupt: return 130
    except Exception as error:
        view.notice(str(error),warning=True); return 1
    finally:
        try:
            if session: session.close()
            elif service: service.close()
        finally:
            if vault: vault.close()
