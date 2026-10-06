"""Offline installation framework: plan/private stage/checkpoint/rollback only.

No payload is executed, no feature/firewall/service is changed, and no state
can declare deployment readiness. Production activation awaits signed assets
and native GPU/isolation/functional evidence.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

from .bundle import BundleError, MANIFEST_NAME
from .install_store import Store
from .model import strict_json
from .payloads import Payloads

GATES = ('signed_bundle', 'windows_folder_qualification', 'parser_containment',
         'gpu_inference', 'tool_calling_and_citations', 'network_isolation',
         'host_connectivity', 'reboot_resume_isolation', 'installer_native_validation')
PHASES = {'planned', 'staging', 'staged', 'awaiting_reboot', 'pending_validation', 'failed', 'rolled_back'}


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def result(manifest, phase, **extra):
    return {'format_version': 1, 'bundle_id': manifest.bundle_id, 'phase': phase,
            'payload_execution_performed': False, 'deployment_ready': False,
            'remaining_gates': list(GATES), **extra}


def journal(store, transaction, digest):
    names = store.names(transaction + '/journal')
    previous, latest = None, None
    for index, name in enumerate(names, 1):
        if name != f'{index:06d}.json': raise BundleError('Installation journal sequence is invalid')
        data = store.read(transaction + '/journal/' + name, 8192)
        value = strict_json(data)
        if (not isinstance(value, dict) or set(value) != {'format_version', 'sequence', 'manifest_sha256', 'previous_sha256', 'phase', 'boot_id'}
                or type(value['format_version']) is not int or value['format_version'] != 1
                or type(value['sequence']) is not int or value['sequence'] != index
                or value['manifest_sha256'] != digest or value['previous_sha256'] != previous
                or value['phase'] not in PHASES
                or (value['boot_id'] is not None and (not isinstance(value['boot_id'], str)
                    or not re.fullmatch(r'[0-9TZ:._+-]{1,64}', value['boot_id'])))):
            raise BundleError('Installation journal is malformed or has changed')
        latest, previous = value, hashlib.sha256(data).hexdigest()
    return latest, previous, len(names)


def checkpoint(store, transaction, digest, phase, *, boot_id=None):
    _, previous, count = journal(store, transaction, digest)
    value = {'format_version': 1, 'sequence': count + 1, 'manifest_sha256': digest,
             'previous_sha256': previous, 'phase': phase, 'boot_id': boot_id}
    store.write(transaction + f'/journal/{count + 1:06d}.json', lambda write: write(encode(value)))
    return value


def verify_staged(path, digest, windows_validation):
    with Payloads(path, digest, windows_validation=windows_validation) as payloads:
        for artifact in payloads.manifest.artifacts: payloads.copy(artifact, lambda _: None)


def operate(action, bundle, digest, *, state_root=None, development=False,
            windows_validation=False, boot_id=None):
    if action not in {'plan', 'stage', 'status', 'pause-for-reboot', 'resume', 'rollback'}:
        raise BundleError('Unknown installation operation')
    if action != 'plan' and not development:
        raise BundleError('Mutations/status require explicit development validation mode; production activation is unavailable')
    if action in {'pause-for-reboot', 'resume'} and (not isinstance(boot_id, str) or not re.fullmatch(r'[0-9TZ:._+-]{1,64}', boot_id)):
        raise BundleError('A trusted host boot timestamp is required')
    with Payloads(bundle, digest, windows_validation=windows_validation) as payloads:
        manifest = payloads.manifest
        if action == 'plan':
            for artifact in manifest.artifacts: payloads.copy(artifact, lambda _: None)
            return result(manifest, 'planned', manifest_sha256=digest,
                          payload_integrity_verified=True, signature_verified=False,
                          payload_bytes=sum(a.size for a in manifest.artifacts),
                          steps=['inventory', 'prerequisites_pending', 'protected_staging',
                                 'reboot_checkpoint_if_needed', 'native_validation_pending', 'activation_blocked'])
        if state_root is None: raise BundleError('Select private installation state storage')
        state_root = Path(state_root).absolute()
        transaction = 'tx-' + digest
        stage_path = state_root / transaction / 'payload'
        with Store(state_root, windows_validation=windows_validation) as store, store.lock():
            if transaction not in store.names():
                if action != 'stage': raise BundleError('No matching installation transaction exists')
                store.mkdir(transaction); store.mkdir(transaction + '/journal')
                checkpoint(store, transaction, digest, 'planned')
            state, _, _ = journal(store, transaction, digest)
            if state is None: raise BundleError('Installation transaction requires recovery inspection')
            phase = state['phase']
            if action == 'status':
                return result(manifest, phase, manifest_sha256=digest, checkpoint_valid=True)
            if action == 'stage':
                if phase in {'staged', 'pending_validation'}:
                    verify_staged(stage_path, digest, windows_validation)
                    return result(manifest, phase, idempotent=True, payload_integrity_verified=True)
                if phase not in {'planned', 'rolled_back'}:
                    raise BundleError('Inspect/resume or roll back this transaction before staging again')
                required = sum(a.size for a in manifest.artifacts) + len(payloads.manifest_data) + 64 * 1024 * 1024
                if shutil.disk_usage(state_root).free < required: raise BundleError('Insufficient space for private staging')
                store.mkdir(transaction + '/payload')
                checkpoint(store, transaction, digest, 'staging')
                try:
                    store.write(transaction + '/payload/' + MANIFEST_NAME, lambda write: write(payloads.manifest_data))
                    directories = sorted({'/'.join(a.path.split('/')[:end]) for a in manifest.artifacts
                                          for end in range(1, len(a.path.split('/')))}, key=lambda p: (p.count('/'), p))
                    for directory in directories: store.mkdir(transaction + '/payload/' + directory)
                    for artifact in manifest.artifacts:
                        store.write(transaction + '/payload/' + artifact.path,
                                    lambda write, item=artifact: payloads.copy(item, write))
                    verify_staged(stage_path, digest, windows_validation)
                    checkpoint(store, transaction, digest, 'staged')
                except Exception:
                    checkpoint(store, transaction, digest, 'failed')
                    raise
                return result(manifest, 'staged', payload_integrity_verified=True, signature_verified=False)
            if action == 'pause-for-reboot':
                if phase != 'staged': raise BundleError('Only verified staging can wait for a reboot')
                verify_staged(stage_path, digest, windows_validation)
                checkpoint(store, transaction, digest, 'awaiting_reboot', boot_id=boot_id)
                return result(manifest, 'awaiting_reboot', reboot_performed=False)
            if action == 'resume':
                if phase != 'awaiting_reboot' or state['boot_id'] == boot_id:
                    raise BundleError('Resume requires the recorded reboot checkpoint and a changed host boot timestamp')
                verify_staged(stage_path, digest, windows_validation)
                checkpoint(store, transaction, digest, 'pending_validation', boot_id=boot_id)
                return result(manifest, 'pending_validation', prerequisite_recheck_required=True)
            if phase == 'rolled_back': return result(manifest, phase, idempotent=True)
            # Conservative rollback: verify the expected files present, reject
            # any unowned/modified content, then remove only declared payloads.
            prefix = transaction + '/payload'
            expected = {a.path: a for a in manifest.artifacts}
            directories = {'/'.join(path.split('/')[:end]) for path in expected
                           for end in range(1, len(path.split('/')))}
            present_files, present_directories = [], []
            def inventory(path=''):
                for name in store.names(prefix + ('/' + path if path else '')):
                    relative = (path + '/' if path else '') + name
                    if relative in directories:
                        present_directories.append(relative); inventory(relative)
                    elif relative in expected or relative == MANIFEST_NAME: present_files.append(relative)
                    else: raise BundleError('Rollback refused: unowned content exists in staging')
            if 'payload' in store.names(transaction):
                inventory()
                for path in present_files:
                    if path == MANIFEST_NAME:
                        if store.read(prefix + '/' + path) != payloads.manifest_data:
                            raise BundleError('Rollback refused: staged manifest changed')
                    else:
                        artifact = expected[path]
                        store.verify_file(prefix + '/' + path, artifact.size, artifact.sha256)
                for path in present_files: store.remove(prefix + '/' + path)
                for path in sorted(present_directories, key=lambda p: p.count('/'), reverse=True):
                    store.remove(prefix + '/' + path, directory=True)
                store.remove(prefix, directory=True)
            checkpoint(store, transaction, digest, 'rolled_back')
            return result(manifest, 'rolled_back', journal_retained=True, unrelated_settings_changed=False)


def main():
    parser = argparse.ArgumentParser(description='Offline installation framework; production activation is blocked')
    parser.add_argument('action', choices=['plan', 'stage', 'status', 'pause-for-reboot', 'resume', 'rollback'])
    parser.add_argument('--bundle', required=True); parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--state-root'); parser.add_argument('--development', action='store_true')
    parser.add_argument('--windows-validation', action='store_true'); parser.add_argument('--boot-id')
    args = parser.parse_args()
    try:
        value = operate(args.action, args.bundle, args.manifest_sha256, state_root=args.state_root,
                        development=args.development, windows_validation=args.windows_validation, boot_id=args.boot_id)
        print(json.dumps(value, indent=2)); return 0
    except (BundleError, OSError, ValueError) as e:
        print(json.dumps({'operation_failed': True, 'deployment_ready': False,
                          'reason': str(e) if isinstance(e, BundleError) else 'Storage or validation operation failed'})); return 1


if __name__ == '__main__': raise SystemExit(main())
