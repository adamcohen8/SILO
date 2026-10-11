"""Build an offline cache of pinned public assets; no inference or payload execution."""
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from local_ai_appliance.evaluation_install import PROFILE, obtain
from local_ai_appliance.asset_integrity import inference_pins, cpu_runtime_pins
from local_ai_appliance.model import strict_json
from local_ai_appliance.model_management import builtin_profiles, model_download_assets
from local_ai_appliance.configuration_catalog import authorize_configuration


def selected_model_assets(root, identifier):
    authorize_configuration(root, identifier, operation='install')
    profile = next((p for p in builtin_profiles(root) if p['id'] == identifier), None)
    if profile is None:
        raise ValueError('Unknown pinned evaluation model')
    return model_download_assets(profile)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', required=True, type=Path)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--cpu-runtime-only', action='store_true',
                        help='Prepare only the pinned Windows x64 CPU archive; no model weights')
    selection.add_argument('--model-id', help='Prepare only the exact pinned weight set for this evaluation profile')
    args = parser.parse_args()
    args.cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    profile = strict_json((ROOT/PROFILE).read_bytes())
    assets = (selected_model_assets(ROOT, args.model_id) if args.model_id
              else cpu_runtime_pins(ROOT)['assets'])
    if not args.cpu_runtime_only and not args.model_id:
        assets = [profile['python'], *profile['wheels'], *inference_pins(ROOT)['assets'], *assets]
    for item in assets:
        obtain(item, args.cache)
