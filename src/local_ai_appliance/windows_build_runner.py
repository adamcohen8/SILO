"""Separately enrolled LPAC build runner. No caller approval or host fallback."""
import base64
from dataclasses import asdict
import hashlib
import os
from pathlib import Path
import platform
import threading
import math
from .asset_integrity import digest_file
from .build_policy import BuildPolicy
from .folders import AccessDenied
from .machine_security import anchor
from .managed_code_storage import volume_record
from .offline_environment import OfflineEnvironment
from .signed_policy import canonical,verify_document
from .windows_code_runner import WindowsCodeRunner,RunnerContainer,BOUNDARY_TESTS
from .windows_code_storage import require_clean_state

BUILD_CHECKS=BOUNDARY_TESTS-{'child_process'}|{'children_contained','process_limit','job_memory','environment_readonly','offline_dependencies'}


def qualify_build(data,digest,configuration,*,key,key_digest,clock=None):
    import time
    if hashlib.sha256(data).hexdigest()!=digest: raise AccessDenied('Build acceptance digest changed')
    v=verify_document(data,key,key_digest,limit=128*1024)
    if (set(v)!={'format_version','scope','configuration','checks','native_os','expires'}
            or type(v['format_version']) is not int or v['format_version']!=1 or v['scope']!='synthetic_build_evaluation'
            or canonical(v['configuration'])!=canonical(configuration) or v['native_os']!='Windows'
            or type(v['expires']) not in (int,float) or not math.isfinite(v['expires']) or v['expires']<=(clock or time.time)()
            or not isinstance(v['checks'],dict) or set(v['checks'])!=BUILD_CHECKS):
        raise AccessDenied('Exact independent build boundary acceptance is required')
    for result in v['checks'].values():
        if (not isinstance(result,dict) or set(result)!={'status','evidence_sha256'} or result['status']!='passed'
                or not isinstance(result['evidence_sha256'],str) or len(result['evidence_sha256'])!=64
                or any(c not in '0123456789abcdef' for c in result['evidence_sha256'])):
            raise AccessDenied('Every build check requires passed native evidence')
    return v


class WindowsBuildRunner(WindowsCodeRunner):
    def __init__(self,root,state,security,environment_id,*,policy=None):
        if os.name!='nt': raise AccessDenied('Build execution requires native Windows')
        self.root,self.state=Path(root).resolve(),Path(state).resolve()
        self.security=security; security.check()
        if not security.settings['allow_code']:
            raise AccessDenied('Build tools require ordinary-user managed code policy')
        self.policy=policy or BuildPolicy()
        if not isinstance(self.policy,BuildPolicy): raise AccessDenied('Build runner needs its separate resource policy')
        from .host_capabilities import environment_registry
        registration=environment_registry(security).get(environment_id)
        if not isinstance(registration,dict) or set(registration)!={'root','sha256'}:
            raise AccessDenied('Administrator must enroll the reviewed offline environment')
        self.registration=registration; self.environment_id=environment_id
        self.environment=OfflineEnvironment(registration['root'],registration['sha256'])
        if (self.environment.value['id']!=environment_id or self.environment.value['platform']!='windows-x64'
                or self.environment.value['license_review']!='reviewed'):
            raise AccessDenied('Environment identity, platform or license review is unsuitable')
        self.sdk=self.environment.root/'payload'; self.sdk_pins=self.environment.value['files']
        self.bootstrap=self.root/'scripts/build_runner_bootstrap.py'
        self.plot=self.root/'src/local_ai_appliance/silo_plot.py'
        self._guard=threading.RLock(); self._cancelled=threading.Event()
        self._idle=threading.Event(); self._idle.set()
        self.active=None; self.closed=False; self.available=False; self._busy=False
        self.volume_record=volume_record(security.store.get('code-volume'))
        self.configuration={'release_sha256':security.release_sha256,'environment_sha256':self.environment.digest,
            'environment_id':environment_id,
            'bootstrap_sha256':digest_file(self.bootstrap),'plot_sha256':digest_file(self.plot),
            'native_version':platform.version(),'boundary':'silo-build-lpac-1','policy':asdict(self.policy),
            'code_volume_sha256':hashlib.sha256(canonical(self.volume_record)).hexdigest()}
        require_clean_state(self.state)
        self.acceptance_record=security.store.get('build-acceptance-'+environment_id)
        if self.acceptance_record is not None:
            key,digest=anchor(security.store,'reviewer-anchor')
            qualify_build(base64.b64decode(self.acceptance_record['envelope'],validate=True),
                self.acceptance_record['sha256'],self.configuration,key=key,key_digest=digest)
            self.available=not security.candidate

    def execute(self,files,inputs,entrypoint,arguments,policy):
        if arguments: raise AccessDenied('Build profiles accept no model-selected options')
        return self.execute_operation(files,inputs,'run',entrypoint,policy)

    def execute_operation(self,files,inputs,operation,entrypoint,policy):
        self._require_acceptance(policy)
        self.environment.plan(operation,entrypoint)
        if operation=='lsp': raise AccessDenied('Language-server sessions use the separately gated navigation service')
        from dataclasses import replace
        result=self._execute_candidate(files,inputs,entrypoint,(),policy,operation=operation)
        return replace(result,boundary='native-build-lpac-managed-fixed-ntfs-vhd')

    def _require_acceptance(self,policy):
        from .host_capabilities import environment_registry
        self.security.check()
        if (self.security.candidate or not self.available or self.security.store.get('build-acceptance-'+self.environment_id)!=self.acceptance_record
                or environment_registry(self.security).get(self.environment_id)!=self.registration
                or policy!=self.policy):
            self.available=False; raise AccessDenied('Build policy, environment or acceptance changed')
        key,digest=anchor(self.security.store,'reviewer-anchor')
        qualify_build(base64.b64decode(self.acceptance_record['envelope'],validate=True),
            self.acceptance_record['sha256'],self.configuration,key=key,key_digest=digest)
    def language_query(self,files,path,action,*,line=1,column=1):
        self._require_acceptance(self.policy); self.environment.plan('lsp',path)
        from .host_capabilities import require_capability
        require_capability(self.security,'language-service',{'environment_sha256':self.environment.digest,'boundary':'lsp-readonly-1'},
            {'readonly_workspace','external_locations','server_requests','frame_limits','timeout','cleanup','network'})
        result=self._execute_candidate(files,{},path,({'action':action,'line':line,'column':column},),self.policy,operation='lsp')
        from .model import strict_json
        return strict_json(result.stdout.encode())

    def _communicate(self,process,work,files,entrypoint,arguments,operation,policy):
        if operation!='lsp': return super()._communicate(process,work,files,entrypoint,arguments,operation,policy)
        from .language_service import NativeLanguageTransport,LanguageClient
        from .model import json_bytes
        transport=NativeLanguageTransport(process,timeout=min(20,policy.timeout_seconds),max_output=policy.max_output_bytes)
        try:
            response=LanguageClient(transport,work,files).query(path=entrypoint,**arguments[0])
            return 0,json_bytes(response),b''
        finally: transport.close()

    def _container(self,work):
        env={key:str(work) for key in ('TEMP','TMP','LOCALAPPDATA','APPDATA','USERPROFILE')}
        env.update(PATH=os.pathsep.join(str(self.sdk/p) for p in self.environment.value['paths']),
            CARGO_NET_OFFLINE='true',CARGO_HOME=str(work/'cargo-home'),RUSTUP_HOME=str(self.sdk/'rustup'),
            npm_config_offline='true',npm_config_audit='false',npm_config_fund='false',
            npm_config_ignore_scripts='true',npm_config_cache=str(work/'npm-cache'),
            PIP_NO_INDEX='1',PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',NODE_PATH=str(self.sdk/'node_modules'))
        c=RunnerContainer(env); c.process_limit=self.policy.max_processes; return c

    def _command(self,work,staged,library,entrypoint,arguments,operation):
        plan=self.environment.plan(operation,entrypoint)
        replacements={'{work}':str(work),'{library}':str(library),'{bootstrap}':str(library/'bootstrap.py'),
                      '{environment}':str(self.environment.root/'silo-environment.json'),'{payload}':str(self.sdk).replace('\\','/')}
        def expand(argument):
            for key,value in replacements.items(): argument=argument.replace(key,value)
            return argument
        return [str(self.sdk/plan['executable'])]+[expand(a) for a in plan['arguments']]

    def _retain_output(self,name,kind):
        # Build caches/binaries stay in the bounded disposable volume and are
        # destroyed with it. Source edits, test output and small text artifacts
        # return to the host; snapshots never turn a binary into run authority.
        if name.split('/')[0] in {'target','build','node_modules','cargo-home','npm-cache'}: return False
        return Path(name).suffix.lower() not in {'.exe','.o','.obj','.a','.lib','.wasm','.pyc','.pdb','.dll'}
