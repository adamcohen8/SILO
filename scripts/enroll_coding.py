"""Explicit administrator enrollment of independently signed coding records.

Never generates keys or acceptance. Ordinary applications cannot write machine
policy. Exact configuration and expiry are rechecked during every operation.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
import time
from contextlib import closing
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from local_ai_appliance.machine_security import MachineStore,anchor
from local_ai_appliance.signed_policy import verify_document
from local_ai_appliance.offline_environment import OfflineEnvironment,identifier
from local_ai_appliance.folders import AccessDenied


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind',choices=('environment','build','repository-apply','git-host','git-runtime','language-service'),required=True)
    p.add_argument('--signed-record',type=Path,required=True)
    a=p.parse_args();data=a.signed_record.read_bytes()
    if len(data)>1024*1024:raise AccessDenied('Signed coding record oversized')
    with closing(MachineStore(writable=True)) as store:
        key,digest=anchor(store,'reviewer-anchor');value=verify_document(data,key,digest,limit=1024*1024)
        import math
        if type(value.get('expires')) not in (int,float) or not math.isfinite(value['expires']) or value['expires']<=time.time():
            raise AccessDenied('Independent coding review is expired')
        if a.kind=='environment':
            if set(value)!={'format','scope','environments','expires'} or value['format']!=1 or value['scope']!='offline-environments':
                raise AccessDenied('Invalid environment registry review')
            environments=value['environments']
            if not isinstance(environments,dict) or not environments or len(environments)>16:raise AccessDenied('Invalid environment registry')
            for name,r in environments.items():
                identifier(name)
                if set(r)!={'root','sha256'}:raise AccessDenied('Invalid environment registration')
                env=OfflineEnvironment(r['root'],r['sha256'])
                if env.value['id']!=name or env.value['license_review']!='reviewed' or env.value['platform']!='windows-x64':
                    raise AccessDenied('Reviewed Windows environment identity required')
                # Every runtime byte needs protected administrator ownership.
                from local_ai_appliance.windows_container import AppContainer
                with AppContainer(evaluation=True) as container:
                    container.allow_managed_read(env.root,directory=True)
                    container.allow_managed_read(env.root/'silo-environment.json')
                    container.allow_managed_read(env.root/'payload',directory=True)
                    for pin in env.value['files']:container.allow_managed_read(env.root/'payload'/pin['path'])
            store.put('build-environments',environments)
            store.put('build-environments-review',{'envelope':base64.b64encode(data).decode(),'sha256':hashlib.sha256(data).hexdigest()})
        elif a.kind=='build':
            from local_ai_appliance.windows_build_runner import qualify_build
            qualify_build(data,hashlib.sha256(data).hexdigest(),value['configuration'],key=key,key_digest=digest)
            env_id=identifier(value['configuration']['environment_id'])
            store.put('build-acceptance-'+env_id,{'envelope':base64.b64encode(data).decode(),'sha256':hashlib.sha256(data).hexdigest()})
        elif a.kind=='git-runtime':
            if set(value)!={'format','scope','runtime','expires'} or value['format']!=1 or value['scope']!='git-host-runtime':
                raise AccessDenied('Invalid Git runtime review')
            from local_ai_appliance.asset_integrity import digest_file
            if set(value['runtime'])!={'path','sha256'} or digest_file(value['runtime']['path'])!=value['runtime']['sha256']:
                raise AccessDenied('Git runtime pin mismatch')
            store.put('git-host-runtime',value['runtime'])
        else:
            if value.get('scope')!=a.kind:raise AccessDenied('Coding capability scope mismatch')
            store.put(a.kind+'-acceptance',{'envelope':base64.b64encode(data).decode(),'sha256':hashlib.sha256(data).hexdigest()})
    print('Independent record enrolled; every operation still validates its exact release, configuration and native evidence.')
    return 0


if __name__=='__main__':raise SystemExit(main())
