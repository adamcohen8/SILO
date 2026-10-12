"""Host-only fixed Git operations on an explicitly writable working copy.

No model schema exposes this service. Git metadata, identity and exact staged
tree are reviewed before commit; hooks, filters, signing and network are disabled.
"""
import hashlib
import json
import os
from pathlib import Path
from contextlib import contextmanager,ExitStack
from .asset_integrity import ordinary,digest_file
from .code_workspace import code_path
from .folders import AccessDenied
from .host_capabilities import require_capability
from .model import json_bytes


class GitWorkflow:
    def __init__(self,broker,folder_id,executable,*,security=None,development=False,state=None):
        self.broker,self.folder_id,self.executable=broker,folder_id,Path(executable).absolute()
        self.security,self.development=security,development;self.reviewed=None
        self.mirror=None;self.state=state
        self.revision=broker.revision
        self.executable_sha256=digest_file(self.executable)
        ordinary(self.executable)
        grants=broker.saved_grants()
        folder=next((f for f in broker.folders() if f.id==folder_id and f.access=='editable'),None)
        if folder is None: raise AccessDenied('Git needs an explicit writable working copy')
        # saved_grants preserves the order of folders; never select by user text.
        self.root=Path(grants[broker.folders().index(folder)]['path']).absolute()
        ordinary(self.root,directory=True); ordinary(self.root/'.git',directory=True)

    def _check(self):
        if self.broker.revision!=self.revision or digest_file(self.executable)!=self.executable_sha256:
            raise AccessDenied('Git grant or pinned executable changed')
        ordinary(self.root,directory=True); ordinary(self.root/'.git',directory=True)
        config=self.root/'.git/config'
        if config.exists():
            ordinary(config)
            text=config.read_text(encoding='utf-8')
            if len(text)>64*1024: raise AccessDenied('Git configuration is oversized')
            import re
            if re.search(r'^\s*\[\s*(include|includeif|filter|credential)\b',text,re.I|re.M):
                raise AccessDenied('Repository includes, filters and credential commands are unsupported')
            if re.search(r'^\s*(worktree|gitproxy|sshcommand|fsmonitor|alternaterefscommand)\s*=',text,re.I|re.M):
                raise AccessDenied('Repository command/worktree redirection is unsupported')
        for p in (self.root/'.git/commondir',self.root/'.git/objects/info/alternates'):
            if p.exists(): raise AccessDenied('Linked/shared Git storage is unsupported')
        count=0
        for directory,children,files in os.walk(self.root/'.git',followlinks=False):
            ordinary(directory,directory=True)
            for name in children: ordinary(Path(directory)/name,directory=True)
            for name in files:
                ordinary(Path(directory)/name); count+=1
                if count>10000: raise AccessDenied('Git metadata inventory exceeds this supported profile')
        if not(self.development is True and os.name=='posix'):
            require_capability(self.security,'git-host',{'git_sha256':self.executable_sha256,'boundary':'private-git-lpac-1'},
                {'root_identity','metadata_links','hooks_filters','config_includes','staged_drift','network',
                 'outside_filesystem','process_tree','job_memory','disk','metadata_races','commit_scope','cleanup'})

    def _run(self,args):
        with self._pin_config(): return self._run_pinned(args)

    @contextmanager
    def _pin_config(self):
        if os.name!='nt':
            yield;return  # Development only; cannot qualify Windows sharing.
        broker=self.broker;native=broker._native
        with broker._lock:
            grant=broker._get(self.folder_id,write=True)
            with broker._directory(grant,['.git']) as parent,ExitStack() as stack:
                names=set(native.names(parent))
                for name in ('config','HEAD','packed-refs'):
                    if name=='packed-refs' and name not in names:continue
                    metadata=native.open_child(parent,name,directory=False);stack.callback(native.close,metadata)
                    broker._check(metadata,volume=grant.info.volume,directory=False)
                    reader=native.open_read(metadata);stack.callback(native.close,reader)
                yield

    def _run_pinned(self,args):
        self._check()
        if self.security is not None:
            # Host Git must be part of the currently verified managed release,
            # rather than an executable selected from a user-writable path.
            try: relative='git/'+self.executable.relative_to(self.security.release/'payload/git').as_posix()
            except ValueError: raise AccessDenied('Git runtime is outside the managed release') from None
            if not any(p['path']==relative and p['sha256']==self.executable_sha256 for p in self.security.bundle['files']):
                raise AccessDenied('Git runtime is not pinned in the signed release inventory')
        env={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','PATH','TEMP','TMP'}}
        env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_TERMINAL_PROMPT='0',
                   GIT_ALLOW_PROTOCOL='',GIT_PAGER='',GIT_OPTIONAL_LOCKS='0',LC_ALL='C')
        command=[str(self.executable),'--no-pager','-C',str(self.root),'-c','core.hooksPath='+os.devnull,
            '-c','core.fsmonitor=false','-c','commit.gpgSign=false','-c','core.attributesFile='+os.devnull,
            '-c','core.autocrlf=false','-c','core.pager=','-c','protocol.allow=never',*args]
        # Timeout and streaming output cap apply to the trusted host process too.
        if os.name=='nt':
            if self.security is None or self.state is None:raise AccessDenied('Native Git requires managed security and bounded storage')
            if self.mirror is None:
                from .git_mirror import NativeGitMirror
                self.mirror=NativeGitMirror(self.security,self.broker,self.folder_id,self.state,self.executable)
            result=self.mirror.run(command,timeout=30,limit=256*1024)
        elif self.development is True and os.name=='posix':
            from .bounded_process import run_bounded
            result=run_bounded(command,cwd=self.executable.parent,env=env,timeout=30,limit=256*1024)
        else:raise AccessDenied('No portable production Git fallback')
        self._check()
        if result[0]!=0: raise AccessDenied('Git operation failed with exit '+str(result[0]))
        return result[1]

    def status(self):
        try:return self._run(['status','--porcelain=v1','--untracked-files=all']).decode('utf-8','replace')
        finally:
            if self.reviewed is None:self.close()
    def diff(self):
        try:return self._run(['diff','--no-ext-diff','--no-textconv','--']).decode('utf-8','replace')
        finally:
            if self.reviewed is None:self.close()

    def cancel(self):
        if self.mirror is not None:self.mirror.cancel()

    def close(self):
        self.reviewed=None
        if self.mirror is not None:
            mirror,self.mirror=self.mirror,None
            mirror.close()

    def prepare_commit(self,paths,message,author_name,author_email):
        self.close()
        try:return self._prepare_commit(paths,message,author_name,author_email)
        except BaseException:self.close();raise

    def _prepare_commit(self,paths,message,author_name,author_email):
        if (not isinstance(paths,list) or not paths or len(paths)>4096 or
                not all(isinstance(s,str) and 0<len(s)<=1024 and not any(ord(c)<32 for c in s) for s in (message,author_name,author_email))):
            raise AccessDenied('Commit needs exact paths, message and explicit author identity')
        for p in paths: code_path(p)
        # Refuse preexisting staged changes so approval covers only selected paths.
        if self._run(['diff','--cached','--name-only','--']): raise AccessDenied('Review or clear existing staged changes first')
        self._run(['--literal-pathspecs','add','--',*paths])
        selected=set(self._run(['diff','--cached','--name-only','-z','--']).decode().rstrip('\0').split('\0'))
        if selected-set(paths):raise AccessDenied('Concurrent staging added unselected paths; inspect the index before retrying')
        tree=self._run(['write-tree']).decode().strip();head=self._run(['rev-parse','--verify','HEAD']).decode().strip()
        branch=self._run(['symbolic-ref','HEAD']).decode().strip()
        patch=self._run(['diff','--cached','--no-ext-diff','--no-textconv','--']).decode('utf-8','replace')
        if not patch: raise AccessDenied('No selected changes to commit')
        v={'tree':tree,'head':head,'branch':branch,'message':message,'author_name':author_name,'author_email':author_email,
           'paths':paths,'patch':patch,'permission_revision':self.revision}
        v['review_sha256']=hashlib.sha256(json_bytes(v)).hexdigest()
        self.reviewed=json.loads(json_bytes(v))
        return v

    def commit(self,review_sha256):
        try:return self._commit(review_sha256)
        finally:self.close()

    def _commit(self,review_sha256):
        v=self.reviewed;self.reviewed=None
        if (v is None or v['review_sha256']!=review_sha256 or
                hashlib.sha256(json_bytes({k:x for k,x in v.items() if k!='review_sha256'})).hexdigest()!=review_sha256):
            raise AccessDenied('Review the exact commit digest first')
        if (self._run(['write-tree']).decode().strip()!=v['tree'] or
                self._run(['rev-parse','--verify','HEAD']).decode().strip()!=v['head'] or
                self._run(['symbolic-ref','HEAD']).decode().strip()!=v['branch']):
            raise AccessDenied('Staged tree or HEAD changed after review')
        # Identity comes from the trusted review, never repository configuration.
        # Commit precisely the reviewed immutable tree. Never let a concurrent
        # staging operation enlarge the commit; atomically compare the old ref.
        commit=self._run(['-c','user.name='+v['author_name'],'-c','user.email='+v['author_email'],
                   'commit-tree',v['tree'],'-p',v['head'],'-m',v['message']]).decode().strip()
        if self.mirror is not None:
            with self._pin_config():
                self._check();self.mirror.publish(commit,v['tree'],v['head'],v['branch'])
        else:self._run(['update-ref',v['branch'],commit,v['head']])
        return {'commit':commit,'tree':v['tree'],'pushed':False}
