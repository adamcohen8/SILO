"""Signed release verification and evidence-bound deployment readiness."""
import hashlib
import re
from pathlib import Path

from .asset_integrity import ordinary, digest_file, verify_tree
from .folders import AccessDenied
from .model import json_bytes
from .signed_policy import sign_document, verify_document

CHECKS = ('fresh_install','offline_install','retry','repair','rollback','network_ipv4','network_ipv6',
    'network_dns','network_proxy','network_loopback','network_vpn','filesystem_reference',
    'filesystem_ungranted','filesystem_links','filesystem_registry','code_disk_quota',
    'code_memory_limit','code_deadline','child_process_denial','cancellation_cleanup',
    'crash_cleanup','reboot','sleep_resume','resource_exhaustion','runtime_drift',
    'model_quality_documents','model_quality_coding','model_tool_compatibility',
    'model_latency_memory','office_render_docx','office_render_xlsx','office_render_pptx',
    'project_backup_restore','project_retention','authenticode_bootstrap',
    'bundle_signature','license_redistribution','organization_authorization')


def inventory(root):
    root = Path(root); ordinary(root,directory=True)
    rows=[]
    for path in sorted(root.rglob('*')):
        ordinary(path,directory=path.is_dir())
        if path.is_file():
            if len(rows) >= 10000: raise AccessDenied('Release inventory is oversized')
            rows.append({'path':path.relative_to(root).as_posix(),'size':path.stat().st_size,'sha256':digest_file(path)})
    return rows


def signed_bundle(root,*,version,configuration_id,private_key):
    if not isinstance(version,str) or not re.fullmatch(r'\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?',version):
        raise AccessDenied('Use a semantic release version')
    if not isinstance(configuration_id,str) or not re.fullmatch(r'[a-z0-9-]{1,100}',configuration_id):
        raise AccessDenied('Invalid release configuration')
    return sign_document({'format':1,'version':version,'configuration_id':configuration_id,
        'files':inventory(root)},private_key)


def verify_signed_bundle(root,envelope,public_key,expected_key_sha256):
    value = verify_document(envelope,public_key,expected_key_sha256,limit=4*1024*1024)
    if not isinstance(value,dict) or set(value) != {'format','version','configuration_id','files'} or value['format'] != 1:
        raise AccessDenied('Invalid signed release manifest')
    verify_tree(Path(root),value['files'])
    return value


def new_evidence(configuration_id,release_sha256):
    if not re.fullmatch(r'[a-f0-9]{64}',release_sha256): raise AccessDenied('Exact release digest required')
    return {'format':1,'configuration_id':configuration_id,'release_sha256':release_sha256,
            'checks':{name:{'status':'pending','receipt':None,'sha256':None} for name in CHECKS}}


def readiness(value,receipt_root,*,configuration_id,release_sha256,reviewer_public_key=None,reviewer_key_sha256=None):
    if (not isinstance(value,dict) or set(value) != {'format','configuration_id','release_sha256','checks'}
            or value['format'] != 1 or value['configuration_id'] != configuration_id
            or value['release_sha256'] != release_sha256 or set(value['checks']) != set(CHECKS)):
        raise AccessDenied('Acceptance evidence must bind the exact release and complete matrix')
    pending=[]
    for name,row in value['checks'].items():
        if not isinstance(row,dict) or set(row) != {'status','receipt','sha256'} or row['status'] not in {'pending','pass','fail','skip'}:
            raise AccessDenied('Invalid acceptance entry')
        if row['status'] != 'pass': pending.append(name); continue
        from .windows_folders import parts
        try: parts(row['receipt'])
        except (ValueError,TypeError): raise AccessDenied('Invalid evidence receipt path') from None
        path=Path(receipt_root)/row['receipt']
        if not re.fullmatch(r'[a-f0-9]{64}',row['sha256']) or digest_file(path) != row['sha256']:
            raise AccessDenied('Acceptance receipt bytes changed')
        # The collector binds configuration/release; independent review remains necessary.
        if ordinary(path).st_size > 64*1024: raise AccessDenied('Evidence receipt is oversized')
        if reviewer_public_key is None or reviewer_key_sha256 is None:
            raise AccessDenied('Passed evidence requires an independently trusted reviewer signature')
        receipt = verify_document(path.read_bytes(),reviewer_public_key,reviewer_key_sha256,limit=64*1024)
        if (receipt.get('check') != name or receipt.get('configuration_id') != configuration_id
                or receipt.get('release_sha256') != release_sha256 or receipt.get('status') != 'pass'
                or name not in {'bundle_signature','license_redistribution','organization_authorization'} and receipt.get('native') is not True
                or receipt.get('reviewed') is not True
                or not isinstance(receipt.get('reviewer'),str) or not receipt['reviewer'].strip()):
            raise AccessDenied('Receipt lacks native evidence and independent review binding')
    return {'deployment_ready':not pending,'pending':pending,'passed':len(CHECKS)-len(pending),
            'required':len(CHECKS),'evidence_sha256':hashlib.sha256(json_bytes(value)).hexdigest()}
