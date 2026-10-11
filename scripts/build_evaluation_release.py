"""Prepare reviewable source/bootstrap release assets locally. Never publishes."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from local_ai_appliance.release_bootstrap import assemble, git_snapshot, write_assets


def main():
    parser = argparse.ArgumentParser(description='Build an exact committed source release; no network or payload execution')
    parser.add_argument('--revision', required=True)
    parser.add_argument('--repository', default='adamcohen8/SILO')
    parser.add_argument('--tag', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--update-sequence', type=int, default=0, help='Increasing positive stable-channel release number; zero is manual bootstrap only')
    args = parser.parse_args()
    source = git_snapshot(ROOT, args.revision)
    assets, metadata = assemble(source, args.revision, args.repository, args.tag, update_sequence=args.update_sequence)
    write_assets(assets, args.output)
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__': main()
