"""Build an offline cache of pinned public assets; no inference or payload execution."""
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from local_ai_appliance.evaluation_install import PROFILE, obtain
from local_ai_appliance.asset_integrity import inference_pins, cpu_runtime_pins
from local_ai_appliance.model import strict_json

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', required=True, type=Path)
    parser.add_argument('--cpu-runtime-only', action='store_true',
                        help='Prepare only the pinned Windows x64 CPU archive; no model weights')
    args = parser.parse_args()
    args.cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    profile = strict_json((ROOT/PROFILE).read_bytes())
    assets = cpu_runtime_pins(ROOT)['assets']
    if not args.cpu_runtime_only:
        assets = [profile['python'], *profile['wheels'], *inference_pins(ROOT)['assets'], *assets]
    for item in assets:
        obtain(item, args.cache)
