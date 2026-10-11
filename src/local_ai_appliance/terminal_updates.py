"""Explicit host updates from published SILO releases; never a model tool.

The evaluation trust root is HTTPS to the fixed GitHub repository API. GitHub's
asset digests authenticate release metadata and source archives. This is not an
organization-signed distribution or CUI qualification.
"""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import secrets
import subprocess
import threading
import urllib.error
import urllib.request
import zipfile

from .asset_integrity import ordinary, digest_file
from .evaluation_install import HTTPSRedirects, installed_config, unpack, verify_release
from .folders import AccessDenied
from .model import json_bytes, strict_json
from .project_store import project_data_directory
from .release_bootstrap import MAX_SOURCE, permitted

REPOSITORY = 'adamcohen8/SILO'
ORIGIN = 'profiles/release-origin.json'
MAX_ARCHIVE = 20 * 1024**2
CHECK_INTERVAL = 3600


def validate_origin(value):
    if (not isinstance(value, dict) or set(value) != {'format_version', 'repository', 'channel', 'sequence', 'tag', 'source_revision'}
            or type(value['format_version']) is not int or value['format_version'] != 1 or value['repository'] != REPOSITORY or value['channel'] != 'stable'
            or type(value['sequence']) is not int or not 0 <= value['sequence'] < 2**53
            or not isinstance(value['tag'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', value['tag'])
            or not isinstance(value['source_revision'], str) or not re.fullmatch(r'[a-f0-9]{40}', value['source_revision'])):
        raise AccessDenied('Invalid SILO release identity')
    return value


def read_origin(root):
    path = Path(root)/ORIGIN
    if not path.exists(): return None  # Reviewed source installations can enter the release channel.
    if ordinary(path).st_size > 4096: raise AccessDenied('Release identity is oversized')
    return validate_origin(strict_json(path.read_bytes()))


class ReleaseNetwork:
    def __init__(self):
        # Public release checks carry no model input, documents, cookies, tokens or proxies.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), HTTPSRedirects())

    def get(self, url, *, limit, cancel=lambda: None):
        request = urllib.request.Request(url, headers={'User-Agent': 'SILO-Updater/1', 'Accept': 'application/json'})
        data = bytearray()
        cancel()
        with self.opener.open(request, timeout=10) as response:
            if not response.url.startswith('https://') or response.status != 200:
                raise AccessDenied('Update response is not complete HTTPS')
            while True:
                cancel()
                block = getattr(response, 'read1', response.read)(min(65536, limit + 1 - len(data)))
                if not block: break
                data.extend(block)
                if len(data) > limit: raise AccessDenied('Update response exceeds its bound')
        cancel()
        return bytes(data)


@dataclass(frozen=True)
class UpdateCandidate:
    origin: dict
    archive: dict
    manifest_sha256: str
    metadata_sha256: str


def asset_pin(release, name, tag, *, limit):
    assets = release.get('assets')
    if not isinstance(assets, list) or len(assets) > 32: raise AccessDenied('Invalid release asset inventory')
    matches = [a for a in assets if isinstance(a, dict) and a.get('name') == name]
    if len(matches) != 1: raise AccessDenied('Required update asset is missing or duplicated')
    asset = matches[0]
    url = f'https://github.com/{REPOSITORY}/releases/download/{tag}/{name}'
    digest = asset.get('digest')
    if (asset.get('state') != 'uploaded' or asset.get('browser_download_url') != url
            or type(asset.get('size')) is not int or not 1 <= asset['size'] <= limit
            or not isinstance(digest, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', digest)):
        raise AccessDenied('Release asset lacks a trusted GitHub digest or valid bounds')
    return {'filename': name, 'url': url, 'size': asset['size'], 'sha256': digest[7:]}


def verify_bytes(data, pin):
    if len(data) != pin['size'] or hashlib.sha256(data).hexdigest() != pin['sha256']:
        raise AccessDenied('Update bytes differ from GitHub release digest')


def discover(current, network, *, cancel=lambda: None):
    try:
        raw = network.get(f'https://api.github.com/repos/{REPOSITORY}/releases/latest', limit=512 * 1024, cancel=cancel)
    except urllib.error.HTTPError as error:
        if error.code == 404: return None
        raise
    release = strict_json(raw)
    if not isinstance(release, dict) or release.get('draft') is not False or release.get('prerelease') is not False:
        raise AccessDenied('Only published stable releases can be installed')
    tag = release.get('tag_name')
    if not isinstance(tag, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', tag):
        raise AccessDenied('Invalid release tag')
    pin = asset_pin(release, 'release.json', tag, limit=128 * 1024)
    data = network.get(pin['url'], limit=pin['size'], cancel=cancel); verify_bytes(data, pin)
    metadata = strict_json(data)
    if not isinstance(metadata, dict) or 'update' not in metadata: return None  # Older manual bootstrap releases.
    origin = validate_origin(metadata['update'])
    if (metadata.get('format_version') != 1 or metadata.get('repository') != REPOSITORY
            or metadata.get('tag') != tag or origin['tag'] != tag
            or metadata.get('source_revision') != origin['source_revision']
            or metadata.get('evaluation_only') is not True or metadata.get('deployment_ready') is not False):
        raise AccessDenied('Release metadata identity or evaluation scope changed')
    if origin['sequence'] <= (current['sequence'] if current else 0): return None
    if current and origin['source_revision'] == current['source_revision']: return None
    filename = 'local-ai-source-'+origin['source_revision']+'.zip'
    archive = asset_pin(release, filename, tag, limit=MAX_ARCHIVE)
    if metadata.get('source_archive') != archive: raise AccessDenied('Source pin differs from GitHub asset inventory')
    manifest = metadata.get('source_manifest_sha256')
    if not isinstance(manifest, str) or not re.fullmatch(r'[a-f0-9]{64}', manifest):
        raise AccessDenied('Invalid update manifest digest')
    return UpdateCandidate(origin, archive, manifest, pin['sha256'])


def extract_source(archive, destination, candidate):
    ordinary(archive)
    with zipfile.ZipFile(archive) as stream:
        files = stream.infolist()
        if (len(files) > 4000 or sum(i.file_size for i in files) > MAX_SOURCE + 2 * 1024**2
                or any(i.file_size > 2 * 1024**2 for i in files)):
            raise AccessDenied('Source update exceeds reviewed source-only limits')
        for item in files:
            if item.filename == 'release-manifest.json': continue
            if item.is_dir(): continue
            if not item.filename.startswith('payload/'): raise AccessDenied('Unexpected source archive member')
            permitted(item.filename[len('payload/'):])
    unpack(archive, destination)
    verify_release(destination, candidate.manifest_sha256)
    source = Path(destination)/'payload'
    if read_origin(source) != candidate.origin: raise AccessDenied('Downloaded source release identity differs')
    if not (source/'scripts/install_evaluation.py').is_file(): raise AccessDenied('Update installer is missing')
    return source


def require_unsigned_update_path():
    if os.name != 'nt': return
    from .machine_security import machine_directory
    if machine_directory().exists():
        raise AccessDenied('Managed application updates require administrator-signed release enrollment')


class TerminalUpdater:
    def __init__(self, root, *, network=None, required_key=None, plain=False, scrollback=False):
        require_unsigned_update_path()
        self.root = Path(root).absolute()
        self.config = installed_config(self.root)
        if self.config is None: raise AccessDenied('Terminal updates require the standalone installation')
        self.release = self.root.parent.parent
        self.base = self.release.parent.parent
        if self.root != self.release/'payload/app' or self.release.parent.name != 'versions':
            raise AccessDenied('Invalid standalone release layout')
        self.state = Path(self.config['state_root'])
        if self.state != self.base/'state': raise AccessDenied('Updates require the installation-owned state directory')
        self.current = read_origin(self.root)
        self.network = network or ReleaseNetwork()
        self.required_key = required_key
        if required_key is not None and not re.fullmatch(r'[a-f0-9]{64}', required_key): raise AccessDenied('Invalid policy trust anchor')
        self.plain, self.scrollback = bool(plain), bool(scrollback)
        self.available = None
        self.status = 'Checking for updates'
        self.stop = threading.Event()
        self.cancel_stage = threading.Event()
        self._guard = threading.Lock()

    def checkpoint(self):
        require_unsigned_update_path()
        if self.stop.is_set(): raise AccessDenied('Update operation cancelled')

    def check(self):
        with self._guard:
            try:
                candidate = discover(self.current, self.network, cancel=self.checkpoint)
            except Exception:
                # Failed/offline checks are never represented as "up to date".
                self.status = 'Unable to check for updates'
                self.available = None
                return self.status
            self.available = candidate
            self.status = 'Update available — Ctrl+U to install' if candidate else 'No newer compatible release'
            return self.status

    def stage(self):
        with self._guard:
            self.cancel_stage.clear()
            def checkpoint():
                self.checkpoint()
                if self.cancel_stage.is_set(): raise AccessDenied('Update download cancelled')
            candidate = self.available
            if candidate is None: raise AccessDenied('No verified update available; use /update check')
            # Recheck publication/digests immediately before downloading code.
            fresh = discover(self.current, self.network, cancel=checkpoint)
            if fresh != candidate: raise AccessDenied('Release changed; check for updates again')
            root = project_data_directory(self.state, name='updates')
            job = root/('u-'+secrets.token_hex(16)); job.mkdir(mode=0o700)
            data = self.network.get(candidate.archive['url'], limit=candidate.archive['size'], cancel=checkpoint)
            verify_bytes(data, candidate.archive)
            archive = job/'source.zip'
            with archive.open('xb') as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
            source = extract_source(archive, job/'source', candidate)
            digest = (self.release/'release-manifest.sha256').read_text(encoding='ascii').strip()
            verify_release(self.release, digest)
            request = {'format_version': 1, 'origin': candidate.origin, 'archive': candidate.archive,
                'source_manifest_sha256': candidate.manifest_sha256, 'metadata_sha256': candidate.metadata_sha256,
                'previous_version': self.release.name, 'previous_manifest_sha256': digest,
                'source': str(source), 'parent_pid': os.getpid(), 'required_policy_key_sha256': self.required_key,
                'plain': self.plain, 'scrollback': self.scrollback}
            ticket = job/'request.json'
            with ticket.open('xb') as stream: stream.write(json_bytes(request)); stream.flush(); os.fsync(stream.fileno())
            checkpoint()
            return ticket

    def launch(self, ticket):
        require_unsigned_update_path()
        if os.name != 'nt': raise AccessDenied('Native Windows updater required')
        # The existing verified host starts the updater only after vault/process cleanup.
        script = self.root/'scripts/run_terminal_update.py'
        ordinary(script)
        python = self.root.parent/'host/python.exe'; ordinary(python)
        return subprocess.Popen([str(python), '-I', '-B', str(script), '--request', str(ticket)],
            cwd=self.base, creationflags=subprocess.CREATE_NEW_CONSOLE, close_fds=True)
