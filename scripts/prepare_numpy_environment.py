"""Prepare the pinned NumPy environment. Online acquisition is explicit; no code runs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from local_ai_appliance.asset_integrity import ordinary
from local_ai_appliance.evaluation_install import obtain,unpack,copy_pinned
from local_ai_appliance.model import strict_json
from local_ai_appliance.release_readiness import inventory
from build_python_environment import assemble


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile',type=Path,default=Path(__file__).resolve().parents[1]/'profiles/windows-python-numpy-build.json')
    p.add_argument('--profile-sha256',required=True);p.add_argument('--cache',type=Path,required=True)
    p.add_argument('--destination',type=Path,required=True);p.add_argument('--online',action='store_true')
    a=p.parse_args();data=a.profile.read_bytes()
    if len(data)>1024*1024 or hashlib.sha256(data).hexdigest()!=a.profile_sha256: raise RuntimeError('Reviewed preparation profile mismatch')
    v=strict_json(data);ordinary(a.cache,directory=True);ordinary(a.destination.absolute().parent,directory=True)
    if a.destination.exists(): raise RuntimeError('Select a new environment directory')
    with tempfile.TemporaryDirectory(prefix='silo-environment-stage-',dir=a.destination.absolute().parent) as tmp:
        stage=Path(tmp)
        assets=[v['python'],*v['wheels']]
        for pin in assets:
            original=obtain(pin,a.cache,offline=not a.online)
            copy_pinned(original,stage/pin['filename'],pin)
        runtime=stage/'interpreter';unpack(stage/v['python']['filename'],runtime)
        result=assemble(runtime,inventory(runtime),stage,
            [{k:pin[k] for k in ('filename','size','sha256','source')} for pin in v['wheels']],
            a.destination,v['requirements'],v['id'])
    print(json.dumps(result,indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
