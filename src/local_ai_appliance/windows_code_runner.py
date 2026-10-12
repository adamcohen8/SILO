"""Separate LPAC Python runner candidate, gated by independently reviewed evidence.

No POSIX fallback, environment bypass, task-time download, shell, or model-owned
approval. Native acceptance is deliberately absent from this source checkout.
"""
import ctypes as C
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import threading

from .asset_integrity import ordinary, digest_file, verify_tree
from .code_workspace import RunResult, MAX_FILES, MAX_FILE, code_path
from .folders import AccessDenied
from .model import strict_json
from .windows_container import AppContainer, bind, ok, U32, PTR, WSTR, BOOL, ExplicitAccess, Trustee
from .windows_code_storage import require_clean_state
from .managed_code_storage import ManagedVolume,volume_record
from .signed_policy import canonical
from .windows_folders import WindowsFolderBroker
from .execution_policy import ExecutionPolicy

BOUNDARY_TESTS = frozenset({'token','inputs_readonly','runtime_readonly','outside_filesystem','profile_storage',
    'registry_storage','network_ipv4_tcp','network_ipv4_udp','network_ipv6','dns','loopback','ipc',
    'child_process','memory','output','disk','timeout','cleanup','recovery'})


def qualify(data,expected_digest,configuration,*,reviewer_public_key=None,reviewer_key_sha256=None,clock=None):
    if not isinstance(expected_digest,str) or len(expected_digest)!=64 or hashlib.sha256(data).hexdigest()!=expected_digest:
        raise AccessDenied('Execution acceptance differs from the independently reviewed digest')
    try:
        from .signed_policy import verify_document
        import time
        if reviewer_public_key is None or reviewer_key_sha256 is None:
            raise AccessDenied('Code acceptance requires an independently protected reviewer signature')
        value=verify_document(data,reviewer_public_key,reviewer_key_sha256,limit=128*1024)
        if (set(value)!={'format_version','scope','configuration','checks','native_os','expires'} or type(value['format_version']) is not int
                or value['format_version']!=1 or value['scope']!='synthetic_code_evaluation'
                or json.dumps(value['configuration'],sort_keys=True)!=json.dumps(configuration,sort_keys=True)
                or value['native_os']!='Windows'
                or not isinstance(value['checks'],dict) or set(value['checks'])!=BOUNDARY_TESTS
                or type(value['expires']) not in {int,float} or value['expires'] <= (clock or time.time)()):
            raise ValueError('Invalid native boundary acceptance')
        for result in value['checks'].values():
            if (not isinstance(result,dict) or set(result)!={'status','evidence_sha256'} or result['status']!='passed'
                    or not isinstance(result['evidence_sha256'],str) or len(result['evidence_sha256'])!=64
                    or any(c not in '0123456789abcdef' for c in result['evidence_sha256'])):
                raise ValueError('Skipped, missing or failed boundary evidence')
        return value
    except (ValueError,TypeError,KeyError) as error:
        raise AccessDenied('Complete independently reviewed native boundary evidence is required') from error


class RunnerContainer(AppContainer):
    lpac=True

    def __init__(self,environment=None):
        self.environment=environment or {}
        self.registry=[]
        super().__init__(evaluation=True)
        bind(self.userenv,'GetAppContainerFolderPath',C.c_int32,[WSTR,C.POINTER(PTR)])
        pointer=PTR()
        result=self.userenv.GetAppContainerFolderPath(self.sid_text,C.byref(pointer))
        if result!=0:
            self.close(); raise AccessDenied('Private profile location unavailable')
        ole=C.WinDLL('ole32'); bind(ole,'CoTaskMemFree',None,[PTR])
        try: self.profile=Path(C.wstring_at(pointer))
        finally: ole.CoTaskMemFree(pointer)
        try:
            # Default private profile storage would otherwise bypass VHD limits.
            for directory,children,files in os.walk(self.profile,followlinks=False):
                if len(self.leases)>256: raise AccessDenied('Unexpected profile storage inventory')
                for path,is_directory in [(Path(directory),True)]+[(Path(directory)/p,False) for p in files]:
                    ordinary(path,directory=is_directory)
                    self.allow_read(path,directory=is_directory)
                    self._acl(self.leases[-1],3,0xD0156,3 if is_directory else 0)
                for child in children: ordinary(Path(directory)/child,directory=True)
        except BaseException:
            self.close(); raise

    def prepare_process(self,process):
        a=self.adv
        bind(a,'ImpersonateLoggedOnUser',BOOL,[PTR]); bind(a,'RevertToSelf',BOOL,[])
        bind(self.userenv,'GetAppContainerRegistryLocation',C.c_int32,[U32,C.POINTER(PTR)])
        bind(a,'RegCloseKey',C.c_long,[PTR])
        bind(a,'RegEnumKeyExW',C.c_long,[PTR,U32,WSTR,C.POINTER(U32),PTR,PTR,PTR,PTR])
        bind(a,'RegOpenKeyExW',C.c_long,[PTR,WSTR,U32,U32,C.POINTER(PTR)])
        token,key=PTR(),PTR()
        ok(a.OpenProcessToken(process.info.process,14,C.byref(token)))
        try:
            if U32.from_buffer(self._token_value(token,46)).value!=1:
                raise AccessDenied('Runner token is not a less-privileged AppContainer')
            ok(a.ImpersonateLoggedOnUser(token))
            try: result=self.userenv.GetAppContainerRegistryLocation(0x60009,C.byref(key))
            finally: ok(a.RevertToSelf())
            if result!=0: raise AccessDenied('Private registry location unavailable')
        finally: self.kernel.CloseHandle(token)
        def protect(handle,depth=0):
            if handle not in self.registry: self.registry.append(handle)
            if depth>16 or len(self.registry)>256: raise AccessDenied('Unexpected private registry inventory')
            children=[]; index=0
            while True:
                name=C.create_unicode_buffer(256); length=U32(len(name))
                result=a.RegEnumKeyExW(handle,index,name,C.byref(length),None,None,None,None)
                if result==259: break
                if result!=0: raise AccessDenied('Private registry inventory unavailable')
                child=PTR()
                if a.RegOpenKeyExW(handle,name.value,0,0x60009,C.byref(child))!=0:
                    raise AccessDenied('Private registry child unavailable')
                children.append(child); index+=1
                self.registry.append(child)
                if index>256: raise AccessDenied('Private registry budget exceeded')
            self._registry_acl(handle,3,0xD0006)
            for child in children: protect(child,depth+1)
        protect(key)
        process.token_evidence.update(lpac=True,profile_storage_readonly=True,registry_storage_readonly=True)

    def _registry_acl(self,handle,mode,mask):
        descriptor,dacl,new=PTR(),PTR(),PTR()
        result=self.adv.GetSecurityInfo(handle,4,4,None,None,C.byref(dacl),None,C.byref(descriptor))
        if result or not dacl.value: raise AccessDenied('Private registry ACL unavailable')
        try:
            entry=ExplicitAccess(mask,mode,2,Trustee(None,0,0,0,self.sid))
            if self.adv.SetEntriesInAclW(1,C.byref(entry),dacl,C.byref(new))!=0:
                raise AccessDenied('Private registry ACL composition failed')
            if self.adv.SetSecurityInfo(handle,4,4,None,None,new,None)!=0:
                raise AccessDenied('Private registry write closure failed')
        finally:
            if new.value: self.kernel.LocalFree(new)
            self.kernel.LocalFree(descriptor)

    def close(self):
        for process in getattr(self,'processes',[]): process.close()
        errors=[]
        for key in reversed(self.registry):
            try: self._registry_acl(key,4,0)
            except Exception as error: errors.append(error)
            finally: self.adv.RegCloseKey(key)
        self.registry.clear()
        super().close()
        if errors: raise AccessDenied('Runner private registry cleanup incomplete')

    def readonly_tree(self,path):
        # Only owned staged input files. Existing toolchains use temporary R/RX
        # leases and must never receive writable ACLs or a low-integrity label.
        self.allow_read(path,directory=True)
        self._acl(self.leases[-1],3,0xD0156,3)


class WindowsCodeRunner:
    def __init__(self,root,sdk,state,*,policy=None,acceptance=None,acceptance_sha256=None,security=None):
        if os.name!='nt': raise AccessDenied('Generated code requires native Windows; no portable execution fallback')
        self.root,self.sdk,self.state=Path(root),Path(sdk),Path(state)
        self.policy=policy or ExecutionPolicy()
        if security is None:
            raise AccessDenied('Generated code requires protected machine deployment policy')
        self.security=security
        security.check()
        if not security.settings['allow_code']:
            raise AccessDenied('Administrator deployment policy disables generated code')
        if self.sdk.resolve()!= (self.root.parent/'code').resolve():
            raise AccessDenied('Use the pinned standalone code Python toolchain')
        self._guard=threading.RLock(); self._cancelled=threading.Event()
        self._idle=threading.Event(); self._idle.set()
        self.active=None; self.closed=False; self.available=False; self._busy=False
        self.bootstrap=self.root/'scripts/code_runner_bootstrap.py'
        self.plot=self.root/'src/local_ai_appliance/silo_plot.py'
        self.executable=self.sdk/'python.exe'
        for path in (self.bootstrap,self.plot,self.executable): ordinary(path)
        from .configuration_catalog import authorize_configuration
        authorize_configuration(self.root,'nemotron-4090-cp314-evaluation-1',operation='launch',workload='code_evaluation')
        release_files=security.bundle['files']
        self.sdk_pins=[{**item,'path':item['path'].removeprefix('code/')} for item in release_files
                       if item['path'].startswith('code/')]
        self.configuration={'release_sha256':security.release_sha256,
            'bootstrap_sha256':digest_file(self.bootstrap),'plot_sha256':digest_file(self.plot),
            'native_version':platform.version(),'interpreter':'3.14.8','boundary':'silo-lpac-managed-2',
            'policy':asdict(self.policy)}
        self.volume_record=volume_record(security.store.get('code-volume'))
        self.configuration['code_volume_sha256']=hashlib.sha256(canonical(self.volume_record)).hexdigest()
        require_clean_state(self.state)
        if acceptance is not None or acceptance_sha256 is not None:
            raise AccessDenied('Caller-supplied execution approval is unavailable; enroll signed evidence as administrator')
        record=security.store.get('code-acceptance')
        if record is not None:
            import base64
            from .machine_security import anchor
            key,digest=anchor(security.store,'reviewer-anchor')
            data=base64.b64decode(record['envelope'],validate=True)
            qualify(data,record['sha256'],self.configuration,reviewer_public_key=key,reviewer_key_sha256=digest)
            self.acceptance_record=record
            self.available=True

    def execute(self,files,inputs,entrypoint,arguments,policy):
        self.security.check()
        if self.security.store.get('code-acceptance') != getattr(self,'acceptance_record',None):
            self.available=False
            raise AccessDenied('Execution acceptance changed; restart after independent review')
        if not self.available: raise AccessDenied('Reviewed native boundary acceptance is required before generated code execution')
        if policy!=self.policy: raise AccessDenied('Execution policy differs from the accepted resource limits')
        return self._execute_candidate(files,inputs,entrypoint,arguments,policy)

    def _container(self,work):
        return RunnerContainer({key:str(work) for key in ('TEMP','TMP','LOCALAPPDATA','APPDATA','USERPROFILE')})

    def _command(self,work,staged,library,entrypoint,arguments,operation):
        if operation!='run': raise AccessDenied('The Python v1 runner supports only run')
        return [str(self.executable),'-I','-S','-B','-u',str(library/'bootstrap.py'),str(work),str(staged),str(library),entrypoint,*arguments]

    def _communicate(self,process,work,files,entrypoint,arguments,operation,policy):
        return process.communicate(timeout=policy.timeout_seconds,limit=policy.max_output_bytes,combined=True)

    def _retain_output(self,name,kind): return True

    def _execute_candidate(self,files,inputs,entrypoint,arguments,policy,*,operation='run'):
        # Trusted native acceptance tooling may exercise this candidate. It is
        # not a registered operation and cannot be selected by model output.
        with self._guard:
            if self.closed or self._busy: raise AccessDenied('Runner is closed or busy')
            self._cancelled.clear()
            self._busy=True
            self._idle.clear()
        volume=container=broker=None
        try:
            self.security.check()
            self.security.audit.emit('execution','attempt',object_sha256=hashlib.sha256(files[entrypoint]).hexdigest())
            require_clean_state(self.state)
            verify_tree(self.sdk,self.sdk_pins,self._check_cancelled)
            plot_data=self.plot.read_bytes(); bootstrap_data=self.bootstrap.read_bytes()
            for key,data in (('plot_sha256',plot_data),('bootstrap_sha256',bootstrap_data)):
                if hashlib.sha256(data).hexdigest()!=self.configuration[key]:
                    raise AccessDenied('Pinned execution support changed after acceptance')
            if self.security.store.get('code-volume')!=self.volume_record:
                raise AccessDenied('Code volume provisioning changed; independent acceptance and restart required')
            volume=ManagedVolume(self.security,policy.max_workspace_bytes)
            work=volume.root/'work'
            container=self._container(work)
            container.allow_managed_read(self.sdk,directory=True)
            if hasattr(self,'environment'):
                container.allow_managed_read(self.environment.root,directory=True)
                container.allow_managed_read(self.environment.root/'silo-environment.json')
                for pin in self.sdk_pins: container.allow_managed_read(self.sdk/pin['path'])
            container.allow_read(volume.root,directory=True)
            container.create_private_ipc(work)
            # Deny changing security descriptors even on runner-created files.
            container._acl(container.leases[-1],3,0xC0000,3)
            staged=work/'inputs'; staged.mkdir()
            library=work/'silo_plot'; library.mkdir()
            for name,data in inputs.items():
                from .windows_folders import parts
                if len(parts(name))!=1: raise AccessDenied('Unsafe staged input')
                (staged/name).write_bytes(data)
            for name,data in files.items():
                code_path(name); target=work/name; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
            (library/'silo_plot.py').write_bytes(plot_data)
            bootstrap=library/'bootstrap.py'; bootstrap.write_bytes(bootstrap_data)
            container.readonly_tree(staged); container.readonly_tree(library)
            if operation=='lsp': container.readonly_tree(work)
            command=self._command(work,staged,library,entrypoint,arguments,operation)
            with self._guard:
                if self._cancelled.is_set(): raise AccessDenied('Runner cancelled before launch')
                process=container.launch(command,cwd=work,memory_mib=policy.memory_mib); self.active=process
            code,out,err=self._communicate(process,work,files,entrypoint,arguments,operation,policy)
            process.close()
            if len(out)+len(err)>policy.max_output_bytes: raise AccessDenied('Combined output budget exceeded')
            if self._cancelled.is_set(): raise AccessDenied('Runner cancelled')
            # No process remains before bytes are copied into the host snapshot.
            # Unique SID access is revoked by container cleanup before review.
            container.close(); container=None
            broker=WindowsFolderBroker(validation_mode=True,max_file_bytes=MAX_FILE)
            folder=broker.grant(work,'read-only'); outputs={}
            for name,data in inputs.items():
                if broker.read_file(folder.id,'inputs/'+name)!=data:
                    raise AccessDenied('Immutable staged input changed during execution')
            def visit(prefix=''):
                listing=broker.list_directory(folder.id,prefix,limit=1000)
                if listing['truncated']: raise AccessDenied('Runner output inventory exceeded')
                for item in listing['entries']:
                    name=(prefix+'/' if prefix else '')+item['name']
                    if name in {'inputs','silo_plot'}: continue
                    if not self._retain_output(name,item['kind']): continue
                    if item['kind']=='directory':
                        if len(name.split('/'))>8: raise AccessDenied('Output depth exceeded')
                        visit(name)
                    else:
                        code_path(name)
                        if len(outputs)>=MAX_FILES: raise AccessDenied('Runner output count exceeded')
                        outputs[name]=broker.read_file(folder.id,name)
            visit()
            self.security.audit.emit('execution','success' if code == 0 else 'failed',code=code if 0 <= code < 2**63 else 1)
            return RunResult(code,out.decode('utf-8','replace'),err.decode('utf-8','replace'),tuple(sorted(outputs.items())),
                             'native-lpac-managed-fixed-ntfs-vhd')
        finally:
            with self._guard: self.active=None
            errors=[]
            for resource in (broker,container,volume):
                if resource is not None:
                    try: resource.close()
                    except Exception as error: errors.append(type(error).__name__)
            with self._guard: self._busy=False
            try:
                if errors:
                    self.available=False
                    marker=self.state/('cleanup-failed-'+secrets.token_hex(8)+'.json')
                    marker.write_text(json.dumps({'cleanup':'failed','errors':errors,
                        'profile':getattr(container,'name',None),'volume_lease':getattr(volume,'id',None)})+'\n')
                    raise AccessDenied('Owned runner cleanup incomplete; execution disabled until reconciliation')
            finally: self._idle.set()

    def cancel(self):
        self._cancelled.set()
        with self._guard:
            if self.active is not None:
                self.active.kernel.TerminateJobObject(self.active.job,125)

    def _check_cancelled(self):
        if self._cancelled.is_set(): raise AccessDenied('Runner cancelled')

    def close(self):
        self.cancel()
        self.wait()
        with self._guard:
            if self._busy: raise AccessDenied('Wait for owned execution cleanup before closing')
            self.closed=True; self.available=False

    def wait(self):
        if not self._idle.wait(45):
            self.available=False
            raise AccessDenied('Owned execution cleanup has not completed; keep the session closed')
