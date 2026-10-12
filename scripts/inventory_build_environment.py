"""Create a reviewable descriptor for a pre-acquired offline SDK; never execute it.

Package closure/provenance are independently supplied review inputs. Actual
payload files are inventoried; commands come only from fixed language adapters.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from local_ai_appliance.asset_integrity import ordinary
from local_ai_appliance.build_profiles import fixed_commands
from local_ai_appliance.offline_environment import inventory_environment
from local_ai_appliance.model import json_bytes,strict_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--id',required=True);p.add_argument('--language',choices=('python','javascript','typescript','rust','cpp'),required=True)
    p.add_argument('--executable',required=True);p.add_argument('--compiler');p.add_argument('--driver')
    p.add_argument('--vendored',action='store_true');p.add_argument('--path',action='append',default=[])
    p.add_argument('--python-path',action='append',default=[])
    p.add_argument('--packages',type=Path,required=True);p.add_argument('--packages-sha256',required=True)
    a=p.parse_args();data=a.packages.read_bytes()
    if len(data)>1024*1024 or hashlib.sha256(data).hexdigest()!=a.packages_sha256:raise RuntimeError('Reviewed package inventory changed')
    packages=strict_json(data);ordinary(a.source,directory=True);ordinary(a.output.absolute().parent,directory=True)
    # inventory_environment expects payload/; assemble copies that exact tree.
    v=inventory_environment(a.source,identifier_value=a.id,platform='windows-x64',language=a.language,packages=packages,
        commands=fixed_commands(a.language,executable=a.executable,compiler=a.compiler,driver=a.driver,vendored=a.vendored),
        paths=a.path,python_paths=a.python_path)
    result=json_bytes(v)
    with a.output.open('xb') as f:f.write(result)
    print(json.dumps({'descriptor_sha256':hashlib.sha256(result).hexdigest(),'license_review':'pending','execution_enabled':False},indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
