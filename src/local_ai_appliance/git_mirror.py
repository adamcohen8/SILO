"""Brokered Git snapshots: Git never receives the original Windows working path.

All CLI work happens on an owned bounded copy. Host publication copies verified
loose objects, compares original metadata, then publishes the branch last.
"""
import hashlib
from pathlib import Path
from contextlib import contextmanager
import re
import threading
import secrets
import zlib
from .folders import AccessDenied
from .repository_apply import observed


class GitMirror:
    def __init__(self,broker,folder_id,root,*,max_bytes=64*1024*1024):
        self.broker,self.folder_id,self.root=broker,folder_id,Path(root)
        self.revision=broker.revision;self.max_bytes=max_bytes
        self.baseline=self.snapshot()
        if '.git/config' not in self.baseline or '.git/HEAD' not in self.baseline:
            raise AccessDenied('A normal initialized Git working copy is required')
        for p,data in self.baseline.items():
            target=self.root/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        text=self.baseline['.git/config'].decode('utf-8')
        if re.search(r'^\s*\[\s*(include|includeif|filter|credential)\b',text,re.I|re.M):
            raise AccessDenied('Git includes, filters and credential commands are unsupported')
        sha256=bool(re.search(r'^\s*objectformat\s*=\s*sha256\s*$',text,re.I|re.M))
        self.algorithm='sha256' if sha256 else 'sha1'
        # Source config is data only. Never hand arbitrary configuration to Git.
        (self.root/'.git/config').write_text('[core]\nrepositoryFormatVersion = '+('1' if sha256 else '0')+'\nbare = false\n'+
            ('[extensions]\nobjectFormat = sha256\n' if sha256 else ''),encoding='utf-8')

    def snapshot(self):
        if self.broker.revision!=self.revision:raise AccessDenied('Git folder grant changed')
        result={};total=0; nodes=0
        def visit(prefix=''):
            nonlocal total,nodes
            listing=self.broker.list_directory(self.folder_id,prefix,limit=1000)
            if listing['truncated']:raise AccessDenied('Git snapshot is incomplete; select a smaller working copy')
            for e in listing['entries']:
                path='/'.join(filter(None,(prefix,e['name'])))
                if path=='.git/hooks' or path.startswith('.git/hooks/'):continue
                nodes+=1
                if nodes>768:raise AccessDenied('Git snapshot exceeds its cleanup-safe file/directory profile')
                if path in {'.git/commondir','.git/objects/info/alternates','.gitmodules'}:
                    raise AccessDenied('Shared Git storage, alternates and submodules are unsupported')
                if len(path.split('/'))>8:raise AccessDenied('Git snapshot depth exceeded')
                if e['kind']=='directory':visit(path)
                else:
                    data=self.broker.read_file(self.folder_id,path);total+=len(data)
                    if total>self.max_bytes or len(result)>=10000:raise AccessDenied('Git snapshot exceeds its bounded volume profile')
                    result[path]=data
        visit()
        if self.broker.revision!=self.revision:raise AccessDenied('Git folder grant changed during snapshot')
        return result

    def check_source(self):
        if self.snapshot()!=self.baseline:raise AccessDenied('Original Git metadata or working files changed; prepare again')

    def publish(self,commit,tree,parent,branch):
        self.check_source()
        if not re.fullmatch(r'refs/heads/[A-Za-z0-9_./-]+',branch) or '..' in branch or branch.endswith('/'):
            raise AccessDenied('Select an ordinary local branch')
        commit_path='.git/objects/'+commit[:2]+'/'+commit[2:]
        raw=self._object((self.root/commit_path).read_bytes(),commit)
        header=raw.split(b'\x00',1)[1].split(b'\n\n',1)[0].splitlines()
        if (not raw.startswith(b'commit ') or b'tree '+tree.encode() not in header or
                [h for h in header if h.startswith(b'parent ')]!=([b'parent '+parent.encode()] if parent else [])):
            raise AccessDenied('Git commit differs from the reviewed tree/parent')
        objects=[]
        for directory,_,files in __import__('os').walk(self.root/'.git/objects'):
            for name in files:
                path=Path(directory)/name;relative=path.relative_to(self.root).as_posix()
                if relative in self.baseline:continue
                if not re.fullmatch(r'\.git/objects/[a-f0-9]{2}/[a-f0-9]{38}(?:[a-f0-9]{24})?',relative):
                    raise AccessDenied('Unexpected new Git object storage')
                data=path.read_bytes();self._object(data,relative.removeprefix('.git/objects/').replace('/',''))
                objects.append((relative,data))
        # Immutable objects are harmless if interrupted; the branch remains old
        # until all of them have been published. No original hooks/config execute.
        for path,data in objects:
            current=observed(self.broker,self.folder_id,path)
            if current is None:self.broker.apply_reviewed_change(self.folder_id,path,None,data)
            elif current!=data:raise AccessDenied('Concurrent Git object differs; preserve it for inspection')
            self.baseline[path]=data
        self.check_source()
        # Publish the reviewed staging state too. If interrupted here, the
        # approved tree is staged and HEAD remains old; never replay the commit.
        index=(self.root/'.git/index').read_bytes()
        self.broker.apply_reviewed_change(self.folder_id,'.git/index',self.baseline.get('.git/index'),index)
        self.baseline['.git/index']=index
        self.check_source()
        path='.git/'+branch
        before=self.baseline.get(path)
        if before is not None and (parent is None or before.strip()!=parent.encode()):raise AccessDenied('Original branch differs from the reviewed parent')
        # Source HEAD/packed-ref leases are held by the native caller through
        # this final CAS, including a branch that previously existed only packed.
        self.broker.apply_reviewed_change(self.folder_id,path,before,(commit+'\n').encode())
        self.baseline[path]=(commit+'\n').encode()

    def _object(self,data,expected):
        decoder=zlib.decompressobj()
        try:raw=decoder.decompress(data,8*1024*1024+1024)
        except zlib.error:raise AccessDenied('Malformed compressed Git object') from None
        if not decoder.eof or decoder.unused_data or len(raw)>8*1024*1024:
            raise AccessDenied('Git object is oversized or incomplete')
        kind,sep,rest=raw.partition(b' ');size,zero,body=rest.partition(b'\x00')
        if kind not in {b'blob',b'tree',b'commit',b'tag'} or not sep or not zero or not size.isdigit() or int(size)!=len(body):
            raise AccessDenied('Malformed Git object')
        if hashlib.new(self.algorithm,raw).hexdigest()!=expected:raise AccessDenied('Git object hash changed')
        return raw


class NativeGitMirror(GitMirror):
    def __init__(self,security,broker,folder_id,state,executable):
        from .managed_code_storage import ManagedVolume
        from .windows_code_storage import require_clean_state
        self.security,self.state,self.executable=security,Path(state),Path(executable)
        self.active=None;self.cancelled=False;self.closed=False
        self.guard=threading.RLock();self.idle=threading.Event();self.idle.set()
        require_clean_state(self.state)
        self.volume=ManagedVolume(security,64*1024*1024)
        self.root=self.volume.root/'work'
        # Private DACL/low label belongs only to this newly created copy.
        from .windows_code_runner import RunnerContainer
        try:
            with self._container({key:str(self.root) for key in ('TEMP','TMP','LOCALAPPDATA','APPDATA','USERPROFILE')}) as container:
                container.create_private_ipc(self.root)
            super().__init__(broker,folder_id,self.root)
        except BaseException:
            try:self.volume.close()
            except BaseException:self._cleanup_unknown();raise
            raise

    def _cleanup_unknown(self):
        from .model import json_bytes
        (self.state/('cleanup-failed-'+secrets.token_hex(8)+'.json')).write_bytes(json_bytes(
            {'cleanup':'failed','role':'git','volume_lease':self.volume.id}))

    @contextmanager
    def _container(self,env):
        from .windows_code_runner import RunnerContainer
        try:container=RunnerContainer(env)
        except BaseException:self._cleanup_unknown();raise
        try:yield container
        finally:
            try:container.close()
            except BaseException:self._cleanup_unknown();raise

    def run(self,command,*,timeout=30,limit=256*1024):
        with self.guard:
            if self.cancelled or self.closed or not self.idle.is_set():raise AccessDenied('Git is cancelled, closed or busy')
            self.idle.clear()
        try:return self._run_owned(command,timeout=timeout,limit=limit)
        finally:self.idle.set()

    def _run_owned(self,command,*,timeout,limit):
        from .windows_code_runner import RunnerContainer
        from .asset_integrity import verify_tree
        if self.cancelled or self.closed:raise AccessDenied('Git operation cancelled')
        self.security.check();self.check_source()
        sdk=self.security.release/'payload/git'
        pins=[{**p,'path':p['path'].removeprefix('git/')} for p in self.security.bundle['files'] if p['path'].startswith('git/')]
        verify_tree(sdk,pins)
        env={key:str(self.root) for key in ('TEMP','TMP','LOCALAPPDATA','APPDATA','USERPROFILE')}
        env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='NUL',GIT_TERMINAL_PROMPT='0',GIT_ALLOW_PROTOCOL='',
                   GIT_OPTIONAL_LOCKS='0',LC_ALL='C',PATH=str(sdk/'cmd'))
        with self._container(env) as container:
            container.allow_managed_read(sdk,directory=True)
            for p in pins:container.allow_managed_read(sdk/p['path'])
            verify_tree(sdk,pins)
            # The original working tree never receives a worker ACL or mount.
            container.allow_read(self.volume.root,directory=True)
            container.allow_read(self.root,directory=True)
            container._acl(container.leases[-1],1,0x1301BF,3)
            container._acl(container.leases[-1],3,0xC0000,3)
            args=list(command);args[args.index('-C')+1]=str(self.root)
            with self.guard:
                if self.cancelled:raise AccessDenied('Git cancelled before launch')
                process=container.launch(args,cwd=self.root,memory_mib=512);self.active=process
            try:result=process.communicate(timeout=timeout,limit=limit,combined=True)
            finally:
                with self.guard:self.active=None
                process.close()
        if self.cancelled:raise AccessDenied('Git operation cancelled')
        self.check_source();return result

    def cancel(self):
        with self.guard:
            self.cancelled=True
            if self.active is not None:self.active.kernel.TerminateJobObject(self.active.job,125)

    def close(self):
        if self.closed:return
        self.cancel()
        if not self.idle.wait(45):
            self._cleanup_unknown();raise AccessDenied('Git process cleanup has not completed')
        try:self.volume.close()
        except BaseException:self._cleanup_unknown();raise
        finally:self.closed=True
