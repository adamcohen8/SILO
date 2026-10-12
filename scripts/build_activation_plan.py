"""Assemble already signed approval material for one exact host. No signing keys."""
import argparse
import base64
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from local_ai_appliance.evaluation_install import installed_config
from local_ai_appliance.managed_installation import parse_plan, validated_records
from local_ai_appliance.model import json_bytes
from local_ai_appliance.asset_integrity import ordinary


def read(path, limit=4 * 1024 * 1024):
    if ordinary(path).st_size > limit:
        raise ValueError('Approval input exceeds its bounded size')
    return Path(path).read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared-root', required=True, type=Path)
    parser.add_argument('--source-id', required=True)
    parser.add_argument('--release-name', required=True)
    parser.add_argument('--user-sid', required=True)
    parser.add_argument('--native-version', required=True, help='Exact target platform.version(), bound by the signed receipt')
    parser.add_argument('--settings', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    for role in ('trust', 'release', 'reviewer'):
        parser.add_argument('--' + role + '-key', required=True, type=Path)
        parser.add_argument('--' + role + '-key-sha256', required=True)
    for field in ('model-policy', 'advisories', 'maintenance', 'release-envelope', 'technical-receipt'):
        parser.add_argument('--' + field, required=True, type=Path)
    args = parser.parse_args()
    try:
        from local_ai_appliance.model import strict_json
        config = installed_config(args.prepared_root / 'payload' / 'app')
        if config is None or 'default_model_id' not in config:
            raise ValueError('An exact prepared model/state configuration is required')
        value = {'format': 1, 'source_id': args.source_id, 'release_name': args.release_name,
                 'user_sid': args.user_sid, 'state_root': config['state_root'], 'model_id': config['default_model_id'],
                 'settings': strict_json(read(args.settings, 64 * 1024)), 'anchors': {}}
        for role in ('trust', 'release', 'reviewer'):
            key = read(getattr(args, role + '_key'), 32)
            value['anchors'][role + '-anchor'] = {'key': base64.b64encode(key).decode('ascii'),
                                                'sha256': getattr(args, role + '_key_sha256')}
        for field in ('model_policy', 'advisories', 'maintenance', 'release_envelope', 'technical_receipt'):
            value[field] = base64.b64encode(read(getattr(args, field))).decode('ascii')
        data = json_bytes(value)
        digest = hashlib.sha256(data).hexdigest()
        plan = parse_plan(data, digest)
        # This is preparation on the host whose existing storage/settings were
        # reviewed. It does not create or claim the signed native observations.
        validated_records(plan, args.prepared_root / 'payload', args.prepared_root.parent / args.release_name,
                          source_id=args.source_id, user_sid=args.user_sid, native_version=args.native_version)
        ordinary(args.output.parent, directory=True)
        with args.output.open('xb') as stream:
            stream.write(data)
        print(json_bytes({'plan_sha256': digest, 'bytes': len(data), 'published': False,
                          'activated': False, 'native_validation_performed': False}).decode())
        return 0
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
