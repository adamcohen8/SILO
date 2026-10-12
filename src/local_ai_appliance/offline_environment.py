"""Exact offline environment inventories and dependency closure. No package execution.

Prepared environments include runtimes, dependencies and notices. Their manifest
digest is supplied by independent review. A manifest is never execution approval.
"""
import hashlib
import re
from pathlib import Path
from .asset_integrity import digest_file, ordinary, verify_tree, entries
from .folders import AccessDenied
from .model import strict_json, json_bytes
from .windows_folders import parts

LANGUAGES = {'python','javascript','typescript','rust','cpp'}
OPERATIONS = {'run','test','check','build','lsp'}


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch('[a-z][a-z0-9_-]{0,47}',value):
        raise AccessDenied('Invalid environment or operation identifier')
    return value


class OfflineEnvironment:
    def __init__(self,root,expected_sha256):
        self.root=Path(root).absolute(); self.digest=expected_sha256
        if not isinstance(expected_sha256,str) or not re.fullmatch('[0-9a-f]{64}',expected_sha256):
            raise AccessDenied('An independently reviewed environment digest is required')
        path=self.root/'silo-environment.json'
        if ordinary(path).st_size>1024*1024: raise AccessDenied('Environment manifest is oversized')
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=expected_sha256: raise AccessDenied('Environment manifest changed')
        v=strict_json(data)
        if (not isinstance(v,dict) or set(v)!={'format','id','platform','language','files','packages','commands','paths','python_paths','license_review'}
                or type(v['format']) is not int or v['format']!=1 or v['language'] not in LANGUAGES
                or v['platform'] not in {'windows-x64','linux-x64','macos-arm64'}
                or v['license_review'] not in {'pending','reviewed'}):
            raise AccessDenied('Invalid offline environment manifest')
        identifier(v['id']); pins=entries(v['files'])
        if not isinstance(v['packages'],list) or len(v['packages'])>1000: raise AccessDenied('Invalid package closure')
        packages={}
        for p in v['packages']:
            if (not isinstance(p,dict) or set(p)!={'name','version','license','source','requires'}
                    or not all(isinstance(p[k],str) and 0<len(p[k])<=1024 for k in ('name','version','license','source'))
                    or not isinstance(p['requires'],dict) or len(p['requires'])>1000):
                raise AccessDenied('Every package needs version, provenance, license and exact dependency pins')
            key=p['name'].casefold()
            if key in packages: raise AccessDenied('Duplicate package identity')
            packages[key]=p
        for p in packages.values():
            for name,version in p['requires'].items():
                if not isinstance(name,str) or name.casefold() not in packages or packages[name.casefold()]['version']!=version:
                    raise AccessDenied('Offline dependency closure is incomplete or conflicting')
        directories={'/'.join(p['path'].split('/')[:i]) for p in pins.values() for i in range(1,len(p['path'].split('/')))}
        for key in ('paths','python_paths'):
            if not isinstance(v[key],list) or len(v[key])>32: raise AccessDenied('Invalid environment search paths')
            for p in v[key]:
                parts(p)
                if p not in directories: raise AccessDenied('Environment paths must be inventoried payload directories')
        if not isinstance(v['commands'],dict) or not v['commands'] or len(v['commands'])>16:
            raise AccessDenied('Invalid fixed command registry')
        for name,c in v['commands'].items():
            identifier(name)
            if (name not in OPERATIONS or not isinstance(c,dict) or set(c)!={'executable','arguments','suffixes'}
                    or c['executable'].casefold() not in pins or pins[c['executable'].casefold()]['path']!=c['executable']
                    or not isinstance(c['arguments'],list) or len(c['arguments'])>64
                    or not all(isinstance(a,str) and len(a)<=2048 and '\x00' not in a for a in c['arguments'])
                    or c['arguments'].count('{entrypoint}')!=(0 if name=='lsp' else 1)
                    or not isinstance(c['suffixes'],list) or not c['suffixes']
                    or not all(isinstance(s,str) and re.fullmatch(r'\.[a-z0-9]+',s) for s in c['suffixes'])):
                raise AccessDenied('Commands must name pinned executables and one literal entrypoint slot')
        self.value=v; self.verify()

    def verify(self):
        if digest_file(self.root/'silo-environment.json')!=self.digest: raise AccessDenied('Environment manifest drift')
        verify_tree(self.root/'payload',self.value['files'])

    def plan(self,operation,entrypoint):
        from .code_workspace import code_path
        code_path(entrypoint); self.verify()
        c=self.value['commands'].get(operation)
        if c is None or Path(entrypoint).suffix not in c['suffixes']:
            raise AccessDenied('Operation or entrypoint is unavailable in this environment')
        return {'environment_sha256':self.digest,'operation':operation,'language':self.value['language'],
                'executable':c['executable'],'arguments':['./'+entrypoint if a=='{entrypoint}' else a for a in c['arguments']],
                'network':'deny','execution_enabled':False}

    def summary(self):
        return {'id':self.value['id'],'language':self.value['language'],'platform':self.value['platform'],
                'sha256':self.digest,'packages':self.value['packages'],'operations':list(self.value['commands']),
                'license_review':self.value['license_review'],'execution_enabled':False}


def import_environment(source,destination,expected_sha256):
    """Import into a new directory; rehash both sides, never run install hooks."""
    import shutil
    env=OfflineEnvironment(source,expected_sha256); destination=Path(destination).absolute()
    ordinary(destination.parent,directory=True); destination.mkdir(mode=0o700)
    try:
        (destination/'payload').mkdir(mode=0o700)
        for p in env.value['files']:
            target=destination/'payload'/p['path']; target.parent.mkdir(parents=True,exist_ok=True)
            with (env.root/'payload'/p['path']).open('rb') as src,target.open('xb') as dst:
                shutil.copyfileobj(src,dst,1024*1024)
        (destination/'silo-environment.json').write_bytes((env.root/'silo-environment.json').read_bytes())
        result=OfflineEnvironment(destination,expected_sha256); env.verify(); return result
    except BaseException:
        shutil.rmtree(destination); raise


def inventory_environment(root,*,identifier_value,platform,language,packages,commands,paths=(),python_paths=()):
    from .release_readiness import inventory
    return {'format':1,'id':identifier_value,'platform':platform,'language':language,
            'files':inventory(Path(root)/'payload'),'packages':packages,'commands':commands,
            'paths':list(paths),'python_paths':list(python_paths),'license_review':'pending'}
