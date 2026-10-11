"""Owned host continuation after Ctrl+U. Source/package bytes are reverified."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from local_ai_appliance.update_installation import install_update


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True, type=Path)
    args = parser.parse_args()
    if os.name != 'nt': parser.error('Native Windows host required')
    print('Installing the verified SILO update. Projects, settings and models are preserved.', flush=True)
    try: result = install_update(ROOT, args.request)
    except Exception as error:
        print('Update could not start: '+str(error)+'. The existing installation is still available.', flush=True)
        return 1
    print('Update installed.' if result['status'] == 'installed' else 'Update failed; inspect the private update receipt.', flush=True)
    return 0 if result['status'] == 'installed' else 1


if __name__ == '__main__': raise SystemExit(main())
