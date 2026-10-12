"""Pinned evaluation preparation. Host downloads precede all AI worker launches.

This creates an application-local interpreter and fixed wheel trees, without
running pip, wheel setup hooks, or a downloaded setup program. Evaluation trust
starts with the reviewed source; signed distribution and CUI acceptance are separate.
"""
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import stat
import tempfile
import urllib.request
import zipfile

from .asset_integrity import (digest_file, entries, inference_pins, ordinary, verify_tree,
                              cpu_runtime_pins, CPU_RUNTIME_PATH, CPU_RUNTIME_DIRECTORY)
from .model import strict_json
from .windows_folders import parts
from .configuration_catalog import authorize_configuration

PROFILE = 'profiles/windows-evaluation-installer.json'
MAX_EXPANSION = 2 * 1024**3


class HTTPSRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        if not url.startswith('https://'):
            raise RuntimeError('A download attempted to redirect outside HTTPS.')
        return super().redirect_request(request, response, code, message, headers, url)


def asset(item):
    if not isinstance(item, dict):
        raise RuntimeError('Invalid download pin.')
    filename = item.get('filename', item.get('name'))
    if len(parts(filename)) != 1:
        raise RuntimeError('Downloads require a single safe filename.')
    entries([{'path': filename, 'size': item['size'], 'sha256': item['sha256']}])
    if item['size'] <= 0 or not item['url'].startswith('https://'):
        raise RuntimeError('Downloads require HTTPS and a positive pinned size.')
    return filename


def verify_download(path, item):
    if ordinary(path).st_size != item['size'] or digest_file(path) != item['sha256']:
        raise RuntimeError('Cached or downloaded asset differs from its reviewed pin: '+asset(item))


def copy_pinned(source, destination, item):
    """Check the bytes actually copied from a potentially shared cache.

    Callers supply a new file in their private transaction. Cache verification
    alone cannot authorize bytes read later from a mutable cache pathname.
    """
    asset(item)
    ordinary(source)
    ordinary(Path(destination).parent, directory=True)
    digest, count = hashlib.sha256(), 0
    with Path(source).open('rb') as incoming, Path(destination).open('xb') as outgoing:
        while block := incoming.read(8 * 1024 * 1024):
            count += len(block)
            if count > item['size']:
                raise RuntimeError('Cached asset grew while copying into private staging.')
            digest.update(block)
            outgoing.write(block)
        outgoing.flush()
        os.fsync(outgoing.fileno())
    if count != item['size'] or digest.hexdigest() != item['sha256']:
        raise RuntimeError('Cached asset changed before its private copy was verified.')
    verify_download(destination, item)


def obtain(item, cache, *, offline=False, progress=print):
    name = asset(item)
    destination = Path(cache)/name
    if destination.exists():
        verify_download(destination, item)
        return destination
    if offline:
        raise RuntimeError('Offline cache is missing '+name)
    partial = destination.with_name(name+'.partial')
    offset = ordinary(partial).st_size if partial.exists() else 0
    if offset > item['size']:
        raise RuntimeError('Oversized partial download; inspect the cache before retrying.')
    if offset < item['size']:
        headers = {'User-Agent': 'LocalAI-Evaluation-Installer/1'}
        if offset:
            headers['Range'] = f'bytes={offset}-'
        request = urllib.request.Request(item['url'], headers=headers)
        opener = urllib.request.build_opener(HTTPSRedirects())
        with opener.open(request, timeout=30) as response:
            if not response.url.startswith('https://'):
                raise RuntimeError('A download redirected outside HTTPS.')
            if offset and (response.status != 206 or not response.headers.get('Content-Range', '').startswith(f'bytes {offset}-')):
                raise RuntimeError('The server did not honor download resumption.')
            progress('Downloading '+name)
            with partial.open('ab' if partial.exists() else 'xb') as out:
                while block := response.read(8 * 1024 * 1024):
                    offset += len(block)
                    if offset > item['size']:
                        raise RuntimeError('Download exceeded the pinned size.')
                    out.write(block)
                out.flush()
                os.fsync(out.fileno())
    verify_download(partial, item)
    # Never replace a concurrently published cache entry.
    if destination.exists():
        verify_download(destination, item)
        partial.unlink()
    else:
        partial.rename(destination)
    return destination


def unpack(archive, destination, *, wheel=False):
    """Reject links, aliases, escapes, executable wheel hooks and oversized expansion."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    ordinary(destination, directory=True)
    seen = set()
    with zipfile.ZipFile(archive) as stream:
        items = stream.infolist()
        if len(items) > 10000 or sum(i.file_size for i in items) > MAX_EXPANSION:
            raise RuntimeError('Archive expansion exceeds its limits.')
        for item in items:
            name = item.filename.rstrip('/')
            components = parts(name)
            mode = item.external_attr >> 16
            if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise RuntimeError('Archive links and special files are forbidden.')
            if wheel and components[0].endswith('.data'):
                if len(components) >= 3 and components[1] == 'scripts':
                    # jsonpatch/jsonpointer ship CLI wrappers. This application
                    # vendors their libraries and deliberately installs no CLI.
                    continue
                if len(components) < 3 or components[1] not in {'purelib', 'platlib'}:
                    raise RuntimeError('Wheel installation hooks/data schemes are unsupported.')
                components = components[2:]
            relative = '/'.join(components)
            if relative.casefold() in seen:
                raise RuntimeError('Archive aliases or duplicate entries are forbidden.')
            seen.add(relative.casefold())
            target = destination.joinpath(*components)
            if wheel and target.suffix.lower() == '.pth':
                raise RuntimeError('Executable wheel path hooks are forbidden.')
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                ordinary(target, directory=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            ordinary(target.parent, directory=True)
            if target.exists():
                raise RuntimeError('Archive extraction would replace an existing file.')
            with stream.open(item) as source, target.open('xb') as out:
                count = 0
                while block := source.read(1024 * 1024):
                    count += len(block)
                    if count > item.file_size:
                        raise RuntimeError('Archive entry grew during extraction.')
                    out.write(block)
                if count != item.file_size:
                    raise RuntimeError('Archive entry has an unexpected size.')


def source_files(source):
    source = Path(source)
    names = ['AGENTS.md', 'Start-LocalAI.cmd', PROFILE,
             'assets/branding/silo.png', 'assets/branding/silo.ico',
             'profiles/nemotron-30b-4090-assets.json', 'profiles/nemotron-30b-4090-candidate.json',
             'profiles/configuration-catalog.json', 'profiles/windows-python312-wheels.json',
             'tests/synthetic_documents.py']
    if (source/'profiles/windows-python-numpy-build.json').is_file(): names.append('profiles/windows-python-numpy-build.json')
    if (source/'profiles/model-catalog.json').is_file(): names.append('profiles/model-catalog.json')
    if (source/'profiles/release-origin.json').is_file(): names.append('profiles/release-origin.json')
    if (source/CPU_RUNTIME_PATH).is_file(): names.append(CPU_RUNTIME_PATH)
    if (source/'Start-SILO-Terminal.cmd').is_file(): names.append('Start-SILO-Terminal.cmd')
    fixture_root=source/'tests/fixtures/silo-milestone'
    names += [p.relative_to(source).as_posix() for p in sorted(fixture_root.glob('*')) if p.is_file()]
    for directory, pattern in [('src/local_ai_appliance', '*.py'), ('scripts', '*.py'), ('installer', '*.ps1')]:
        names += [p.relative_to(source).as_posix() for p in sorted((source/directory).glob(pattern))]
    if not (source/'src/local_ai_appliance/evaluation_install.py').is_file():
        raise RuntimeError('Select the complete reviewed installer source.')
    return [{'path': name, 'size': ordinary(source/name).st_size, 'sha256': digest_file(source/name)}
            for name in sorted(names)]


def release_id(source):
    return hashlib.sha256(json.dumps(source_files(source), sort_keys=True).encode()).hexdigest()[:16]


def inventory(root):
    result = []
    for path in sorted(Path(root).rglob('*')):
        if path.is_dir():
            ordinary(path, directory=True)
        else:
            result.append({'path': path.relative_to(root).as_posix(), 'size': ordinary(path).st_size,
                           'sha256': digest_file(path)})
    entries(result)
    return result


def verify_release(root, expected_sha256):
    root = Path(root)
    manifest = root/'release-manifest.json'
    if digest_file(manifest) != expected_sha256:
        raise RuntimeError('Installed evaluation manifest changed.')
    value = strict_json(manifest.read_bytes())
    if (set(value) != {'format_version', 'evaluation_only', 'deployment_ready', 'files'} or
            value['format_version'] != 1 or value['evaluation_only'] is not True or value['deployment_ready'] is not False):
        raise RuntimeError('Invalid evaluation release manifest.')
    # Manifest lives beside the fully enumerated payload directory.
    verify_tree(root/'payload', value['files'])
    return value


def prepare(source, destination, cache, state_root, *, offline=False, progress=print, include_model=True, model_id=None):
    source, destination, cache, state_root = map(Path, (source, destination, cache, state_root))
    ordinary(source, directory=True)
    ordinary(destination, directory=True)
    ordinary(cache, directory=True)
    ordinary(state_root, directory=True)
    if any(destination.iterdir()):
        raise RuntimeError('Preparation requires a new, empty transaction directory.')
    source_snapshot = source_files(source)
    authorize_configuration(source, 'nemotron-4090-cp314-evaluation-1', operation='install')
    profile = strict_json((source/PROFILE).read_bytes())
    if profile['format_version'] != 1 or profile['evaluation_only'] is not True or profile['deployment_ready'] is not False:
        raise RuntimeError('An explicit evaluation profile is required.')
    inference = inference_pins(source)
    from .model_management import (DEFAULT, builtin_profiles, hardware_mismatches,
                                  model_download_assets, preparation_default, scan_hardware)
    if model_id is not None and not include_model:
        raise RuntimeError('Application updates preserve selection; do not supply a model override')
    if model_id is not None:
        authorize_configuration(source, model_id, operation='install')
        chosen = next((p for p in builtin_profiles(source) if p['id'] == model_id), None)
        if chosen is None: raise RuntimeError('Unknown pinned preparation model')
        reasons = hardware_mismatches(chosen, scan_hardware())
        if reasons: raise RuntimeError('Selected preparation model does not fit: '+'; '.join(reasons))
    default_model_id = model_id if model_id is not None else (preparation_default(source) if include_model else DEFAULT)
    if include_model and default_model_id is None:
        raise RuntimeError('No compatible pinned model for the detected hardware. Check RAM, first NVIDIA GPU and Windows x64; no model was downloaded')
    assets = [a for a in inference['assets'] if include_model or a['role'] != 'model']
    if include_model and default_model_id != DEFAULT:
        authorize_configuration(source, default_model_id, operation='install')
        selected = next(p for p in builtin_profiles(source) if p['id'] == default_model_id)
        assets = [a for a in assets if a['role'] != 'model'] + [
            dict(item, role='model') for item in model_download_assets(selected)]
        progress('Preparing '+selected['display_name']+' as the default model.')
    cpu = cpu_runtime_pins(source) if (source/CPU_RUNTIME_PATH).is_file() else None
    downloads = [profile['python'], *profile['wheels'], *assets,
                 *(cpu['assets'] if cpu else [])]
    names = [asset(item).casefold() for item in downloads]
    if len(names) != len(set(names)):
        raise RuntimeError('Duplicate download pins.')
    missing = sum(item['size'] for item in downloads if not (cache/asset(item)).exists())
    # Model remains in the resumable cache and in the installation. Extraction
    # and the host/worker interpreters also need independent storage.
    required = missing + sum(item['size'] for item in downloads) + 4 * 1024**3
    if shutil.disk_usage(destination).free < required:
        raise RuntimeError('Insufficient free space for the cache and installed evaluation.')
    paths = {asset(item): obtain(item, cache, offline=offline, progress=progress) for item in downloads}
    payload = destination/'payload'
    app, host, worker, code_sdk = payload/'app', payload/'host', payload/'worker', payload/'code'
    for entry in source_snapshot:
        target = app/entry['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source/entry['path'], target)
        if digest_file(target) != entry['sha256']:
            raise RuntimeError('Source changed while preparing the installation.')
    with tempfile.TemporaryDirectory(dir=destination, prefix='.verified-archives-') as staging:
        staging = Path(staging)
        interpreter = staging/asset(profile['python'])
        copy_pinned(paths[interpreter.name], interpreter, profile['python'])
        for sdk in (host, worker, code_sdk):
            unpack(interpreter, sdk)
            python_paths = list(sdk.glob('python*._pth'))
            if len(python_paths) != 1:
                raise RuntimeError('Unexpected embedded Python path configuration.')
            stem = python_paths[0].stem
            # Application-managed vendoring, rather than pip into embedded Python.
            paths_text=stem+'.zip\n.\n'
            if sdk!=code_sdk: paths_text+='Lib/site-packages\nimport site\n'
            python_paths[0].write_bytes(paths_text.encode('ascii'))
        for item in profile['wheels']:
            archive = staging/asset(item)
            copy_pinned(paths[archive.name], archive, item)
            unpack(archive, host/'Lib/site-packages', wheel=True)
            if not item['ui_only']:
                unpack(archive, worker/'Lib/site-packages', wheel=True)
            archive.unlink()
    shutil.copytree(app/'src/local_ai_appliance', worker/'Lib/site-packages/local_ai_appliance')
    shutil.copyfile(app/'scripts/contained_agent_worker.py', worker/'contained_agent_worker.py')
    runtime = app/'artifacts/inference/runtime-b11433-cuda12.4'
    runtime.mkdir(parents=True)
    for item in assets:
        if item['role'] == 'runtime':
            with tempfile.TemporaryDirectory(dir=destination, prefix='.verified-archives-') as staging:
                archive = Path(staging)/item['name']
                copy_pinned(paths[item['name']], archive, item)
                unpack(archive, runtime)
        else:
            # Weights are independently pinned mutable assets, outside the complete
            # immutable code/runtime payload. Removing a model cannot invalidate it.
            from .project_store import project_data_directory
            models = project_data_directory(state_root, name='models')
            model = models/(item['sha256']+'.gguf')
            if model.exists():
                verify_download(model, item)
            else:
                if shutil.disk_usage(models).free < item['size'] + 256 * 1024**2:
                    raise RuntimeError('Insufficient free space in private model storage.')
                with tempfile.TemporaryDirectory(dir=models, prefix='.prepare-model-') as staging:
                    private = Path(staging)/item['name']
                    copy_pinned(paths[item['name']], private, item)
                    try: os.link(private, model)
                    except FileExistsError: verify_download(model, item)
    verify_tree(runtime, inference['extracted_runtime'])
    if cpu:
        cpu_runtime = app/CPU_RUNTIME_DIRECTORY
        cpu_runtime.mkdir(parents=True)
        for item in cpu['assets']:
            with tempfile.TemporaryDirectory(dir=destination, prefix='.verified-archives-') as staging:
                archive = Path(staging)/item['name']
                copy_pinned(paths[item['name']], archive, item)
                unpack(archive, cpu_runtime)
        verify_tree(cpu_runtime, cpu['extracted_runtime'])
    (app/'artifacts/inference/verified-assets.json').write_text(json.dumps(inference, indent=2)+'\n')
    config = {'format_version': 1, 'evaluation_only': True, 'state_root': str(state_root.absolute()),
              'worker': '../worker', 'qualification': 'evaluation_only_full_isolation_and_CUI_acceptance_pending'}
    if include_model:
        config['default_model_id'] = default_model_id
    (app/'evaluation-installation.json').write_text(json.dumps(config, indent=2)+'\n')
    if source_files(source) != source_snapshot:
        raise RuntimeError('Source changed during preparation; the transaction was not published.')
    files = inventory(payload)
    data = json.dumps({'format_version': 1, 'evaluation_only': True, 'deployment_ready': False,
                       'files': files}, sort_keys=True, indent=2).encode('ascii')+b'\n'
    manifest = destination/'release-manifest.json'
    manifest.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    verify_release(destination, digest)
    (destination/'release-manifest.sha256').write_text(digest+'\n', encoding='ascii')
    return {'evaluation_only': True, 'deployment_ready': False, 'manifest_sha256': digest,
            'release_id': release_id(source), 'files': len(files), 'native_acceptance': 'not_run',
            'prepared_default_model_id': default_model_id if include_model else None}


def installed_config(app):
    path = Path(app)/'evaluation-installation.json'
    if not path.exists():
        return None
    if ordinary(path).st_size > 4096:
        raise RuntimeError('Installed evaluation configuration is oversized.')
    config = strict_json(path.read_bytes())
    required = {'format_version', 'evaluation_only', 'state_root', 'worker', 'qualification'}
    if (not isinstance(config, dict) or not required <= set(config) or set(config) - required - {'default_model_id'} or
            config['format_version'] != 1 or config['evaluation_only'] is not True or
            config['worker'] != '../worker' or not isinstance(config['state_root'], str) or
            not Path(config['state_root']).is_absolute()):
        raise RuntimeError('Invalid installed evaluation configuration.')
    if ('default_model_id' in config and (not isinstance(config['default_model_id'], str)
            or not re.fullmatch(r'[a-z0-9-]{1,64}', config['default_model_id']))):
        raise RuntimeError('Invalid installed default model.')
    ordinary(config['state_root'], directory=True)
    return config
