"""Reviewed install plans consume independent signatures; they never create trust.

The plan SHA-256 must come from the approved distribution channel. It binds the
initial public keys and all administrative choices, before first enrollment.
Portable validation is preparation only, never native acceptance.
"""
import base64
import copy
import hashlib
import re
import time
from pathlib import Path, PureWindowsPath

from .asset_integrity import ordinary
from .evaluation_install import installed_config
from .folders import AccessDenied
from .machine_security import anchor, technical_receipt
from .managed_deployment import deployment_settings
from .model import strict_json
from .model_management import ModelManager, validate_model_policy
from .release_readiness import verify_signed_bundle
from .security_maintenance import maintenance_acceptance, sbom
from .signed_policy import verify_document
from .windows_folders import parts

MAX_PLAN = 8 * 1024 * 1024
ROLES = {'trust-anchor', 'release-anchor', 'reviewer-anchor'}
FIELDS = {'format', 'source_id', 'release_name', 'user_sid', 'state_root',
          'model_id', 'anchors', 'model_policy', 'advisories', 'maintenance',
          'release_envelope', 'technical_receipt', 'settings'}


class Records:
    administrator_owned = True

    def __init__(self, records):
        self.records = records

    def get(self, name, default=None):
        return self.records.get(name, default)


def decode(value, limit=4 * 1024 * 1024):
    if not isinstance(value, str) or len(value) > (limit + 2) // 3 * 4:
        raise AccessDenied('Install plan contains an oversized security document')
    try:
        data = base64.b64decode(value, validate=True)
    except ValueError:
        raise AccessDenied('Install plan contains invalid base64') from None
    if len(data) > limit:
        raise AccessDenied('Install plan contains an oversized security document')
    return data


def read_plan(path, expected_sha256):
    if (not isinstance(expected_sha256, str) or not re.fullmatch('[a-f0-9]{64}', expected_sha256)
            or ordinary(path).st_size > MAX_PLAN):
        raise AccessDenied('An independently supplied install-plan digest is required')
    data = Path(path).read_bytes()
    return parse_plan(data, expected_sha256)


def parse_plan(data, expected_sha256):
    if (len(data) > MAX_PLAN or not isinstance(expected_sha256, str)
            or not re.fullmatch('[a-f0-9]{64}', expected_sha256)
            or hashlib.sha256(data).hexdigest() != expected_sha256):
        raise AccessDenied('Install plan differs from its independently supplied digest')
    value = strict_json(data)
    if (not isinstance(value, dict) or set(value) != FIELDS or type(value['format']) is not int
            or value['format'] != 1 or not isinstance(value['source_id'], str)
            or not re.fullmatch('[a-f0-9]{16}', value['source_id'])
            or not isinstance(value['release_name'], str)
            or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', value['release_name'])
            or value['release_name'].endswith('.')
            or not isinstance(value['user_sid'], str)
            or not re.fullmatch('S-1-5-21-[0-9]+-[0-9]+-[0-9]+-[0-9]+', value['user_sid'])
            or not isinstance(value['state_root'], str) or not (Path(value['state_root']).is_absolute()
                or PureWindowsPath(value['state_root']).is_absolute())
            or not isinstance(value['model_id'], str)):
        raise AccessDenied('Invalid exact-host install plan')
    # Maintainers can inspect/generate commands from a Windows plan on another
    # OS. Actual enrollment revalidates paths and storage on the target host.
    settings = deployment_settings(value['settings'], windows_paths=True)
    try:
        if len(parts(value['release_name'])) != 1:
            raise ValueError()
    except (ValueError, TypeError):
        raise AccessDenied('Unsafe Windows managed release name') from None
    # This installer provisions documents/analysis. Optional execution boundaries
    # retain their separate administrative provisioning and acceptance paths.
    if any(settings[name] for name in ('allow_code', 'allow_code_exports', 'allow_ocr', 'allow_schedules')):
        raise AccessDenied('One-command activation currently requires optional features disabled')
    if not isinstance(value['anchors'], dict) or set(value['anchors']) != ROLES:
        raise AccessDenied('Install plan requires all three independent public anchors')
    for role in ROLES:
        anchor(Records(value['anchors']), role)
    for field, limit in (('model_policy', 1024 * 1024), ('release_envelope', 4 * 1024 * 1024),
                         ('advisories', 4 * 1024 * 1024), ('maintenance', 128 * 1024),
                         ('technical_receipt', 128 * 1024)):
        if not decode(value[field], limit):
            raise AccessDenied('Install plan requires every signed approval document')
    return value


def validated_records(plan, payload, release_root, *, source_id, user_sid,
                      native_version, previous=None, clock=time.time):
    """Validate everything before touching machine state or enabling a session."""
    if plan['source_id'] != source_id or plan['user_sid'] != user_sid:
        raise AccessDenied('Install plan belongs to a different source or host account')
    payload = Path(payload)
    deployment_settings(plan['settings'])
    config = installed_config(payload / 'app')
    if (config is None or config['state_root'] != plan['state_root']
            or config.get('default_model_id') != plan['model_id']):
        raise AccessDenied('Prepared model/private state differ from the reviewed install plan')
    state = Path(plan['state_root'])
    ordinary(state, directory=True)
    if (state == payload or state in payload.parents or payload in state.parents
            or not any(Path(root) == state or Path(root) in state.parents
                       for root in plan['settings']['excluded_roots'])):
        raise AccessDenied('Private state must be outside public software and explicitly excluded from grants')
    if Path(release_root).name != plan['release_name']:
        raise AccessDenied('Managed release name differs from the reviewed install plan')
    old = previous or {}
    records = copy.deepcopy(plan['anchors'])
    for name in ROLES:
        if old.get(name) is not None and old[name] != records[name]:
            raise AccessDenied('Existing trust anchors require a separate reviewed rotation')
    overlay = Records({**old, **records})
    key, digest = anchor(overlay, 'release-anchor')
    release = decode(plan['release_envelope'])
    signed = verify_signed_bundle(payload, release, key, digest)
    release_digest = hashlib.sha256(release).hexdigest()
    if release_digest in old.get('revoked-releases', []):
        raise AccessDenied('Install plan names a revoked release')
    trust_key, trust_digest = anchor(overlay, 'trust-anchor')
    policy = verify_document(decode(plan['model_policy'], 1024 * 1024), trust_key, trust_digest)
    validate_model_policy(policy)
    reviewer_key, reviewer_digest = anchor(overlay, 'reviewer-anchor')
    for name, field, value in (
            ('active-policy', 'model_policy', policy),
            ('advisory-snapshot', 'advisories', verify_document(decode(plan['advisories']), reviewer_key,
                                                             reviewer_digest, limit=4 * 1024 * 1024)),
            ('maintenance-review', 'maintenance', verify_document(decode(plan['maintenance'], 128 * 1024),
                                                                 reviewer_key, reviewer_digest, limit=128 * 1024))):
        if (type(value.get('sequence')) is not int or value['sequence'] < 1
                or type(value.get('expires')) not in {int, float} or value['expires'] <= clock()):
            raise AccessDenied('Expired or invalid install policy/review')
        record = {'sequence': value['sequence'], 'envelope': plan[field]}
        prior = old.get(name)
        if prior is not None and record != prior and value['sequence'] <= prior['sequence']:
            raise AccessDenied('Install policy/review rollback or conflicting replay denied')
        records[name] = record
        overlay.records[name] = record
    # Authorize the specific prepared model under the supplied signed policy.
    manager = ModelManager(payload / 'app', overlay, policy_store=overlay, clock=clock,
                           model_cache=state / 'models')
    profile = manager.authorize(plan['model_id'])
    manager.verify_model(profile)
    maintenance_acceptance(decode(plan['maintenance'], 128 * 1024), overlay, sbom(payload, signed['files']),
                           release_sha256=release_digest, clock=clock)
    technical_receipt(decode(plan['technical_receipt'], 128 * 1024), overlay,
                      release_sha256=release_digest, native_version=native_version, clock=clock)
    # Validate storage now as well as on every actual session launch.
    from .data_security import StoragePolicy
    StoragePolicy(**{name: plan['settings'][name] for name in
                     ('reference_roots', 'draft_roots', 'excluded_roots', 'allow_code_exports')})
    records['deployment'] = {'format': 1, 'release_root': str(Path(release_root).absolute()),
                             'release_envelope': plan['release_envelope'], 'release_sha256': release_digest,
                             'technical_receipt': plan['technical_receipt'], 'settings': plan['settings']}
    return records


def activate(plan, release_root, store, audit, *, source_id, user_sid, native_version):
    """Only protected native provisioning calls this; exact retry is idempotent."""
    from .managed_deployment import ManagedDeployment
    release_root = Path(release_root)
    with store.transaction():
        previous = store._read()['records']
        records = validated_records(plan, release_root / 'payload', release_root,
                                    source_id=source_id, user_sid=user_sid, native_version=native_version,
                                    previous=previous)
        # Native filesystem/ACL verification precedes enrollment. No model is run.
        if not store.development:
            checker = object.__new__(ManagedDeployment)
            checker.release = release_root
            checker._protect_payload()
        changed = {name: value for name, value in records.items() if previous.get(name) != value}
        digest = records['deployment']['release_sha256']
        audit.emit('policy', 'attempt', release_sha256=digest)
        if changed:
            store.put_many(changed)
        # Audit failure after publication has an unknown outcome; an exact retry
        # revalidates current bytes/policies and can complete without replaying them.
        audit.emit('policy', 'success', release_sha256=digest)
        return {'activated': True, 'changed': bool(changed), 'release_sha256': digest,
                'model_launched': False, 'deployment_ready': False, 'cui_authorized': False}
