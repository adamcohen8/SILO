"""Repin an externally signed bootstrap into new local unpublished release assets."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from local_ai_appliance.asset_integrity import ordinary
from local_ai_appliance.model import strict_json
from local_ai_appliance.release_bootstrap import MAX_SOURCE, repin_bootstrap, write_assets
from local_ai_appliance.windows_folders import parts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', required=True, type=Path)
    parser.add_argument('--signed-bootstrap', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        metadata = strict_json((args.release / 'release.json').read_bytes())
        name = metadata['source_archive']['filename']
        if len(parts(name)) != 1:
            raise ValueError('Unsafe release archive name')
        assets = {}
        for filename in (name, 'release.json', 'install.ps1', 'INSTALL.md'):
            path = args.release / filename
            if ordinary(path).st_size > MAX_SOURCE:
                raise ValueError('Release asset exceeds source-only limit')
            assets[filename] = path.read_bytes()
        if ordinary(args.signed_bootstrap).st_size > MAX_SOURCE:
            raise ValueError('Signed bootstrap exceeds size bound')
        write_assets(repin_bootstrap(assets, args.signed_bootstrap.read_bytes()), args.output)
        print('Fresh pins saved to a new unpublished release. Native Authenticode verification remains required.')
        return 0
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
