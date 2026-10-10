"""Fixed bootstrap target; called only after the interpreter archive is verified."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from local_ai_appliance.evaluation_install import prepare, release_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--identity-only', action='store_true')
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--state-root', type=Path)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    if args.identity_only:
        print(release_id(ROOT))
        return
    if any(v is None for v in (args.destination, args.cache, args.state_root)):
        parser.error('destination, cache and state-root are required for preparation')
    result = prepare(ROOT, args.destination, args.cache, args.state_root, offline=args.offline,
                     progress=lambda text: print(text, file=sys.stderr, flush=True))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
