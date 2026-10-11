"""Host-managed pinned model selection, explicit downloads and offline imports."""
from dataclasses import asdict, dataclass
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import stat
import tempfile
import urllib.request

from .asset_integrity import (ordinary, digest_file, inference_pins, verify_tree, INFERENCE_LOCK_SHA256,
                              cpu_runtime_pins, CPU_RUNTIME_SHA256, CPU_RUNTIME_DIRECTORY)
from .configuration_catalog import authorize_configuration
from .folders import AccessDenied
from .signed_policy import SignedPolicyStore
from .model import strict_json
from .model_adapters import model_adapter

DEFAULT = 'nemotron-4090-cp314-evaluation-1'
FIELDS = {'id','status','model','publishers','jurisdictions','data_scopes','workloads',
          'harness','runtime_lock_sha256','interpreter','gpu_layers','minimum_ram_mib',
          'minimum_vram_mib','license'}
CATALOG_FIELDS = {'adapter', 'display_name', 'native_acceptance', 'source'}
OPTIONAL_FIELDS = CATALOG_FIELDS | {'execution_backend', 'cpu_threads'}
MODEL_CATALOG_PATH = 'profiles/model-catalog.json'
MODEL_CATALOG_SHA256 = '9b40157a18b0cd56860e363fb894bbe0a4ecc18d6f6feab0f136d8a6d5dacbed'
CPU_IDS = {'gemma4-e2b-q4-cpu-evaluation-1', 'gemma4-e4b-q4-cpu-evaluation-1'}
CPU_RAM_RESERVE_MIB = 512  # Nominal laptop RAM can exclude firmware/iGPU reservations.
BUILTIN_IDS = CPU_IDS | {DEFAULT, 'gemma4-26b-a4b-q4-evaluation-1', 'muse-glimmer-30b-q4-evaluation-1',
               'gemma4-31b-q4-evaluation-1', 'gpt-oss-20b-mxfp4-evaluation-1', 'gemma4-12b-q4-evaluation-1',
               'nemotron-cascade2-30b-iq4-xs-evaluation-1', 'nemotron35-lightning-30b-q4-evaluation-1'}


def execution_backend(profile):
    # Policies written before CPU profiles retain their exact CUDA semantics.
    return profile.get('execution_backend', 'cuda')


def execution_binding(profile):
    """Policy fields that require a restart and independent coding review."""
    return (profile['model'], profile['gpu_layers'], profile['runtime_lock_sha256'],
            profile['harness'], profile['interpreter'], profile.get('adapter', 'nemotron3'),
            execution_backend(profile), profile.get('cpu_threads'),
            profile['minimum_ram_mib'], profile['minimum_vram_mib'])


def _validate_model_policy(value):
    if (not isinstance(value,dict) or set(value) != {'format','sequence','expires','profiles',
            'blocked_publishers','blocked_jurisdictions'} or type(value['format']) is not int or value['format'] != 1
            or not isinstance(value['profiles'],list) or not 1 <= len(value['profiles']) <= 32):
        raise AccessDenied('Invalid model policy')
    identifiers = set()
    def tokens(values):
        return (isinstance(values,list) and len(values) <= 64 and len(set(values)) == len(values)
                and all(isinstance(v,str) and re.fullmatch(r'[a-z0-9_.-]{1,100}',v) for v in values))
    if not tokens(value['blocked_publishers']) or not tokens(value['blocked_jurisdictions']):
        raise AccessDenied('Invalid provenance restrictions')
    for profile in value['profiles']:
        if not isinstance(profile,dict) or not FIELDS <= set(profile) or set(profile) - FIELDS - OPTIONAL_FIELDS:
            raise AccessDenied('Invalid model profile')
        identifier = profile['id']
        if not isinstance(identifier,str) or not re.fullmatch(r'[a-z0-9-]{1,64}',identifier) or identifier in identifiers:
            raise AccessDenied('Duplicate or invalid model ID')
        identifiers.add(identifier)
        backend = execution_backend(profile)
        if backend not in {'cpu', 'cuda'}:
            raise AccessDenied('Unsupported execution backend')
        if backend == 'cpu':
            if (identifier not in CPU_IDS or type(profile.get('cpu_threads')) is not int
                    or profile['cpu_threads'] != 4 or type(profile['gpu_layers']) is not int
                    or profile['gpu_layers'] != 0 or type(profile['minimum_vram_mib']) is not int
                    or profile['minimum_vram_mib'] != 0 or profile.get('adapter') != 'gemma4'
                    or profile['runtime_lock_sha256'] != CPU_RUNTIME_SHA256):
                raise AccessDenied('CPU execution requires an explicit reviewed model/runtime profile')
        elif ('cpu_threads' in profile or identifier in CPU_IDS
                or profile['runtime_lock_sha256'] != INFERENCE_LOCK_SHA256):
            raise AccessDenied('CUDA execution requires its reviewed runtime without CPU fallback')
        if (profile['status'] not in {'evaluation_allowed','revoked'} or profile['harness'] != 'silo-langgraph-1'
                or profile['interpreter'] != '3.14.8'
                or not isinstance(profile['data_scopes'],list) or not profile['data_scopes']
                or set(profile['data_scopes']) - {'public','synthetic'}
                or not isinstance(profile['workloads'],list) or not profile['workloads']
                or set(profile['workloads']) - {'documents','code_evaluation'}
                or 'documents' not in profile['workloads']
                or 'code_evaluation' in profile['workloads'] and profile['id'] not in BUILTIN_IDS):
            raise AccessDenied('Unsupported harness/runtime/data policy; custom coding profiles require separate qualification')
        if any(not tokens(profile[key]) or not profile[key] for key in ('publishers','jurisdictions')):
            raise AccessDenied('Model provenance must be explicit')
        model_adapter(profile.get('adapter', 'nemotron3'))
        if 'display_name' in profile and (not isinstance(profile['display_name'], str)
                or not re.fullmatch(r'[A-Za-z0-9 ._-]{1,100}', profile['display_name'])):
            raise AccessDenied('Invalid model display name')
        if 'native_acceptance' in profile and profile['native_acceptance'] not in {'pending', 'partial'}:
            raise AccessDenied('Model profiles cannot grant native acceptance')
        for key,low,high in [('gpu_layers',0 if backend == 'cpu' else 1,1024),
                             ('minimum_ram_mib',1024,1048576),
                             ('minimum_vram_mib',0 if backend == 'cpu' else 1024,1048576)]:
            if type(profile[key]) is not int or not low <= profile[key] <= high:
                raise AccessDenied('Invalid hardware or layer bounds')
        model = profile['model']
        if (not isinstance(model,dict) or set(model) != {'name','size','sha256'}
                or not isinstance(model['name'],str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,160}\.gguf',model['name'])
                or type(model['size']) is not int or not 1 <= model['size'] <= 512*1024**3
                or not re.fullmatch(r'[a-f0-9]{64}',model['sha256'])):
            raise AccessDenied('Model requires a bounded ordinary GGUF with exact size and SHA-256')
        license = profile['license']
        if (not isinstance(license,dict) or set(license) != {'id','source','redistribution'}
                or not isinstance(license['id'],str) or not 1 <= len(license['id']) <= 128
                or not isinstance(license['source'],str) or not license['source'].startswith('https://')
                or len(license['source']) > 1024 or license['redistribution'] not in {'pending','approved','prohibited'}):
            raise AccessDenied('License review metadata is required')
        if 'source' in profile:
            source = profile['source']
            if (not isinstance(source, dict) or set(source) != {'upstream', 'upstream_revision', 'repository',
                    'revision', 'url', 'hash_origin', 'metadata_checked'}
                    or any(not isinstance(source[k], str) for k in source)
                    or any(not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,160}', source[k])
                           for k in ('upstream', 'repository'))
                    or any(not re.fullmatch(r'[a-f0-9]{40}', source[k]) for k in ('upstream_revision', 'revision'))
                    or source['url'] != 'https://huggingface.co/'+source['repository']+'/resolve/'+source['revision']+'/'+model['name']
                    or source['hash_origin'] not in {'publisher-lfs-metadata', 'publisher-lfs-metadata-and-prior-local-verification'}
                    or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', source['metadata_checked'])):
                raise AccessDenied('Invalid immutable model provenance')


def validate_model_policy(value):
    try:
        return _validate_model_policy(value)
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError) as error:
        raise AccessDenied('Malformed or unsupported signed model policy') from error


def builtin_profiles(root):
    """Host-pinned evaluation candidates, never a downloaded policy fallback."""
    path = Path(root)/MODEL_CATALOG_PATH
    if ordinary(path).st_size > 128 * 1024:
        raise AccessDenied('Model catalog is oversized')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != MODEL_CATALOG_SHA256:
        raise AccessDenied('Model catalog differs from the reviewed host policy')
    try:
        value = strict_json(data)
        if (not isinstance(value, dict) or set(value) != {'format_version', 'authority', 'profiles'}
                or type(value['format_version']) is not int or value['format_version'] != 1
                or value['authority'] != 'development_evaluation_only'):
            raise AccessDenied('Invalid embedded model catalog')
        validate_model_policy({'format': 1, 'sequence': 1, 'expires': 1, 'profiles': value['profiles'],
                               'blocked_publishers': [], 'blocked_jurisdictions': []})
        if ({p['id'] for p in value['profiles']} != BUILTIN_IDS
                or any(not CATALOG_FIELDS <= set(p) for p in value['profiles'])):
            raise AccessDenied('Incomplete embedded model catalog')
        return value['profiles']
    except (ValueError, TypeError, KeyError, RecursionError) as error:
        raise AccessDenied('Malformed embedded model catalog') from error

@dataclass(frozen=True)
class Hardware:
    ram_mib: int | None
    cpu_count: int | None
    gpus: tuple[dict,...]
    platform: str
    architecture: str = 'unknown'


def _gpu_inventory_tool(system_directory):
    # Windows driver servicing can hard-link this trusted system executable.
    # This exception is limited to the fixed OS tool, never application assets.
    directory = Path(system_directory)
    ordinary(directory, directory=True)
    candidate = directory/'nvidia-smi.exe'
    info = candidate.lstat()
    if (not stat.S_ISREG(info.st_mode)
            or getattr(info, 'st_file_attributes', 0) & 0x441400):
        raise AccessDenied('Trusted GPU inventory executable unavailable')
    return candidate


def scan_hardware():
    import sys
    import platform
    ram = None
    if os.name == 'nt':
        import ctypes as C
        class Memory(C.Structure):
            _fields_ = [('length',C.c_uint32),('load',C.c_uint32),
                *[(name,C.c_uint64) for name in ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]]
        value = Memory(); value.length = C.sizeof(value)
        if C.windll.kernel32.GlobalMemoryStatusEx(C.byref(value)): ram = value.total//1024**2
    elif sys.platform == 'darwin':
        result = subprocess.run(['/usr/sbin/sysctl','-n','hw.memsize'],capture_output=True,timeout=5,check=True)
        ram = int(result.stdout.strip())//1024**2
    elif hasattr(os,'sysconf'):
        ram = os.sysconf('SC_PHYS_PAGES')*os.sysconf('SC_PAGE_SIZE')//1024**2
    gpus = []
    if os.name == 'nt':
        # No PATH search and no command proposed by the model.
        import ctypes as C
        kernel=C.WinDLL('kernel32',use_last_error=True)
        kernel.GetSystemDirectoryW.argtypes=[C.c_wchar_p,C.c_uint32]
        kernel.GetSystemDirectoryW.restype=C.c_uint32
        buffer=C.create_unicode_buffer(32768)
        count=kernel.GetSystemDirectoryW(buffer,len(buffer))
        if not 0<count<len(buffer):raise AccessDenied('Trusted Windows system directory is unavailable')
        candidate = Path(buffer.value)/'nvidia-smi.exe'
        if candidate.exists():
            candidate = _gpu_inventory_tool(candidate.parent)
            # NVML needs the machine Program Files location. Resolve it through
            # Windows, without inheriting PATH, proxy or credential variables.
            shell=C.WinDLL('shell32',use_last_error=True)
            shell.SHGetFolderPathW.argtypes=[C.c_void_p,C.c_int,C.c_void_p,C.c_uint32,C.c_wchar_p]
            shell.SHGetFolderPathW.restype=C.c_int32
            programs=C.create_unicode_buffer(32768)
            if shell.SHGetFolderPathW(None,0x26,None,0,programs) != 0 or not programs.value:
                raise AccessDenied('Trusted Windows Program Files directory is unavailable')
            ordinary(Path(programs.value),directory=True)
            environment={'SystemRoot':str(candidate.parent.parent),'ProgramFiles':programs.value}
            result = subprocess.run([str(candidate),'--query-gpu=name,memory.total','--format=csv,noheader,nounits'],
                capture_output=True,timeout=10,env=environment,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if result.returncode == 0 and len(result.stdout) <= 8192:
                import csv
                for row in csv.reader(result.stdout.decode('utf-8').splitlines()):
                    if len(row) == 2 and row[1].strip().isdigit():
                        gpus.append({'name':row[0].strip()[:128],'vram_mib':int(row[1])})
    return Hardware(ram,os.cpu_count(),tuple(gpus),sys.platform,platform.machine().lower())


class ModelManager:
    def __init__(self,root,vault,*,clock=None,required_key_sha256=None,model_cache=None):
        self.root,self.vault = Path(root),vault
        self.model_cache=Path(model_cache) if model_cache is not None else self.root/'artifacts/inference/imported'
        if required_key_sha256 is not None and not re.fullmatch(r'[a-f0-9]{64}',required_key_sha256):
            raise AccessDenied('Invalid required organization policy key digest')
        self.required_key_sha256=required_key_sha256
        self.policy = SignedPolicyStore(vault,**({'clock':clock} if clock else {}))

    def current_policy(self):
        anchor=self.vault.get('trust-anchor')
        if self.required_key_sha256 is not None and (anchor is None or anchor['sha256']!=self.required_key_sha256):
            raise AccessDenied('Required organization policy trust anchor is missing or changed')
        policy=self.policy.current(validate_model_policy)
        if policy is None and (anchor is not None or self.required_key_sha256 is not None):
            raise AccessDenied('Enrolled organization policy is missing; embedded fallback denied')
        return policy

    def profiles(self):
        policy = self.current_policy()
        if policy is not None:
            return policy['profiles']
        return builtin_profiles(self.root)

    def authorize(self,identifier,*,operation='launch',data_scope='synthetic',workload='documents'):
        if operation not in {'install','launch'}: raise AccessDenied('Invalid model operation')
        policy = self.current_policy()
        profile = next((p for p in self.profiles() if p['id'] == identifier),None)
        if (profile is None or profile['status'] != 'evaluation_allowed' or data_scope not in profile['data_scopes']
                or workload not in profile['workloads'] or workload=='code_evaluation' and data_scope!='synthetic'
                or profile['license']['redistribution'] == 'prohibited'):
            raise AccessDenied('Model is unknown, revoked, prohibited or outside project scope')
        if policy:
            if (set(profile['publishers']) & set(policy['blocked_publishers'])
                    or set(profile['jurisdictions']) & set(policy['blocked_jurisdictions'])):
                raise AccessDenied('Model provenance is prohibited by administrator policy')
        else:
            authorize_configuration(self.root,identifier,operation=operation,data_scope=data_scope,workload=workload)
        if workload == 'code_evaluation':
            reviewed = next((p for p in builtin_profiles(self.root) if p['id'] == identifier), None)
            if reviewed is None or execution_binding(profile) != execution_binding(reviewed):
                raise AccessDenied('Selected model requires a separately reviewed coding profile')
        return profile

    def selected(self):
        saved = self.vault.get('selected-model')
        return saved['id'] if saved else DEFAULT

    def select(self,identifier,*,data_scope='synthetic'):
        profile = self.authorize(identifier,data_scope=data_scope)
        self.verify_model(profile)
        self.vault.put('selected-model',{'id':identifier})
        return profile

    def model_path(self,profile):
        managed = self.model_cache/ (profile['model']['sha256']+'.gguf')
        if os.path.lexists(managed): return managed
        return self.root/'artifacts/inference/downloads'/profile['model']['name']

    def verify_model(self,profile, cancel=lambda: None):
        path = self.model_path(profile); pin = profile['model']
        if ordinary(path).st_size != pin['size'] or digest_file(path, cancel) != pin['sha256']:
            raise AccessDenied('Model bytes differ from administrator allowlist')
        with path.open('rb') as stream:
            if stream.read(4) != b'GGUF': raise AccessDenied('Model is not a GGUF file')
        return path

    def installed(self, profile):
        # Listing never hashes tens of GiB; selection/launch still verify every byte.
        try:
            ordinary(self.model_path(profile))
            return True
        except FileNotFoundError:
            return False

    def install(self, identifier, *, data_scope='synthetic', cancel=lambda: None, progress=lambda text: None):
        """Explicit host download, with no ambient credentials, proxies or discovery."""
        from .evaluation_install import HTTPSRedirects
        profile = self.authorize(identifier, operation='install', data_scope=data_scope)
        if self.installed(profile):
            return self.verify_model(profile, cancel)
        if 'source' not in profile:
            raise AccessDenied('No pinned download source. Use /model import ID PATH for an offline file.')
        pin = profile['model']
        parent = self.model_cache
        parent.mkdir(mode=0o700, parents=True, exist_ok=True); ordinary(parent, directory=True)
        if shutil.disk_usage(parent).free < pin['size'] + 256 * 1024**2:
            raise AccessDenied('Insufficient free disk space for the selected model')
        descriptor, temporary = tempfile.mkstemp(prefix='.model-', dir=parent)
        published = False
        try:
            count, digest = 0, hashlib.sha256()
            with os.fdopen(descriptor, 'wb') as output:
                cancel()
                request = urllib.request.Request(profile['source']['url'], headers={'User-Agent': 'SILO-Model-Installer/1'})
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), HTTPSRedirects())
                with opener.open(request, timeout=15) as response:
                    if not response.url.startswith('https://') or response.status != 200:
                        raise AccessDenied('Model download requires a complete HTTPS response')
                    while True:
                        cancel()
                        read = getattr(response, 'read1', response.read)
                        block = read(min(1024 * 1024, pin['size'] + 1 - count))
                        if not block: break
                        count += len(block)
                        if count > pin['size']: raise AccessDenied('Download exceeded the pinned model size')
                        digest.update(block); output.write(block)
                        progress(f'Downloading {profile.get("display_name", identifier)}: {count / 1024**3:.2f} / {pin["size"] / 1024**3:.2f} GiB')
                output.flush(); os.fsync(output.fileno())
            cancel()
            if count != pin['size'] or digest.hexdigest() != pin['sha256']:
                raise AccessDenied('Downloaded model differs from the pinned size or SHA-256')
            if digest_file(temporary, cancel) != pin['sha256']:
                raise AccessDenied('Downloaded model changed before publication')
            # Recheck policy after a potentially long download, before publication.
            current = self.authorize(identifier, operation='install', data_scope=data_scope)
            if current != profile: raise AccessDenied('Model policy changed during installation')
            with Path(temporary).open('rb') as stream:
                if stream.read(4) != b'GGUF': raise AccessDenied('Downloaded model is not GGUF')
            cancel()
            destination = parent/(pin['sha256']+'.gguf')
            info = ordinary(temporary)
            try:
                os.link(temporary, destination)
                published = True
            except FileExistsError: pass
        finally:
            Path(temporary).unlink(missing_ok=True)
        try:
            result = self.verify_model(profile, cancel)
            cancel()
            return result
        except BaseException:
            if published:
                current = ordinary(destination)
                if (current.st_dev, current.st_ino) == (info.st_dev, info.st_ino): destination.unlink()
            raise

    def remove(self, identifier):
        # Revoked models may still be removed; policy remains authoritative for identity.
        profile = next((p for p in self.profiles() if p['id'] == identifier), None)
        if profile is None: raise AccessDenied('Unknown model')
        selected = next((p for p in self.profiles() if p['id'] == self.selected()), None)
        if selected and self.model_path(selected) == self.model_path(profile):
            raise AccessDenied('Unload the active model before removing it')
        path = self.model_path(profile)
        if path.parent != self.model_cache:
            raise AccessDenied('This legacy model belongs to the verified application payload. Repair with the new installer before removing it.')
        ordinary(self.model_cache, directory=True); ordinary(path)
        path.unlink()
        return profile['model']['size']

    def import_model(self,identifier,path):
        profile = self.authorize(identifier,operation='install')
        source = Path(path); pin = profile['model']
        if ordinary(source).st_size != pin['size'] or digest_file(source) != pin['sha256']:
            raise AccessDenied('Offline import does not match allowed model bytes')
        parent = self.model_cache
        parent.mkdir(mode=0o700,parents=True,exist_ok=True); ordinary(parent,directory=True)
        destination = parent/(pin['sha256']+'.gguf')
        if destination.exists():
            self.verify_model(profile); return destination
        descriptor,temporary = tempfile.mkstemp(prefix='.model-',dir=parent)
        try:
            count,digest=0,hashlib.sha256()
            with os.fdopen(descriptor,'wb') as output,source.open('rb') as input:
                while block:=input.read(min(8*1024*1024,pin['size']+1-count)):
                    count+=len(block)
                    if count>pin['size']:raise AccessDenied('Offline model grew while copying')
                    digest.update(block);output.write(block)
                output.flush();os.fsync(output.fileno())
            if count!=pin['size'] or digest.hexdigest()!=pin['sha256']:
                raise AccessDenied('Offline model changed during import')
            if ordinary(temporary).st_size != pin['size'] or digest_file(temporary) != pin['sha256']:
                raise AccessDenied('Offline model changed during import')
            # Atomic new file only, including Windows; never replace another model.
            os.link(temporary,destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
        self.verify_model(profile); return destination

    def launch_assets(self,*,data_scope='synthetic',cancel=lambda:None):
        profile = self.authorize(self.selected(),data_scope=data_scope)
        if os.name == 'nt':
            hardware = scan_hardware()
            if not self.hardware_fit(profile, hardware):
                raise AccessDenied('Selected model needs its stated hardware and explicit CPU/CUDA backend; no automatic fallback')
        if execution_backend(profile) == 'cpu':
            pins = cpu_runtime_pins(self.root)
            runtime = self.root/CPU_RUNTIME_DIRECTORY
        else:
            pins = inference_pins(self.root)
            runtime = self.root/'artifacts/inference/runtime-b11433-cuda12.4'
        verify_tree(runtime,pins['extracted_runtime'],cancel)
        model = self.verify_model(profile, cancel)
        return runtime,model,profile

    @staticmethod
    def hardware_fit(profile, hardware):
        backend = execution_backend(profile)
        reserve = CPU_RAM_RESERVE_MIB if backend == 'cpu' else 0
        if hardware.ram_mib is None or hardware.ram_mib < profile['minimum_ram_mib'] - reserve:
            return False
        if execution_backend(profile) == 'cpu':
            return (hardware.platform == 'win32' and hardware.architecture in {'amd64', 'x86_64'}
                    and hardware.cpu_count is not None and hardware.cpu_count >= profile['cpu_threads'])
        # The launcher uses CUDA0, not the largest GPU or aggregate GPU memory.
        # Nominal GPU capacities can report slightly less due to driver reserves.
        return (bool(hardware.gpus) and hardware.gpus[0]['vram_mib'] >= profile['minimum_vram_mib'] - 128)

    def recommendations(self,hardware):
        result = []
        for profile in self.profiles():
            try: self.authorize(profile['id'],operation='install')
            except (AccessDenied,RuntimeError): continue
            result.append({'id':profile['id'],'name':profile.get('display_name', profile['id']),
                'adapter':profile.get('adapter', 'nemotron3'), 'fits':self.hardware_fit(profile, hardware),
                'execution_backend':execution_backend(profile), 'cpu_threads':profile.get('cpu_threads'),
                'ram_reserve_mib':CPU_RAM_RESERVE_MIB if execution_backend(profile) == 'cpu' else 0,
                'minimum_ram_mib':profile['minimum_ram_mib'],'minimum_vram_mib':profile['minimum_vram_mib'],
                'qualification':'Evaluation only; task quality, latency, tool compatibility and native isolation need evidence'})
        return sorted(result,key=lambda row:(not row['fits'],row['minimum_vram_mib'],row['id']))
