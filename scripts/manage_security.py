"""Local security preparation. Native mutations require explicit administrator commands.

No model, credential prompt, package download, signing key generation, policy
bypass, remote scanner, application activation or test-pass fabrication.
"""
import argparse
import base64
import hashlib
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from local_ai_appliance.asset_integrity import ordinary
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.machine_security import MachineStore,create_machine_directory,enroll_anchor,anchor
from local_ai_appliance.model import strict_json,json_bytes
from local_ai_appliance.signed_policy import verify_document,administrative_access,SignedPolicyStore
from local_ai_appliance.model_management import validate_model_policy
from local_ai_appliance.managed_deployment import ManagedDeployment,deployment_settings
from local_ai_appliance.release_readiness import verify_signed_bundle
from local_ai_appliance.security_maintenance import sbom,scan_advisories


def read(path,limit=4*1024*1024):
    if ordinary(path).st_size>limit:raise AccessDenied('Security input exceeds limit')
    return Path(path).read_bytes()


def write(path,data):
    ordinary(path.parent,directory=True)
    with path.open('xb') as output:output.write(data)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('init-machine')
    enroll=sub.add_parser('enroll-key')
    enroll.add_argument('--role',choices=('trust-anchor','release-anchor','reviewer-anchor'),required=True)
    enroll.add_argument('--public-key',type=Path,required=True);enroll.add_argument('--key-sha256',required=True)
    policy=sub.add_parser('update-model-policy');policy.add_argument('--signed-policy',type=Path,required=True)
    deployment=sub.add_parser('enroll-deployment');deployment.add_argument('--record',type=Path,required=True)
    deployment.add_argument('--candidate',action='store_true',help='Enroll a signed synthetic evaluator configuration; ordinary sessions cannot use it')
    for name in ('code-acceptance','ocr-acceptance','maintenance-review','advisory-snapshot'):
        update=sub.add_parser('update-'+name);update.add_argument('--signed-record',type=Path,required=True)
    ocr=sub.add_parser('update-ocr-policy');ocr.add_argument('--runtime',type=Path,required=True)
    ocr.add_argument('--signed-policy',type=Path,required=True)
    revoke=sub.add_parser('revoke-release');revoke.add_argument('--release-sha256',required=True)
    inventory=sub.add_parser('sbom');inventory.add_argument('--payload',type=Path,required=True)
    inventory.add_argument('--signed-manifest',type=Path,required=True)
    inventory.add_argument('--public-key',type=Path,required=True);inventory.add_argument('--key-sha256',required=True)
    inventory.add_argument('--output',type=Path,required=True)
    scan=sub.add_parser('scan');scan.add_argument('--sbom',type=Path,required=True)
    scan.add_argument('--signed-advisories',type=Path,required=True)
    scan.add_argument('--public-key',type=Path,required=True);scan.add_argument('--key-sha256',required=True)
    scan.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();store=audit_sink=audit=None
    try:
        if args.command=='sbom':
            signed=verify_signed_bundle(args.payload,read(args.signed_manifest),read(args.public_key,32),args.key_sha256)
            write(args.output,json_bytes(sbom(args.payload,signed['files'])));return 0
        if args.command=='scan':
            snapshot=verify_document(read(args.signed_advisories),read(args.public_key,32),args.key_sha256,limit=4*1024*1024)
            report=scan_advisories(strict_json(read(args.sbom)),snapshot)
            write(args.output,json_bytes(report))
            return 0 if report['coverage_complete'] and not report['findings'] else 2
        administrative_access()
        from local_ai_appliance.security_events import WindowsEventSink,SecurityAudit,identifier
        audit_sink=WindowsEventSink();audit=SecurityAudit(audit_sink)
        audit.emit('policy','attempt',object_sha256=identifier(args.command))
        if args.command=='init-machine':
            create_machine_directory()
            audit.emit('policy','success',object_sha256=identifier(args.command))
            print('Administrator-owned machine directory created; sessions remain disabled until provisioning is complete.')
            return 0
        store=MachineStore(writable=True)
        if args.command=='enroll-key':enroll_anchor(store,args.role,read(args.public_key,32),args.key_sha256)
        elif args.command=='update-model-policy':SignedPolicyStore(store).update(read(args.signed_policy),validate_model_policy)
        elif args.command=='enroll-deployment':
            record=strict_json(read(args.record,8*1024*1024));ManagedDeployment.validate_record(record)
            deployment_settings(record['settings'])
            key,digest=anchor(store,'release-anchor')
            envelope=base64.b64decode(record['release_envelope'],validate=True)
            if hashlib.sha256(envelope).hexdigest()!=record['release_sha256']:raise AccessDenied('Release digest mismatch')
            verify_signed_bundle(Path(record['release_root'])/'payload',envelope,key,digest)
            # Technical acceptance is verified here and rechecked by every launch.
            from local_ai_appliance.machine_security import technical_receipt
            import platform
            if not args.candidate:
                technical_receipt(base64.b64decode(record['technical_receipt'],validate=True),store,
                    release_sha256=record['release_sha256'],native_version=platform.version())
            store.put('evaluation-deployment' if args.candidate else 'deployment',record)
        elif args.command=='update-ocr-policy':
            from local_ai_appliance.ocr import OfflineOCR
            OfflineOCR(args.runtime,SignedPolicyStore(store)).enroll(read(args.signed_policy))
        elif args.command=='revoke-release':
            import re
            if not re.fullmatch('[a-f0-9]{64}',args.release_sha256):raise AccessDenied('Exact release digest required')
            with store.transaction():
                store.put('revoked-releases',sorted(set(store.get('revoked-releases',[])+[args.release_sha256])))
        else:
            name=args.command.removeprefix('update-')
            data=read(args.signed_record)
            key,digest=anchor(store,'reviewer-anchor');value=verify_document(data,key,digest)
            import time
            if type(value.get('expires')) not in {int,float} or value['expires']<=time.time():
                raise AccessDenied('Independent review is expired')
            with store.transaction():
                previous=store.get(name)
                if name in {'code-acceptance','ocr-acceptance'}:
                    if name=='ocr-acceptance':
                        if value.get('boundary')!='silo-lpac-managed-2':raise AccessDenied('OCR boundary is unsupported')
                        store.put(name,{'envelope':base64.b64encode(data).decode('ascii'),'sha256':hashlib.sha256(data).hexdigest()})
                        audit.emit('policy','success',object_sha256=identifier(args.command),policy_sha256=hashlib.sha256(data).hexdigest())
                        print('OCR review enrolled; exact runtime acceptance is checked on every use.')
                        return 0
                    if not isinstance(value.get('configuration'),dict):raise AccessDenied('Code configuration is missing')
                    from local_ai_appliance.windows_code_runner import qualify
                    qualify(data,hashlib.sha256(data).hexdigest(),value['configuration'],reviewer_public_key=key,reviewer_key_sha256=digest)
                    # Supersession is an explicit administrative action; no caller can replace this record.
                    store.put(name,{'envelope':base64.b64encode(data).decode('ascii'),'sha256':hashlib.sha256(data).hexdigest()})
                else:
                    if type(value.get('sequence')) is not int or value['sequence']<1 or previous and value['sequence']<=previous['sequence']:
                        raise AccessDenied('Review/advisory rollback or replay denied')
                    store.put(name,{'sequence':value['sequence'],'envelope':base64.b64encode(data).decode('ascii')})
        audit.emit('policy','success',object_sha256=identifier(args.command),
                   policy_sha256=hashlib.sha256(json_bytes(store._read())).hexdigest())
        print('Administrator security record updated. Active sessions must restart.')
        return 0
    except Exception as error:
        if audit:
            try:audit.emit('policy','failed')
            except Exception:pass
        print(str(error),file=sys.stderr);return 1
    finally:
        try:
            if store:store.close()
        finally:
            if audit_sink:audit_sink.close()


if __name__=='__main__':raise SystemExit(main())
