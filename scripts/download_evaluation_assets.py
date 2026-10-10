"""Build an offline cache of pinned public assets; no inference or payload execution."""
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from local_ai_appliance.evaluation_install import PROFILE, obtain
from local_ai_appliance.asset_integrity import inference_pins
from local_ai_appliance.model import strict_json

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', required=True, type=Path)
    args = parser.parse_args()
    args.cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    profile = strict_json((ROOT/PROFILE).read_bytes())
    for item in [profile['python'], *profile['wheels'], *inference_pins(ROOT)['assets']]:
        obtain(item, args.cache)
