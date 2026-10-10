#Requires -Version 5.1
<#
.SYNOPSIS
One-command, application-local Windows evaluation installation.
.DESCRIPTION
Run from the reviewed source ZIP. Downloads pinned public assets on the host,
or uses -Offline -CachePath. Supplies Python; no Codex runtime, pip setup hooks,
execution-policy changes, global firewall changes, driver installation or CUI
activation. The native preflight must pass before an installation is published.
#>
[CmdletBinding()]
param([string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'LocalAI-Evaluation'),
      [string]$CachePath,
      [switch]$Offline,
      [switch]$NoLaunch,
      [switch]$NoShortcut,
      [switch]$Repair,
      [switch]$Rollback)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitProcess) { throw 'Run native 64-bit Windows PowerShell.' }
. (Join-Path $PSScriptRoot 'Evaluation-Common.ps1')
$source = Split-Path -Parent $PSScriptRoot
$base = New-PrivateDirectory $InstallRoot
$versions = New-PrivateDirectory (Join-Path $base 'versions')
$state = New-PrivateDirectory (Join-Path $base 'state')
if ([Text.Encoding]::UTF8.GetByteCount((Join-Path $state 'i-12345678\s.sock')) -ge 108) {
    throw 'The private socket path would be too long. Use -InstallRoot with a shorter local NTFS path.'
}
$lockPath = Join-Path $base '.installation-lock'
$lock = [IO.File]::Open($lockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
$bootstrap = $null
$transaction = $null

function Write-ActiveLaunchers($Record) {
    if ($Record.version -notmatch '^[0-9a-f]{16}(?:-[0-9a-f]{8})?$' -or $Record.manifest_sha256 -notmatch '^[0-9a-f]{64}$') {
        throw 'Invalid active installation record.'
    }
    $command = '@echo off' + "`r`n" + 'setlocal DisableDelayedExpansion' + "`r`n" +
        'powershell.exe -NoProfile -File "%~dp0versions\'+$Record.version+'\payload\app\installer\Start-Evaluation.ps1" '+
        '-InstallationRoot "%~dp0versions\'+$Record.version+'" -ManifestSha256 "'+$Record.manifest_sha256+'"'+"`r`n"+
        'if errorlevel 1 pause'+"`r`n"
    $launcher = Join-Path $base 'Start-LocalAI.cmd'
    [IO.File]::WriteAllText($launcher+'.new', $command, [Text.Encoding]::ASCII)
    if (Test-Path -LiteralPath $launcher) { [IO.File]::Replace($launcher+'.new', $launcher, $null) }
    else { [IO.File]::Move($launcher+'.new', $launcher) }
    $active = Join-Path $base 'active.json'
    $recordText = $Record | ConvertTo-Json -Depth 8
    [IO.File]::WriteAllText($active+'.new', $recordText, (New-Object Text.UTF8Encoding($false)))
    if (Test-Path -LiteralPath $active) {
        $previous = Join-Path $base 'active.previous.json'
        if (Test-Path -LiteralPath $previous) { Remove-Item -LiteralPath $previous }
        [IO.File]::Replace($active+'.new', $active, $previous)
    } else { [IO.File]::Move($active+'.new', $active) }
}

try {
    Write-Host 'LOCAL EVALUATION - public or synthetic documents only. Full isolation/CUI acceptance remains pending.'
    $active = Join-Path $base 'active.json'
    if ($Rollback) {
        $previous = Join-Path $base 'active.previous.json'
        if (-not (Test-Path -LiteralPath $previous)) { throw 'No previous installed evaluation is available.' }
        $record = Get-Content -LiteralPath $previous -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($record.version -notmatch '^[0-9a-f]{16}(?:-[0-9a-f]{8})?$') { throw 'Invalid previous version.' }
        $target = Join-Path $versions $record.version
        Test-EvaluationRelease $target $record.manifest_sha256
        Write-ActiveLaunchers $record
        Write-Host 'Previous verified evaluation restored. State and granted documents were preserved.'
        return
    }
    if (-not $CachePath) { $CachePath = New-PrivateDirectory (Join-Path $base 'cache') }
    else { $CachePath = Test-LocalPath $CachePath -Directory }
    if (-not (Test-Path -LiteralPath $CachePath)) { throw 'The selected cache directory must exist.' }
    $profile = Get-Content -LiteralPath (Join-Path $source 'profiles\windows-evaluation-installer.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($profile.format_version -ne 1 -or $profile.evaluation_only -ne $true -or $profile.deployment_ready -ne $false) { throw 'Expected the reviewed evaluation profile.' }
    $archive = Get-PinnedDownload $profile.python $CachePath -Offline:$Offline
    $bootstrap = New-PrivateDirectory (Join-Path $base ('.bootstrap-'+[Guid]::NewGuid().ToString('N')))
    Expand-PythonArchive $archive $bootstrap $profile.python
    $python = Join-Path $bootstrap 'python.exe'
    $entry = Join-Path $source 'scripts\install_evaluation.py'
    # Avoid embedded quotes in -c: Windows PowerShell 5.1 strips them when
    # marshaling legacy native-command arguments. The archive is Windows-only.
    & $python -I -B -c 'import ctypes,sys; sys.exit(0 if ctypes.sizeof(ctypes.c_void_p)==8 and sys.version_info[:2]==(3,14) else 2)'
    if ($LASTEXITCODE -ne 0) { throw 'The pinned native interpreter prerequisite failed.' }
    $sourceId = & $python -I -B $entry --identity-only
    if ($LASTEXITCODE -ne 0 -or $sourceId -notmatch '^[0-9a-f]{16}$') { throw 'Source inventory failed.' }
    $record = $null
    if ((Test-Path -LiteralPath $active) -and -not $Repair) {
        $existing = Get-Content -LiteralPath $active -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($existing.source_id -eq $sourceId) {
            if ($existing.version -notmatch '^[0-9a-f]{16}(?:-[0-9a-f]{8})?$') { throw 'Invalid installed version.' }
            Test-EvaluationRelease (Join-Path $versions $existing.version) $existing.manifest_sha256
            $record = $existing
            Write-Host 'The same verified evaluation is already installed.'
        }
    }
    if (-not $record) {
        $transaction = New-PrivateDirectory (Join-Path $versions ('.pending-'+[Guid]::NewGuid().ToString('N')))
        $arguments = @('-I', '-B', $entry, '--destination', $transaction, '--cache', $CachePath, '--state-root', $state)
        if ($Offline) { $arguments += '--offline' }
        $preparedText = & $python @arguments
        if ($LASTEXITCODE -ne 0) { throw 'Preparation failed. The previous installation and resumable cache were preserved.' }
        $prepared = $preparedText | ConvertFrom-Json
        if ($prepared.release_id -ne $sourceId) { throw 'Source changed during installation; the transaction was not published.' }
        Test-EvaluationRelease $transaction $prepared.manifest_sha256
        # User preferences are mutable state, outside the immutable release tree.
        $instructions = Join-Path $state 'AGENTS.md'
        if (-not (Test-Path -LiteralPath $instructions)) {
            [IO.File]::Copy((Join-Path $transaction 'payload\app\AGENTS.md'), $instructions, $false)
        }
        $hostPython = Join-Path $transaction 'payload\host\python.exe'
        $check = Join-Path $transaction 'payload\app\scripts\check_evaluation_install.py'
        Write-Host 'Running native GPU, contained-token, synthetic document and cleanup preflight...'
        & $hostPython -I -B $check --manifest-sha256 $prepared.manifest_sha256
        if ($LASTEXITCODE -ne 0) { throw ('Native preflight failed; inspect '+(Join-Path $state 'installation-preflight.json')+'. This evaluation was not made active.') }
        $version = $sourceId
        if (Test-Path -LiteralPath (Join-Path $versions $version)) { $version += '-'+[Guid]::NewGuid().ToString('N').Substring(0,8) }
        [IO.Directory]::Move($transaction, (Join-Path $versions $version))
        $transaction = $null
        $record = @{format_version=1; version=$version; source_id=$sourceId; manifest_sha256=$prepared.manifest_sha256;
                    evaluation_only=$true; evaluation_preflight_passed=$true; deployment_ready=$false; full_isolation_accepted=$false}
        Write-ActiveLaunchers $record
    }
    if (-not $NoShortcut) {
        $menu = Join-Path ([Environment]::GetFolderPath('Programs')) 'Local AI Evaluation.lnk'
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($menu)
        $launcher = Join-Path $base 'Start-LocalAI.cmd'
        if (-not (Test-Path -LiteralPath $menu) -or $shortcut.TargetPath -eq $launcher) {
            $shortcut.TargetPath = $launcher
            $shortcut.WorkingDirectory = $base
            $shortcut.Description = 'Local AI evaluation - public or synthetic documents only'
            $shortcut.Save()
        } else { Write-Warning 'An unrelated shortcut already uses this name; it was preserved.' }
    }
    Write-Host ('Installed evaluation. Start it with: '+(Join-Path $base 'Start-LocalAI.cmd'))
    if (-not $NoLaunch) {
        $installed = Join-Path $versions $record.version
        & (Join-Path $installed 'payload\app\installer\Start-Evaluation.ps1') -InstallationRoot $installed -ManifestSha256 $record.manifest_sha256
    }
} catch {
    if ($transaction) { Write-Warning ('Incomplete private transaction retained for inspection: '+$transaction) }
    throw
} finally {
    # Only the fresh, owned bootstrap is retired. Versions, state and cache are retained.
    if ($bootstrap -and (Split-Path -Parent $bootstrap) -eq $base -and (Split-Path -Leaf $bootstrap) -match '^\.bootstrap-[0-9a-f]{32}$') {
        Test-LocalPath $bootstrap -Directory | Out-Null
        Remove-Item -LiteralPath $bootstrap -Recurse -Force
    }
    $lock.Dispose()
}
