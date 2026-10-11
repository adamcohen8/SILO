"""Create a pending native security matrix. Never signs or marks checks passed."""
import argparse
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from local_ai_appliance.machine_security import TECHNICAL_CHECKS
from local_ai_appliance.model import json_bytes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-sha256',required=True)
    parser.add_argument('--native-version',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not re.fullmatch('[a-f0-9]{64}',args.release_sha256):parser.error('Exact signed release-envelope SHA-256 required')
    value={'format':1,'release_sha256':args.release_sha256,'native_version':args.native_version,
        'boundary':'silo-lpac-managed-2','expires':0,
        'checks':{name:{'status':'pending','evidence_sha256':None} for name in sorted(TECHNICAL_CHECKS)}}
    with args.output.open('xb') as stream:stream.write(json_bytes(value))
    print('Pending technical matrix written. Separate native observations and independent review are required.')


if __name__=='__main__':main()
