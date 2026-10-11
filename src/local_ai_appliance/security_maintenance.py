"""Offline SBOM and exact-version vulnerability review. Never uploads a payload.

Advisory coverage is declared by a signed snapshot, not inferred from no hits.
No unpinned package installation, update download, or hosted scanner is invoked.
"""
from email.parser import BytesParser
import hashlib
from pathlib import Path
import re
import time

from .asset_integrity import ordinary
from .folders import AccessDenied
from .machine_security import anchor
from .model import json_bytes
from .signed_policy import verify_document,canonical


def sbom(payload, files):
    components = []
    root = Path(payload)
    for row in files:
        path = row['path']
        if path.endswith('.dist-info/METADATA'):
            metadata = root / path
            if ordinary(metadata).st_size > 512 * 1024:
                raise AccessDenied('Package metadata exceeds SBOM limit')
            data = metadata.read_bytes()
            if hashlib.sha256(data).hexdigest() != row['sha256']:
                raise AccessDenied('SBOM metadata differs from authenticated release')
            headers = BytesParser().parsebytes(data, headersonly=True)
            name, version = headers.get('Name'), headers.get('Version')
            if (not name or not version or not re.fullmatch('[A-Za-z0-9_.-]{1,150}', name)
                    or len(version) > 100):
                raise AccessDenied('Invalid dependency identity')
            components.append({'type': 'library', 'name': re.sub('[-_.]+','-',name.lower()), 'version': version,
                'bom-ref': path, 'hashes': [{'alg': 'SHA-256', 'content': row['sha256']}],
                'properties': [{'name': 'silo:metadata-path', 'value': path}]})
        elif path.endswith(('.exe', '.dll', '.pyd', '.sys', '.zip', '.whl', '.gguf', '.onnx', '.safetensors')):
            components.append({'type': 'file', 'name': Path(path).name, 'bom-ref': path,
                'hashes': [{'alg': 'SHA-256', 'content': row['sha256']}],
                'properties': [{'name': 'silo:payload-path', 'value': path}]})
    return {'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'version': 1,
            'components': sorted(components, key=lambda c: c['bom-ref'])}


def scan_advisories(bom, snapshot, *, clock=time.time):
    if (not isinstance(snapshot, dict) or set(snapshot) != {'format', 'sequence', 'expires', 'coverage', 'advisories'}
            or type(snapshot['format']) is not int or snapshot['format'] != 1 or type(snapshot['sequence']) is not int or snapshot['sequence'] < 1
            or type(snapshot['expires']) not in {int, float} or snapshot['expires'] <= clock()
            or not isinstance(snapshot['coverage'], list) or not isinstance(snapshot['advisories'], list)
            or len(snapshot['advisories']) > 100000):
        raise AccessDenied('Offline advisory snapshot is invalid or expired')
    coverage = set(snapshot['coverage'])
    if any(not isinstance(v, str) or not v for v in coverage):
        raise AccessDenied('Invalid advisory coverage')
    findings, uncovered = [], []
    versions = {(c['name'], c['version']) for c in bom['components'] if c['type'] == 'library'}
    for name in sorted({name for name,version in versions}):
        if name not in coverage: uncovered.append(name)
    for advisory in snapshot['advisories']:
        if (not isinstance(advisory, dict) or set(advisory) != {'id', 'component', 'affected_versions', 'severity'}
                or not isinstance(advisory['id'], str) or not advisory['id'] or len(advisory['id']) > 150
                or not isinstance(advisory['component'], str) or not isinstance(advisory['affected_versions'], list)
                or not all(isinstance(v, str) for v in advisory['affected_versions'])
                or advisory['severity'] not in {'low', 'moderate', 'high', 'critical'}):
            raise AccessDenied('Invalid advisory entry; ranges must be resolved to exact versions during trusted preparation')
        for name,version in sorted(versions):
            if name == advisory['component'] and version in advisory['affected_versions']:
                findings.append({'id': advisory['id'], 'component': name,
                                 'version': version, 'severity': advisory['severity']})
    return {'format': 1, 'sbom_sha256': hashlib.sha256(canonical(bom)).hexdigest(),
            'snapshot_sha256': hashlib.sha256(canonical(snapshot)).hexdigest(),
            'findings': sorted(findings, key=lambda f: (f['id'], f['component'])),
            'uncovered': sorted(uncovered), 'coverage_complete': not uncovered,
            'native_components_require_separate_review': True}


def enrolled_advisories(store, bom, *, clock=time.time):
    import base64
    record = store.get('advisory-snapshot')
    if not isinstance(record, dict) or set(record) != {'sequence', 'envelope'}:
        raise AccessDenied('Administrator must enroll a signed offline advisory snapshot')
    key, digest = anchor(store, 'reviewer-anchor')
    value = verify_document(base64.b64decode(record['envelope'], validate=True), key, digest, limit=4*1024*1024)
    report = scan_advisories(bom, value, clock=clock)
    if value['sequence'] != record['sequence'] or not report['coverage_complete'] or report['findings']:
        raise AccessDenied('Advisory coverage is incomplete or known vulnerable versions need remediation')
    return report


def maintenance_acceptance(envelope, store, bom, *, release_sha256, clock=time.time):
    key, digest = anchor(store, 'reviewer-anchor')
    value = verify_document(envelope, key, digest, limit=128 * 1024)
    if (not isinstance(value, dict) or set(value) != {'format', 'sequence', 'expires', 'release_sha256',
            'sbom_sha256', 'advisory_snapshot_sha256', 'status', 'native_components_reviewed'}
            or type(value['format']) is not int or value['format'] != 1 or type(value['sequence']) is not int or value['sequence'] < 1
            or type(value['expires']) not in {int, float} or value['expires'] <= clock()
            or value['release_sha256'] != release_sha256
            or value['sbom_sha256'] != hashlib.sha256(canonical(bom)).hexdigest()
            or value['status'] != 'accepted' or value['native_components_reviewed'] is not True
            or not isinstance(value['advisory_snapshot_sha256'], str)
            or not re.fullmatch('[a-f0-9]{64}', value['advisory_snapshot_sha256'])):
        raise AccessDenied('Release vulnerability/maintenance review is missing, changed or expired')
    report = enrolled_advisories(store, bom, clock=clock)
    if value['advisory_snapshot_sha256'] != report['snapshot_sha256']:
        raise AccessDenied('Maintenance review names a different offline advisory snapshot')
    return value
