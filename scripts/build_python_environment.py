"""Assemble a new Windows offline Python environment from independently pinned inputs.

No interpreter, setup.py, pip, package hook or model is executed. License review
and native acceptance are separate administrative steps after preparation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from local_ai_appliance.asset_integrity import verify_tree,ordinary
from local_ai_appliance.evaluation_install import unpack
from local_ai_appliance.offline_environment import inventory_environment,OfflineEnvironment
from local_ai_appliance.offline_wheels import resolve_wheels
from local_ai_appliance.model import strict_json,json_bytes


def assemble(interpreter,inventory,wheels,wheel_pins,destination,requirements,identifier):
    interpreter=Path(interpreter).absolute(); destination=Path(destination).absolute()
    verify_tree(interpreter,inventory)
    resolved=resolve_wheels(wheels,wheel_pins,requirements)
    ordinary(destination.parent,directory=True); destination.mkdir(mode=0o700)
    try:
        payload=destination/'payload'; payload.mkdir()
        for p in inventory:
            target=payload/p['path']; target.parent.mkdir(parents=True,exist_ok=True)
            with (interpreter/p['path']).open('rb') as src,target.open('xb') as dst: shutil.copyfileobj(src,dst)
        library=payload/'Lib/site-packages'
        for p in resolved: unpack(Path(wheels)/p['wheel']['filename'],library,wheel=True)
        verify_tree(interpreter,inventory)
        for p in resolved:
            from local_ai_appliance.asset_integrity import digest_file
            if digest_file(Path(wheels)/p['wheel']['filename'])!=p['wheel']['sha256']: raise RuntimeError('Wheel changed during extraction')
        commands={op:{'executable':'python.exe','arguments':['-I','-S','-B','-u','{bootstrap}','{work}','{library}','{environment}',op,'{entrypoint}'],
                      'suffixes':['.py']} for op in ('run','test','check')}
        manifest=inventory_environment(destination,identifier_value=identifier,platform='windows-x64',language='python',
                    packages=[{k:v for k,v in p.items() if k!='wheel'} for p in resolved],commands=commands,
                    python_paths=['Lib/site-packages'] if resolved else [])
        data=json_bytes(manifest); (destination/'silo-environment.json').write_bytes(data)
        digest=hashlib.sha256(data).hexdigest(); env=OfflineEnvironment(destination,digest)
        return env.summary()
    except BaseException: shutil.rmtree(destination); raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--interpreter',type=Path,required=True); p.add_argument('--input-lock',type=Path,required=True)
    p.add_argument('--input-lock-sha256',required=True); p.add_argument('--wheels',type=Path,required=True)
    p.add_argument('--destination',type=Path,required=True); p.add_argument('--id',required=True)
    a=p.parse_args(); data=a.input_lock.read_bytes()
    if len(data)>1024*1024 or hashlib.sha256(data).hexdigest()!=a.input_lock_sha256: raise RuntimeError('Independent input lock mismatch')
    lock=strict_json(data)
    print(json.dumps(assemble(a.interpreter,lock['interpreter_files'],a.wheels,lock['wheels'],a.destination,lock['requirements'],a.id),indent=2))
    return 0


if __name__=='__main__': raise SystemExit(main())
