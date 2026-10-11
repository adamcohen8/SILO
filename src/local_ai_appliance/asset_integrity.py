"""Complete pinned inference verification; downloaded inventories are not trust anchors."""
import hashlib
import json
import os
from pathlib import Path
import stat

from .model import strict_json
from .windows_folders import parts

INFERENCE_LOCK_SHA256 = '35339d83085d7a0ce78dbd58f4051f776412a30948aa51aa9eb2b686e995abd9'


def ordinary(path, *, directory=False):
    path = Path(path).absolute()
    for ancestor in (path, *path.parents):
        info = ancestor.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x441400:
            raise RuntimeError('Software storage contains a link, reparse point or recalled file.')
    info = path.lstat()
    if (directory and not stat.S_ISDIR(info.st_mode) or
            not directory and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1)):
        raise RuntimeError('Software storage contains an unsupported object.')
    return info


def digest_file(path, cancel=lambda: None):
    before = ordinary(path)
    # Windows path stat and descriptor stat can disagree on deprecated ctime:
    # one reports creation, the other metadata change. Compare birthtime for
    # identity, and separately retain descriptor ctime to detect changes.
    def fingerprint(value):
        timestamp = value.st_birthtime_ns if os.name == 'nt' else value.st_ctime_ns
        return (value.st_dev, value.st_ino, value.st_size, value.st_nlink,
                value.st_mtime_ns, timestamp)
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        opened = os.fstat(stream.fileno())
        if fingerprint(opened) != fingerprint(before):
            raise RuntimeError('Software identity changed during verification.')
        while block := stream.read(8 * 1024 * 1024):
            cancel()
            digest.update(block)
        finished = os.fstat(stream.fileno())
        if (fingerprint(finished) != fingerprint(opened)
                or finished.st_ctime_ns != opened.st_ctime_ns):
            raise RuntimeError('Software changed during verification.')
    after = ordinary(path)
    # Compare path metadata with path metadata, never with descriptor ctime.
    # A final same-size write with restored mtime must not lose this guard.
    if (fingerprint(after) != fingerprint(before)
            or after.st_ctime_ns != before.st_ctime_ns):
        raise RuntimeError('Software identity changed after verification.')
    return digest.hexdigest()


def entries(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 10000:
        raise RuntimeError('A complete, nonempty software inventory is required.')
    result = {}
    for item in value:
        if not isinstance(item, dict) or set(item) != {'path', 'size', 'sha256'}:
            raise RuntimeError('Invalid software inventory entry.')
        try:
            parts(item['path'])
        except (ValueError, TypeError):
            raise RuntimeError('Unsafe software inventory path.') from None
        key = item['path'].casefold()
        if (key in result or type(item['size']) is not int or item['size'] < 0 or
                not isinstance(item['sha256'], str) or len(item['sha256']) != 64 or
                any(c not in '0123456789abcdef' for c in item['sha256'])):
            raise RuntimeError('Invalid or duplicate software inventory entry.')
        result[key] = item
    return result


def verify_tree(root, expected, cancel=lambda: None):
    expected = entries(expected)
    ordinary(root, directory=True)
    seen = set()
    directories = {'/'.join(e['path'].split('/')[:i]).casefold()
                   for e in expected.values() for i in range(1, len(e['path'].split('/')))}
    for directory, children, files in os.walk(root, followlinks=False):
        for name in children:
            path = Path(directory)/name
            ordinary(path, directory=True)
            if path.relative_to(root).as_posix().casefold() not in directories:
                raise RuntimeError('Undeclared software directory found.')
        for name in files:
            cancel()
            path = Path(directory)/name
            relative = path.relative_to(root).as_posix()
            key = relative.casefold()
            if key in seen or key not in expected or expected[key]['path'] != relative:
                raise RuntimeError('Undeclared or aliased software file found.')
            item = expected[key]
            if ordinary(path).st_size != item['size'] or digest_file(path, cancel) != item['sha256']:
                raise RuntimeError('Software size or SHA-256 verification failed.')
            seen.add(key)
    if seen != set(expected):
        raise RuntimeError('Software inventory is incomplete.')


def inference_pins(root):
    path = Path(root)/'profiles/nemotron-30b-4090-assets.json'
    if ordinary(path).st_size > 1024 * 1024:
        raise RuntimeError('The reviewed inference lock is oversized.')
    value = strict_json(path.read_bytes())
    canonical = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')
    if hashlib.sha256(canonical).hexdigest() != INFERENCE_LOCK_SHA256:
        raise RuntimeError('The reviewed inference lock has changed.')
    return value


def verify_inference(root, cancel=lambda: None):
    root = Path(root)
    expected = inference_pins(root)
    profile = strict_json((root/'profiles/nemotron-30b-4090-candidate.json').read_bytes())
    lock = strict_json((root/'artifacts/inference/verified-assets.json').read_bytes())
    if (lock.get('profile_id') != expected['profile_id'] or
            lock.get('runtime_source_revision') != expected['runtime_source_revision'] or
            profile['profile_id'] != expected['profile_id'] or
            profile['runtime']['source_revision'] != expected['runtime_source_revision']):
        raise RuntimeError('Prepared assets do not match the reviewed inference profile.')
    pinned = entries(expected['extracted_runtime'])
    if entries(lock.get('extracted_runtime')) != pinned or 'llama-server.exe' not in pinned:
        raise RuntimeError('Prepared runtime inventory differs from the complete reviewed lock.')
    runtime = root/'artifacts/inference/runtime-b11433-cuda12.4'
    verify_tree(runtime, list(pinned.values()), cancel)
    model_pin = next(a for a in expected['assets'] if a['role'] == 'model')
    model = profile['model']
    if (model['file'], model['size'], model['sha256']) != (model_pin['name'], model_pin['size'], model_pin['sha256']):
        raise RuntimeError('Model profile differs from the reviewed model pin.')
    path = root/'artifacts/inference/downloads'/model_pin['name']
    from .evaluation_install import installed_config
    installation = installed_config(root)
    if installation is not None:
        managed = Path(installation['state_root'])/'models'/(model_pin['sha256']+'.gguf')
        if managed.exists(): path = managed
    if ordinary(path).st_size != model_pin['size'] or digest_file(path, cancel) != model_pin['sha256']:
        raise RuntimeError('Model verification failed.')
    return runtime, path
