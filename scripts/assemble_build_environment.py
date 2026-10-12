"""Inventory a pre-acquired SDK using a separately reviewed descriptor. No hooks run.

The descriptor supplies language, package closure, fixed commands, paths and pins
for every pre-acquired payload byte. License/native reviews remain separate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from local_ai_appliance.asset_integrity import verify_tree,ordinary
from local_ai_appliance.model import strict_json,json_bytes
from local_ai_appliance.offline_environment import OfflineEnvironment


def assemble(source,destination,descriptor,digest):
    data=Path(descriptor).read_bytes()
    if len(data)>1024*1024 or hashlib.sha256(data).hexdigest()!=digest: raise RuntimeError('Reviewed SDK descriptor mismatch')
    v=strict_json(data);source=Path(source).absolute();destination=Path(destination).absolute()
    verify_tree(source,v['files']);ordinary(destination.parent,directory=True);destination.mkdir(mode=0o700)
    try:
        (destination/'payload').mkdir()
        for pin in v['files']:
            target=destination/'payload'/pin['path'];target.parent.mkdir(parents=True,exist_ok=True)
            with (source/pin['path']).open('rb') as src,target.open('xb') as dst:shutil.copyfileobj(src,dst)
        # A preparer cannot assert that licensing has been independently reviewed.
        v['license_review']='pending';manifest=json_bytes(v);(destination/'silo-environment.json').write_bytes(manifest)
        result=OfflineEnvironment(destination,hashlib.sha256(manifest).hexdigest());verify_tree(source,v['files'])
        return result.summary()
    except BaseException:shutil.rmtree(destination);raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True)
    p.add_argument('--descriptor',type=Path,required=True);p.add_argument('--descriptor-sha256',required=True)
    a=p.parse_args();print(json.dumps(assemble(a.source,a.destination,a.descriptor,a.descriptor_sha256),indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
