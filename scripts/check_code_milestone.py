"""Independently inspect a published synthetic milestone ZIP; no code execution."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from local_ai_appliance.milestone import inspect_milestone


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifact_zip',type=Path)
    args=parser.parse_args()
    if args.artifact_zip.stat().st_size>1024*1024: raise RuntimeError('Artifact set exceeds its bounded size')
    result=inspect_milestone(args.artifact_zip.read_bytes(),ROOT/'tests/fixtures/silo-milestone')
    print(json.dumps(result,indent=2))
if __name__=='__main__': main()
