"""Generate hash-pinned public bootstrap assets from an exact Git source snapshot.

No model, dependencies, Git history, credentials or local untracked files are
included. Generation never publishes assets or changes repository visibility.
"""
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

from .asset_integrity import entries
from .windows_folders import parts

MAX_SOURCE = 16 * 1024**2
ROOT_FILES = {'.gitattributes', '.gitignore', 'AGENTS.md', 'README.md', 'test_plan.md', 'windows_test_report.md', 'Start-LocalAI.cmd', 'Start-SILO-Terminal.cmd', 'pyproject.toml', 'LICENSE', 'NOTICE', 'CHANGELOG.md'}
BRANDING_FILES = {'assets/branding/silo.png', 'assets/branding/silo.ico'}
SYNTHETIC_CSV_FILES = {'tests/fixtures/silo-milestone/'+name for name in
                       ('inventory.csv', 'missing-capacity.csv', 'invalid-quantity.csv', 'malformed.csv')}
DIRECTORIES = {'src', 'tests', 'installer', 'scripts', 'docs', 'profiles', 'requirements'}
EXTENSIONS = {'.py', '.ps1', '.in', '.md', '.json', '.txt', '.toml', '.cmd'}
REQUIRED = {'README.md', 'AGENTS.md', 'Start-LocalAI.cmd', 'installer/Install-Evaluation.ps1',
            'installer/Evaluation-Common.ps1', 'installer/Bootstrap-Evaluation.ps1.in',
            'profiles/windows-evaluation-installer.json', 'profiles/nemotron-30b-4090-assets.json',
            'profiles/nemotron-30b-4090-candidate.json', 'scripts/install_evaluation.py',
            'scripts/check_evaluation_install.py', 'scripts/contained_agent_worker.py',
            'src/local_ai_appliance/evaluation_install.py', 'tests/synthetic_documents.py'} | BRANDING_FILES


def permitted(name):
    components = parts(name)
    if name not in ROOT_FILES | BRANDING_FILES | SYNTHETIC_CSV_FILES and (components[0] not in DIRECTORIES or Path(name).suffix not in EXTENSIONS):
        raise ValueError('Unexpected tracked item requires source publication review: '+name)


def git_snapshot(repository, revision):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('An exact 40-character source commit is required.')
    records = subprocess.check_output(['git', 'ls-tree', '-rz', '-l', '--full-tree', revision], cwd=repository)
    objects, total = [], 0
    for record in records.split(b'\0'):
        if not record:
            continue
        header, raw_name = record.split(b'\t', 1)
        mode, kind, oid, raw_size = header.split()
        name = raw_name.decode('utf-8')
        permitted(name)
        if kind != b'blob' or mode not in {b'100644', b'100755'}:
            raise ValueError('Source links, submodules and special objects are unavailable.')
        size = int(raw_size)
        total += size
        if size > 2 * 1024**2 or total > MAX_SOURCE or len(objects) >= 2000:
            raise ValueError('Source publication exceeds its bounded source-only limits.')
        objects.append((name, oid, size))
    # One bounded batch avoids one Git subprocess per source file. Object IDs
    # are immutable, and all sizes/types were checked before requesting bytes.
    output = subprocess.check_output(['git', 'cat-file', '--batch'], cwd=repository,
                                     input=b'\n'.join(oid for _, oid, _ in objects)+b'\n') if objects else b''
    stream, result = io.BytesIO(output), {}
    for name, oid, size in objects:
        header = stream.readline(128).split()
        if header != [oid, b'blob', str(size).encode('ascii')]:
            raise ValueError('Unexpected Git object metadata.')
        data = stream.read(size)
        if len(data) != size or stream.read(1) != b'\n':
            raise ValueError('Unexpected Git object size.')
        result[name] = data
    if stream.read(1):
        raise ValueError('Unexpected trailing Git object bytes.')
    return result


def json_bytes(value):
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True).encode('ascii')+b'\n'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def signature_comments(data):
    lines = data.strip(b'\r\n').splitlines()
    return (len(lines) >= 3 and lines[0] == b'# SIG # Begin signature block'
            and lines[-1] == b'# SIG # End signature block'
            and all(re.fullmatch(rb'# [A-Za-z0-9+/=]+', line) for line in lines[1:-1]))


def embedded_script(data):
    """Embed helper code, retaining its original signed bytes in the source ZIP.

    A helper's appended signature authenticates that helper file only. Including
    it inside another script would conflict with that script's signing step.
    """
    text = data.decode('utf-8-sig')
    marker = '# SIG # Begin signature block'
    if marker not in text:
        return text
    index = text.index(marker)
    if (text.count(marker) != 1 or index and text[index - 1] != '\n'
            or not signature_comments(text[index:].encode('utf-8'))):
        raise ValueError('Embedded helper has an unsupported signature comment block')
    return text[:index]


def curl_command(url, sha256, size, *, installer_arguments=None):
    # Paste into native PowerShell. Use curl.exe explicitly (curl can be an
    # Invoke-WebRequest alias in Windows PowerShell), check before &, and keep
    # the Internet-zone marker. No pipe/Invoke-Expression or policy bypass.
    if (not isinstance(url, str) or not url.startswith('https://') or len(url) > 4096
            or any(ord(c) < 32 for c in url) or not isinstance(sha256, str)
            or not re.fullmatch('[a-f0-9]{64}', sha256) or type(size) is not int
            or not 0 < size <= MAX_SOURCE):
        raise ValueError('Use a bounded HTTPS bootstrap and exact digest/size')
    arguments = {} if installer_arguments is None else installer_arguments
    allowed = {'InstallRoot', 'CachePath', 'ModelId', 'ActivationPlan', 'ActivationPlanSha256',
               'Interface', 'Activate', 'PrepareOnly', 'Offline', 'NoShortcut', 'Repair'}
    if not isinstance(arguments, dict) or set(arguments) - allowed:
        raise ValueError('Unsupported bootstrap arguments')
    invocation = ''
    for name, value in arguments.items():
        if type(value) is bool:
            if value: invocation += ' -' + name
        elif isinstance(value, str) and value and len(value) <= 4096 and not any(ord(c) < 32 for c in value):
            # Single-quoted PowerShell literals never interpolate $(), backticks,
            # environment variables or user-supplied quotes.
            invocation += " -" + name + " '" + value.replace("'", "''") + "'"
        else:
            raise ValueError('Use bounded literal bootstrap arguments')
    return ("$b=Join-Path $env:TEMP ('local-ai-'+[guid]::NewGuid().ToString('N')+'.ps1'); "
            f"curl.exe --disable --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --connect-timeout 15 --max-time 180 --retry 2 --max-filesize {size} '"+url.replace("'", "''")+"' --output $b; "
            "if($LASTEXITCODE -ne 0){throw 'Bootstrap download failed'}; "
            "Set-Content -LiteralPath ($b+':Zone.Identifier') -Encoding ASCII -Value \"[ZoneTransfer]`r`nZoneId=3\"; "
            "$f=[IO.File]::Open($b,'Open','Read','Read'); $h=[Security.Cryptography.SHA256]::Create(); "
            "try { if(([BitConverter]::ToString($h.ComputeHash($f))).Replace('-','') -ne '"+sha256+
            "'){throw 'Bootstrap integrity failed'}; & $b" + invocation + " } finally {$h.Dispose(); $f.Dispose()}")


def assemble(source, revision, repository, tag, *, update_sequence=0):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('An exact source commit is required.')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9][A-Za-z0-9._-]{0,99}', repository):
        raise ValueError('Use an ordinary GitHub owner/repository.')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', tag):
        raise ValueError('Use a bounded release tag without shell or path characters.')
    if not REQUIRED <= set(source):
        raise ValueError('The reviewed source snapshot is incomplete.')
    managed = ('$installArguments.Activate=$true' in source['installer/Bootstrap-Evaluation.ps1.in'].decode('utf-8-sig')
               and '[switch]$Activate' in source['installer/Install-Evaluation.ps1'].decode('utf-8-sig'))
    if managed and not {'installer/Activate-SILO.ps1', 'installer/Protect-SILORelease.ps1',
                        'installer/Register-SILOAudit.ps1', 'installer/Start-SILOManaged.ps1',
                        'scripts/install_managed.py', 'src/local_ai_appliance/managed_installation.py'} <= set(source):
        raise ValueError('Reviewed activation requires the complete managed installer source')
    if type(update_sequence) is not int or not 0 <= update_sequence < 2**53:
        raise ValueError('Use a nonnegative monotonic update sequence')
    source = dict(source)
    origin = {'format_version': 1, 'repository': repository, 'channel': 'stable',
              'sequence': update_sequence, 'tag': tag, 'source_revision': revision}
    if update_sequence:
        if 'src/local_ai_appliance/terminal_updates.py' not in source:
            raise ValueError('Update-channel releases require the terminal updater')
        source['profiles/release-origin.json'] = json_bytes(origin)
    total, inventory = 0, []
    for name, data in sorted(source.items()):
        permitted(name)
        if not isinstance(data, bytes) or len(data) > 2 * 1024**2:
            raise ValueError('Only bounded source bytes are permitted.')
        total += len(data)
        inventory.append({'path': name, 'size': len(data), 'sha256': digest(data)})
    if total > MAX_SOURCE or len(source) > 2000:
        raise ValueError('Source publication exceeds its limits.')
    entries(inventory)
    manifest = json_bytes({'format_version':1, 'evaluation_only':True, 'deployment_ready':False, 'files':inventory})
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in [('release-manifest.json', manifest), *[('payload/'+n, d) for n, d in sorted(source.items())]]:
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    archive = stream.getvalue()
    filename = 'local-ai-source-'+revision+'.zip'
    base_url = f'https://github.com/{repository}/releases/download/{tag}/'
    pin = {'filename': filename, 'size':len(archive), 'sha256':digest(archive), 'url':base_url+filename}
    template = source['installer/Bootstrap-Evaluation.ps1.in'].decode('utf-8-sig')
    replacements = {'@@REVISION@@':revision, '@@COMMON@@':embedded_script(source['installer/Evaluation-Common.ps1']),
                    '@@SOURCE_PIN@@':json_bytes(pin).decode('ascii').strip(), '@@MANIFEST_SHA256@@':digest(manifest),
                    '@@SOURCE_ID@@':revision[:16]+'-'+digest(manifest)[:8]}
    for token, value in replacements.items():
        if token not in template:
            raise ValueError('Bootstrap template lacks a required binding.')
        template = template.replace(token, value)
    if '@@' in template:
        raise ValueError('Bootstrap contains unresolved bindings.')
    bootstrap = template.encode('utf-8-sig')
    command = curl_command(base_url+'install.ps1', digest(bootstrap), len(bootstrap))
    metadata = {'format_version':1, 'source_revision':revision, 'repository':repository, 'tag':tag,
                'evaluation_only':True, 'deployment_ready':False, 'published':False,
                'authenticode_signed':False, 'native_windows_acceptance':'not_run',
                'source_archive':pin, 'source_manifest_sha256':digest(manifest),
                'bootstrap':{'filename':'install.ps1', 'size':len(bootstrap), 'sha256':digest(bootstrap), 'url':base_url+'install.ps1'}}
    metadata['reviewed_activation_supported'] = managed
    if update_sequence: metadata['update'] = origin
    instruction = ('# Prepared evaluation installation command\n\n'
                   'Run in native 64-bit Windows PowerShell from any folder after the public release assets are published.\n'
                   'This command is not live until publication. Existing script policy and unsigned-script restrictions apply.\n'
                   'It performs a public/synthetic evaluation; native Windows acceptance and CUI authorization remain pending.\n\n'
                   + ('Default: prepare an inactive candidate. Activation requires a separately reviewed exact-host plan, independent signatures and native acceptance.\n\n' if managed else '') +
                   '```powershell\n'+command+'\n```\n')
    return {filename:archive, 'install.ps1':bootstrap, 'release.json':json_bytes(metadata),
            'INSTALL.md':instruction.encode('utf-8')}, metadata


def write_assets(assets, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for name, data in assets.items():
        if len(parts(name)) != 1:
            raise ValueError('Release assets require simple filenames.')
        with (destination/name).open('xb') as stream:
            stream.write(data)


def repin_bootstrap(assets, signed_bootstrap):
    """Repin externally supplied signature bytes in a new unpublished asset set.

    This portable step cannot establish Authenticode trust. A native reviewer
    must verify signer/status/timestamp and policy before publication.
    """
    from .model import strict_json
    metadata = strict_json(assets['release.json'])
    original = assets['install.ps1']
    if (metadata.get('published') is not False or metadata.get('reviewed_activation_supported') is not True
            or digest(original) != metadata['bootstrap']['sha256']
            or len(original) != metadata['bootstrap']['size']
            or digest(assets[metadata['source_archive']['filename']]) != metadata['source_archive']['sha256']):
        raise ValueError('Only an intact unpublished release can be repinned')
    if (not isinstance(signed_bootstrap, bytes) or len(signed_bootstrap) > MAX_SOURCE
            or not signed_bootstrap.startswith(original) or b'# SIG # Begin signature block' in original):
        raise ValueError('Signing must preserve the complete reviewed bootstrap bytes')
    if not signature_comments(signed_bootstrap[len(original):]):
        raise ValueError('Only an appended Authenticode comment block is accepted')
    metadata['bootstrap'].update(size=len(signed_bootstrap), sha256=digest(signed_bootstrap))
    metadata['authenticode_signed'] = False
    metadata['authenticode_status'] = 'supplied_pending_native_verification'
    metadata['native_windows_acceptance'] = 'not_run'
    pin = metadata['bootstrap']
    command = curl_command(pin['url'], pin['sha256'], pin['size'])
    instructions = ('# Prepared signed-bootstrap installation command\n\n'
                    'External signature bytes were repinned locally; native Authenticode signer, timestamp, trust and policy validation remain pending.\n'
                    'This command is not live until publication. Default preparation stays inactive; managed activation needs its reviewed exact-host plan.\n\n'
                    '```powershell\n' + command + '\n```\n')
    return {**assets, 'install.ps1': signed_bootstrap, 'release.json': json_bytes(metadata),
            'INSTALL.md': instructions.encode('utf-8')}
