"""Validate/enroll an independently reviewed install plan. Never signs or runs a model."""
import argparse
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from local_ai_appliance.managed_installation import read_plan, validated_records, activate
from local_ai_appliance.machine_security import MachineStore, machine_directory, release_directory
from local_ai_appliance.model import json_bytes
from local_ai_appliance.signed_policy import administrative_access


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--prepared-root', type=Path, required=True)
    parser.add_argument('--source-id', required=True)
    parser.add_argument('--user-sid', required=True)
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    store = sink = None
    try:
        administrative_access()
        plan = read_plan(args.plan, args.plan_sha256)
        release = release_directory() / plan['release_name']
        if machine_directory().exists():
            store = MachineStore(writable=not args.validate_only)
        if args.validate_only:
            validated_records(plan, args.prepared_root / 'payload', release,
                              source_id=args.source_id, user_sid=args.user_sid,
                              native_version=platform.version(), previous=store._read()['records'] if store else {})
            print('Install plan, payload, signatures and exact-host acceptance verified; no enrollment changed.')
            return 0
        if store is None or args.prepared_root.absolute() != release.absolute():
            raise ValueError('Activation requires the protected exact release and machine store')
        from local_ai_appliance.security_events import WindowsEventSink, SecurityAudit
        sink = WindowsEventSink()
        result = activate(plan, release, store, SecurityAudit(sink), source_id=args.source_id,
                          user_sid=args.user_sid, native_version=platform.version())
        print(json_bytes(result).decode())
        return 0
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        try:
            if store: store.close()
        finally:
            if sink: sink.close()


if __name__ == '__main__':
    raise SystemExit(main())
