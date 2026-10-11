"""Explicit administrative policy, signing, backup and readiness operations."""
import argparse
import hashlib
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from local_ai_appliance.asset_integrity import ordinary
from local_ai_appliance.model import json_bytes, strict_json
from local_ai_appliance.project_store import LocalVault, project_data_directory
from local_ai_appliance.signed_policy import SignedPolicyStore
from local_ai_appliance.model_management import validate_model_policy, builtin_profiles, ModelManager
from local_ai_appliance.release_readiness import new_evidence, readiness, signed_bundle, verify_signed_bundle


def read(path,limit):
    if ordinary(path).st_size > limit: raise ValueError('Input exceeds limit')
    return path.read_bytes()


def write(path,data):
    ordinary(path.parent,directory=True)
    with path.open('xb') as stream: stream.write(data)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    models=sub.add_parser('models'); models.add_argument('--root',type=Path,required=True)
    for command in ('import-model', 'select-model'):
        model=sub.add_parser(command); model.add_argument('--root',type=Path,required=True)
        model.add_argument('--state',type=Path,required=True); model.add_argument('--id',required=True)
        model.add_argument('--required-policy-key-sha256')
        if command == 'import-model': model.add_argument('--file',type=Path,required=True)
    enroll=sub.add_parser('enroll-key'); enroll.add_argument('--state',type=Path,required=True)
    enroll.add_argument('--public-key',type=Path,required=True); enroll.add_argument('--key-sha256',required=True)
    update=sub.add_parser('update-policy'); update.add_argument('--state',type=Path,required=True)
    update.add_argument('--signed-policy',type=Path,required=True)
    recovery=sub.add_parser('export-recovery'); recovery.add_argument('--state',type=Path,required=True)
    recovery.add_argument('--output',type=Path,required=True)
    restore=sub.add_parser('restore-recovery'); restore.add_argument('--state',type=Path,required=True)
    restore.add_argument('--archive',type=Path,required=True)
    ocr=sub.add_parser('update-ocr-policy'); ocr.add_argument('--state',type=Path,required=True)
    ocr.add_argument('--runtime',type=Path,required=True); ocr.add_argument('--signed-policy',type=Path,required=True)
    license=sub.add_parser('license-inventory'); license.add_argument('--root',type=Path,required=True)
    license.add_argument('--output',type=Path,required=True)
    sign=sub.add_parser('sign-bundle'); sign.add_argument('--payload',type=Path,required=True)
    sign.add_argument('--version',required=True); sign.add_argument('--configuration',required=True)
    sign.add_argument('--private-key',type=Path,required=True); sign.add_argument('--output',type=Path,required=True)
    verify=sub.add_parser('verify-bundle'); verify.add_argument('--payload',type=Path,required=True)
    verify.add_argument('--signature',type=Path,required=True); verify.add_argument('--public-key',type=Path,required=True)
    verify.add_argument('--key-sha256',required=True)
    evidence=sub.add_parser('new-evidence'); evidence.add_argument('--configuration',required=True)
    evidence.add_argument('--release-sha256',required=True); evidence.add_argument('--output',type=Path,required=True)
    check=sub.add_parser('readiness'); check.add_argument('--evidence',type=Path,required=True)
    check.add_argument('--receipts',type=Path,required=True); check.add_argument('--configuration',required=True)
    check.add_argument('--release-sha256',required=True)
    check.add_argument('--reviewer-public-key',type=Path)
    check.add_argument('--reviewer-key-sha256')
    args=parser.parse_args()
    try:
        if args.command == 'models':
            print(json_bytes({'scope':'public/synthetic evaluation candidates',
                              'profiles':builtin_profiles(args.root)}).decode())
        elif args.command in {'import-model', 'select-model'}:
            import os
            with_context=LocalVault(args.state,windows_validation=os.name=='nt')
            try:
                manager=ModelManager(args.root,with_context,
                    required_key_sha256=args.required_policy_key_sha256,
                    model_cache=project_data_directory(args.state.parent,name='models'))
                if args.command == 'import-model': manager.import_model(args.id,args.file)
                else: manager.select(args.id)
            finally: with_context.close()
            print('Offline model verified and imported.' if args.command=='import-model'
                  else 'Model selected. Restart SILO to load it.')
        elif args.command in {'enroll-key','update-policy','update-ocr-policy'}:
            import os
            with_context=LocalVault(args.state,windows_validation=os.name=='nt')
            try:
                policy=SignedPolicyStore(with_context)
                if args.command=='enroll-key': policy.enroll(read(args.public_key,32),args.key_sha256)
                elif args.command=='update-policy': policy.update(read(args.signed_policy,1024*1024),validate_model_policy)
                else:
                    from local_ai_appliance.ocr import OfflineOCR
                    OfflineOCR(args.runtime,policy).enroll(read(args.signed_policy,1024*1024))
            finally: with_context.close()
            print('Administrative policy operation complete.')
        elif args.command in {'export-recovery','restore-recovery'}:
            import getpass,os
            vault=LocalVault(args.state,windows_validation=os.name=='nt')
            try:
                password=getpass.getpass('Recovery password: ')
                if args.command=='export-recovery':
                    if password!=getpass.getpass('Confirm recovery password: '):raise ValueError('Passwords differ')
                    write(args.output,vault.recovery_backup(password))
                    print('Password-protected recovery archive created; store the password separately.')
                else:
                    vault.restore_recovery(read(args.archive,64*1024*1024+54),password)
                    print('Projects restored under the new local key; schedules require reconciliation.')
            finally:vault.close()
        elif args.command=='license-inventory':
            from local_ai_appliance.licensing import license_inventory
            write(args.output,json_bytes(license_inventory(args.root)))
            print('License review inventory created; approvals remain pending.')
        elif args.command=='sign-bundle':
            write(args.output,signed_bundle(args.payload,version=args.version,configuration_id=args.configuration,
                private_key=read(args.private_key,32)))
            print('Detached signature created. Keep the public trust anchor independent of this bundle.')
        elif args.command=='verify-bundle':
            value=verify_signed_bundle(args.payload,read(args.signature,4*1024*1024),
                read(args.public_key,32),args.key_sha256)
            print(json_bytes({'verified':True,'version':value['version'],'configuration_id':value['configuration_id']}).decode())
        elif args.command=='new-evidence':
            write(args.output,json_bytes(new_evidence(args.configuration,args.release_sha256)))
            print('Evidence matrix created; every check starts pending.')
        else:
            report=readiness(strict_json(read(args.evidence,1024*1024)),args.receipts,
                configuration_id=args.configuration,release_sha256=args.release_sha256,
                reviewer_public_key=read(args.reviewer_public_key,32) if args.reviewer_public_key else None,
                reviewer_key_sha256=args.reviewer_key_sha256)
            print(json_bytes(report).decode()); return 0 if report['deployment_ready'] else 2
        return 0
    except Exception as error:
        print(str(error),file=sys.stderr); return 1

if __name__=='__main__': raise SystemExit(main())
