"""Stage the pinned Windows x64 CPU archive offline; never execute its payload."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from local_ai_appliance.runtime_preparation import prepare_cpu_runtime


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    args = parser.parse_args(arguments)
    prepare_cpu_runtime(ROOT, args.archive)
    print('Pinned CPU runtime staged. Native model and containment acceptance remain pending.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
