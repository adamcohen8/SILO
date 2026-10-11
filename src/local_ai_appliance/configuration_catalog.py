"""Pinned development allowlist, enforced by the trusted install/launch host.

This catalog permits public/synthetic document evaluation only. It is not an
administrator policy store, a signed trust anchor, or government approval.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from .asset_integrity import digest_file, ordinary
from .model import strict_json

CATALOG_PATH = 'profiles/configuration-catalog.json'
CATALOG_SHA256 = '664af867b6ac08af64a850f5fac57e9d6d92fe1203e985005f25d6a68e4a97d1'


@dataclass(frozen=True)
class Configuration:
    id: str
    status: str
    data_scopes: tuple[str, ...]
    workloads: tuple[str, ...]
    publishers: tuple[str, ...]
    jurisdictions: tuple[str, ...]
    profile_pins: tuple[tuple[str, str], ...]
    interpreter: str
    native_acceptance: str
    harness: str


@dataclass(frozen=True)
class Catalog:
    configurations: tuple[Configuration, ...]
    blocked_publishers: tuple[str, ...]
    blocked_jurisdictions: tuple[str, ...]

    def authorize(self, root, configuration_id, *, operation, data_scope='synthetic', workload='documents'):
        if operation not in {'install', 'launch'}:
            raise RuntimeError('Unknown configuration operation')
        entry = next((c for c in self.configurations if c.id == configuration_id), None)
        if workload == 'code_evaluation' and data_scope != 'synthetic':
            raise RuntimeError('Code evaluation is limited to synthetic data')
        if (entry is None or entry.status != 'evaluation_allowed' or data_scope not in entry.data_scopes
                or workload not in entry.workloads):
            raise RuntimeError('Configuration is unknown, revoked, or outside its evaluation scope')
        if (set(entry.publishers) & set(self.blocked_publishers)
                or set(entry.jurisdictions) & set(self.blocked_jurisdictions)):
            raise RuntimeError('Configuration provenance is prohibited by policy')
        for name, digest in entry.profile_pins:
            if digest_file(Path(root)/name) != digest:
                raise RuntimeError('Configuration profile changed: '+name)
        return entry


def _strings(value):
    if (not isinstance(value, list) or len(value) > 64
            or any(not isinstance(s, str) or not re.fullmatch(r'[A-Za-z0-9_./-]{1,160}', s) for s in value)
            or len(set(value)) != len(value)):
        raise RuntimeError('Invalid catalog values')
    return tuple(value)


def parse_catalog(data):
    try:
        value = strict_json(data)
        if (not isinstance(value, dict) or set(value) != {'format_version', 'authority', 'blocked_publishers',
                'blocked_jurisdictions', 'configurations'} or type(value['format_version']) is not int
                or value['format_version'] != 1 or value['authority'] != 'development_evaluation_only'):
            raise RuntimeError('Invalid evaluation catalog')
        rows = value['configurations']
        if not isinstance(rows, list) or not 1 <= len(rows) <= 32:
            raise RuntimeError('Invalid configuration catalog size')
        parsed = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != {'id', 'status', 'data_scopes', 'workloads', 'publishers',
                    'jurisdictions', 'profile_pins', 'interpreter', 'native_acceptance', 'harness'}:
                raise RuntimeError('Invalid configuration entry')
            for key in ('id', 'interpreter', 'harness'):
                if not isinstance(row[key], str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', row[key]):
                    raise RuntimeError('Invalid configuration identity')
            if row['status'] not in {'evaluation_allowed', 'revoked'} or row['native_acceptance'] not in {'pending', 'partial'}:
                raise RuntimeError('Invalid evaluation qualification')
            scopes, workloads = _strings(row['data_scopes']), _strings(row['workloads'])
            if not scopes or set(scopes) - {'public', 'synthetic'} or not workloads or set(workloads) - {'documents', 'code_evaluation'}:
                raise RuntimeError('Catalog cannot authorize CUI or an unrestricted code workload')
            publishers, jurisdictions = _strings(row['publishers']), _strings(row['jurisdictions'])
            if not publishers or not jurisdictions:
                raise RuntimeError('Provenance must be stated, including unknown values')
            pins = row['profile_pins']
            if not isinstance(pins, list) or not 1 <= len(pins) <= 8:
                raise RuntimeError('Configuration pins are required')
            seen, checked = set(), []
            for pin in pins:
                if (not isinstance(pin, dict) or set(pin) != {'path', 'sha256'} or not isinstance(pin['path'], str)
                        or not re.fullmatch(r'profiles/[a-z0-9-]+\.json', pin['path']) or pin['path'] in seen
                        or not isinstance(pin['sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', pin['sha256'])):
                    raise RuntimeError('Invalid or repeated configuration pin')
                seen.add(pin['path'])
                checked.append((pin['path'], pin['sha256']))
            parsed.append(Configuration(row['id'], row['status'], scopes, workloads, publishers, jurisdictions,
                                        tuple(checked), row['interpreter'], row['native_acceptance'], row['harness']))
        if len({c.id for c in parsed}) != len(parsed):
            raise RuntimeError('Duplicate configuration ID')
        return Catalog(tuple(parsed), _strings(value['blocked_publishers']), _strings(value['blocked_jurisdictions']))
    except (ValueError, TypeError, KeyError) as error:
        raise RuntimeError('Malformed configuration catalog') from error


def authorize_configuration(root, configuration_id, *, operation, data_scope='synthetic', workload='documents'):
    path = Path(root)/CATALOG_PATH
    if ordinary(path).st_size > 64 * 1024:
        raise RuntimeError('Configuration catalog is oversized')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != CATALOG_SHA256:
        raise RuntimeError('Configuration catalog differs from the reviewed host policy')
    return parse_catalog(data).authorize(root, configuration_id, operation=operation,
                                         data_scope=data_scope, workload=workload)
