"""Verify/import inert offline toolchain bundles; never download or run a package."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from local_ai_appliance.toolchains import ToolchainBundle, import_bundle


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--manifest-sha256',required=True,help='Independent reviewed manifest digest')
    parser.add_argument('--destination',type=Path,help='New directory for verified offline import')
    parser.add_argument('--command',help='Preview one fixed command, without execution')
    parser.add_argument('--entrypoint',help='Workspace-relative entrypoint for preview')
    args=parser.parse_args()
    if bool(args.command)!=bool(args.entrypoint):parser.error('--command and --entrypoint are required together')
    bundle=import_bundle(args.source,args.destination,args.manifest_sha256) if args.destination else ToolchainBundle(args.source,args.manifest_sha256)
    result={'manifest_sha256':bundle.digest,'platform':bundle.value['platform'],
            'license_review':bundle.value['license_review'],'execution_enabled':False,
            'commands':list(bundle.value['commands'])}
    if args.command:
        from dataclasses import asdict
        result['command_preview']=asdict(bundle.plan(args.command,args.entrypoint))
    print(json.dumps(result,indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
