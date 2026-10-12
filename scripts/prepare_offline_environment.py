"""Inspect/import an independently reviewed prebuilt environment without execution."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from local_ai_appliance.offline_environment import OfflineEnvironment,import_environment


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True); p.add_argument('--manifest-sha256',required=True)
    p.add_argument('--destination',type=Path); p.add_argument('--operation'); p.add_argument('--entrypoint')
    a=p.parse_args()
    if bool(a.operation)!=bool(a.entrypoint): p.error('operation and entrypoint are required together')
    e=import_environment(a.source,a.destination,a.manifest_sha256) if a.destination else OfflineEnvironment(a.source,a.manifest_sha256)
    result=e.summary()
    if a.operation: result['preview']=e.plan(a.operation,a.entrypoint)
    print(json.dumps(result,indent=2)); return 0


if __name__=='__main__': raise SystemExit(main())
