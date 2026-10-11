"""Side-by-side update transaction, run by the existing verified Windows host."""
from contextlib import contextmanager
import ctypes as C
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile

from .asset_integrity import ordinary, digest_file
from .evaluation_install import installed_config, verify_release
from .folders import AccessDenied
from .model import json_bytes, strict_json
from .terminal_updates import UpdateCandidate, ReleaseNetwork, discover, read_origin, validate_origin


def bounded_json(path, limit=128 * 1024):
    if ordinary(path).st_size > limit: raise AccessDenied('Update record is oversized')
    return strict_json(Path(path).read_bytes())


@contextmanager
def exclusive_lock(path):
    """Same Windows share-denied lock used by the PowerShell installer."""
    if os.name != 'nt': raise AccessDenied('Native Windows update transaction required')
    ordinary(Path(path).parent, directory=True)
    if Path(path).exists(): ordinary(path)
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [C.c_wchar_p, C.c_uint32, C.c_uint32, C.c_void_p, C.c_uint32, C.c_uint32, C.c_void_p]
    kernel.CreateFileW.restype = C.c_void_p
    kernel.CloseHandle.argtypes = [C.c_void_p]; kernel.CloseHandle.restype = C.c_int
    handle = kernel.CreateFileW(str(path), 0xc0000000, 0, None, 4, 0x00200080, None)
    if handle in {None, C.c_void_p(-1).value}: raise AccessDenied('Another installation or session is running')
    try:
        from .windows_native import NativeFiles
        info = NativeFiles().info(handle)
        if not info.disk or info.directory or info.reparse or info.offline or info.links != 1:
            raise AccessDenied('Update lock is not an ordinary local file')
        yield
    finally: kernel.CloseHandle(handle)


def wait_for_parent(pid, *, timeout=300):
    if os.name != 'nt' or type(pid) is not int or pid <= 0 or pid == os.getpid():
        raise AccessDenied('Invalid Windows update parent')
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [C.c_uint32, C.c_int, C.c_uint32]; kernel.OpenProcess.restype = C.c_void_p
    kernel.WaitForSingleObject.argtypes = [C.c_void_p, C.c_uint32]; kernel.WaitForSingleObject.restype = C.c_uint32
    kernel.CloseHandle.argtypes = [C.c_void_p]; kernel.CloseHandle.restype = C.c_int
    handle = kernel.OpenProcess(0x100000, False, pid)
    if not handle:
        if C.get_last_error() == 87: return  # Original process has already exited.
        raise AccessDenied('Unable to verify that SILO exited')
    try:
        if kernel.WaitForSingleObject(handle, timeout * 1000) != 0:
            raise AccessDenied('SILO did not exit; update was not installed')
    finally: kernel.CloseHandle(handle)


def atomic_write(path, data):
    path = Path(path); ordinary(path.parent, directory=True)
    if path.exists(): ordinary(path)
    descriptor, temporary = tempfile.mkstemp(prefix='.update-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally: Path(temporary).unlink(missing_ok=True)


def launchers(record):
    version, digest = record['version'], record['manifest_sha256']
    if not re.fullmatch(r'[a-f0-9]{16}-[a-f0-9]{8}', version) or not re.fullmatch(r'[a-f0-9]{64}', digest):
        raise AccessDenied('Invalid update activation identity')
    gui = ('@echo off\r\nsetlocal DisableDelayedExpansion\r\n'
           f'powershell.exe -NoProfile -File "%~dp0versions\\{version}\\payload\\app\\installer\\Start-Evaluation.ps1" '
           f'-InstallationRoot "%~dp0versions\\{version}" -ManifestSha256 "{digest}"\r\nif errorlevel 1 pause\r\n')
    terminal = ('@echo off\r\nsetlocal DisableDelayedExpansion\r\n'
                f'"%~dp0versions\\{version}\\payload\\host\\python.exe" -I -B '
                f'"%~dp0versions\\{version}\\payload\\app\\scripts\\start_windows_terminal.py" %*\r\n')
    return {'Start-LocalAI.cmd': gui.encode('ascii'), 'Start-SILO-Terminal.cmd': terminal.encode('ascii')}


def activation_snapshot(base):
    result = {}
    for name in ('active.json', 'active.previous.json', 'Start-LocalAI.cmd', 'Start-SILO-Terminal.cmd'):
        path = base/name
        if path.exists():
            if ordinary(path).st_size > 16384: raise AccessDenied('Installed launcher or active record is oversized')
            result[name] = path.read_bytes()
        else: result[name] = None
    return result


def restore_activation(base, snapshot):
    for name, data in snapshot.items():
        path = base/name
        if data is None:
            if path.exists(): ordinary(path); path.unlink()
        else: atomic_write(path, data)


def activate(base, record, previous):
    atomic_write(base/'active.previous.json', previous)
    for name, data in launchers(record).items(): atomic_write(base/name, data)
    # Publish the active record last, while installers and sessions are excluded.
    atomic_write(base/'active.json', json_bytes(record))


def terminal_command(release, request):
    python = release/'payload/host/python.exe'
    script = release/'payload/app/scripts/start_windows_terminal.py'
    ordinary(python); ordinary(script)
    command = [str(python), '-I', '-B', str(script)]
    if request['plain']: command.append('--plain')
    if request['scrollback']: command.append('--scrollback')
    if request['required_policy_key_sha256']:
        command += ['--required-policy-key-sha256', request['required_policy_key_sha256']]
    # Native-code acceptance is release-bound and must be requalified after update.
    return command


def spawn_terminal(release, request):
    return subprocess.Popen(terminal_command(release, request), cwd=release/'payload',
                            creationflags=subprocess.CREATE_NEW_CONSOLE, close_fds=True)


def install_update(root, ticket, *, network=None, runner=subprocess.run,
                   lock=exclusive_lock, wait=wait_for_parent, spawn=spawn_terminal):
    from .terminal_updates import require_unsigned_update_path
    require_unsigned_update_path()
    root, ticket = Path(root).absolute(), Path(ticket).absolute()
    config = installed_config(root)
    if config is None: raise AccessDenied('Installed host required')
    old = root.parent.parent; base = old.parent.parent; state = Path(config['state_root'])
    if (root != old/'payload/app' or old.parent.name != 'versions' or state != base/'state'
            or ticket.name != 'request.json' or ticket.parent.parent != state/'updates'
            or not re.fullmatch(r'u-[a-f0-9]{32}', ticket.parent.name)):
        raise AccessDenied('Update ticket is outside private installation storage')
    request = bounded_json(ticket)
    fields = {'format_version', 'origin', 'archive', 'source_manifest_sha256', 'metadata_sha256',
              'previous_version', 'previous_manifest_sha256', 'source', 'parent_pid',
              'required_policy_key_sha256', 'plain', 'scrollback'}
    if (not isinstance(request, dict) or set(request) != fields or request['format_version'] != 1
            or request['previous_version'] != old.name or type(request['parent_pid']) is not int or request['parent_pid'] <= 0
            or type(request['plain']) is not bool or type(request['scrollback']) is not bool
            or request['required_policy_key_sha256'] is not None and
               (not isinstance(request['required_policy_key_sha256'], str) or
                not re.fullmatch(r'[a-f0-9]{64}', request['required_policy_key_sha256']))
            or request['source'] != str(ticket.parent/'source/payload')):
        raise AccessDenied('Invalid update handoff')
    validate_origin(request['origin'])
    candidate = UpdateCandidate(request['origin'], request['archive'], request['source_manifest_sha256'], request['metadata_sha256'])
    verify_release(old, request['previous_manifest_sha256'])
    # Claim once; a crash/replayed handoff cannot install the same transaction again.
    with (ticket.parent/'.claimed').open('xb') as stream: stream.write(b'claimed\n')
    result = {'format_version': 1, 'status': 'failed', 'previous_version': old.name,
              'release_tag': candidate.origin['tag'], 'deployment_ready': False}
    snapshot, activated, target, parent_exited = None, False, None, False
    try:
        wait(request['parent_pid'])
        parent_exited = True
        with lock(base/'.installation-lock'):
            active = bounded_json(base/'active.json', limit=16384)
            if active.get('version') != old.name or active.get('manifest_sha256') != request['previous_manifest_sha256']:
                raise AccessDenied('Active installation changed; start SILO again before updating')
            if discover(read_origin(root), network or ReleaseNetwork()) != candidate:
                raise AccessDenied('Published update changed after download')
            source_root = ticket.parent/'source'
            verify_release(source_root, candidate.manifest_sha256)
            source = source_root/'payload'
            if read_origin(source) != candidate.origin: raise AccessDenied('Staged release identity changed')
            archive = ticket.parent/'source.zip'
            if ordinary(archive).st_size != candidate.archive['size'] or digest_file(archive) != candidate.archive['sha256']:
                raise AccessDenied('Staged source archive changed')
            versions = base/'versions'; ordinary(versions, directory=True)
            pending = versions/('.pending-update-'+secrets.token_hex(16)); pending.mkdir(mode=0o700)
            cache = base/'cache'; cache.mkdir(mode=0o700, exist_ok=True); ordinary(cache, directory=True)
            prepared_path = ticket.parent/'prepared.json'
            host = old/'payload/host/python.exe'; ordinary(host)
            command = [str(host), '-I', '-B', str(source/'scripts/install_evaluation.py'),
                '--application-update', '--destination', str(pending), '--cache', str(cache),
                '--state-root', str(state), '--result', str(prepared_path)]
            # Reserve the GPU/session slot while preparing; preflight acquires its own lock.
            with lock(state/'session.lock'):
                if runner(command, cwd=source, timeout=1800).returncode != 0:
                    raise AccessDenied('Update preparation failed; previous installation retained')
            prepared = bounded_json(prepared_path)
            if (prepared.get('evaluation_only') is not True or prepared.get('deployment_ready') is not False
                    or not isinstance(prepared.get('release_id'), str) or not re.fullmatch(r'[a-f0-9]{16}', prepared['release_id'])):
                raise AccessDenied('Prepared update is not an evaluation installation')
            manifest = prepared.get('manifest_sha256')
            if not isinstance(manifest, str) or not re.fullmatch(r'[a-f0-9]{64}', manifest): raise AccessDenied('Invalid prepared digest')
            verify_release(pending, manifest)
            if read_origin(pending/'payload/app') != candidate.origin:
                raise AccessDenied('Prepared release identity changed')
            preflight = [str(pending/'payload/host/python.exe'), '-I', '-B',
                str(pending/'payload/app/scripts/check_evaluation_install.py'), '--manifest-sha256', manifest, '--application-update']
            if request['required_policy_key_sha256']:
                preflight += ['--required-policy-key-sha256', request['required_policy_key_sha256']]
            if runner(preflight, cwd=pending/'payload', timeout=600).returncode != 0:
                raise AccessDenied('Native update preflight failed; previous installation retained')
            report = bounded_json(state/'installation-preflight.json')
            if (report.get('manifest_sha256') != manifest or report.get('mode') != 'application_update'
                    or report.get('evaluation_preflight_passed') is not True or report.get('deployment_ready') is not False
                    or report.get('full_isolation_accepted') is not False):
                raise AccessDenied('Update preflight receipt does not match this transaction')
            atomic_write(ticket.parent/'native-preflight.json', json_bytes(report))
            version = prepared['release_id']+'-'+secrets.token_hex(4)
            target = versions/version
            pending.rename(target)
            record = {'format_version': 1, 'version': version, 'source_id': prepared['release_id'],
                'manifest_sha256': manifest, 'evaluation_only': True, 'evaluation_preflight_passed': True,
                'deployment_ready': False, 'full_isolation_accepted': False}
            with lock(state/'session.lock'):
                snapshot = activation_snapshot(base)
                try:
                    activate(base, record, snapshot['active.json'])
                    activated = True
                except BaseException:
                    restore_activation(base, snapshot); raise
            try: spawn(target, request)
            except BaseException:
                with lock(state/'session.lock'): restore_activation(base, snapshot)
                activated = False
                raise
            result.update(status='installed', version=version, manifest_sha256=manifest)
    except Exception as error:
        result['error_type'] = type(error).__name__
        # Never undo another installer/session's active version on an unknown outcome.
        try:
            current = bounded_json(base/'active.json', limit=16384)
            if parent_exited and not activated and current.get('version') == old.name:
                verify_release(old, request['previous_manifest_sha256'])
                spawn(old, request); result['previous_restarted'] = True
            else: result['previous_restarted'] = False
        except Exception: result['previous_restarted'] = False
        print('Update stopped: '+str(error), flush=True)
    finally:
        atomic_write(ticket.parent/'result.json', json_bytes(result))
    return result
