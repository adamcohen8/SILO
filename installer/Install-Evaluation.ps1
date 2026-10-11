#Requires -Version 5.1
<#
.SYNOPSIS
One-command, application-local Windows evaluation installation.
.DESCRIPTION
Run from the reviewed source ZIP. Downloads pinned public assets on the host,
or uses -Offline -CachePath. Supplies Python; no Codex runtime, pip setup hooks,
execution-policy changes, global firewall changes, driver installation or CUI
activation. This prepares an inactive candidate; managed launch requires separate
administrator protection, independent signatures and native security acceptance.
#>
[CmdletBinding()]
param([string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'LocalAI-Evaluation'),
      [string]$CachePath,
      [switch]$Offline,
      [switch]$NoLaunch,
      [switch]$NoShortcut,
      [switch]$Repair,
      [switch]$Rollback,
      [switch]$PrepareOnly)
$ErrorActionPreference = 'Stop'
if (-not $PrepareOnly -or $Rollback) { throw 'This installer now prepares inactive candidates only. Supply -PrepareOnly; use administrator-managed enrollment for activation or rollback.' }
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


try {
    Write-Host 'LOCAL EVALUATION - public or synthetic documents only. Full isolation/CUI acceptance remains pending.'
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
    . {
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
        $version = $sourceId
        if (Test-Path -LiteralPath (Join-Path $versions $version)) { $version += '-'+[Guid]::NewGuid().ToString('N').Substring(0,8) }
        [IO.Directory]::Move($transaction, (Join-Path $versions $version))
        $transaction = $null
        Write-Host ('Inactive candidate prepared at: '+(Join-Path $versions $version))
        Write-Host 'No shortcut, active record, interpreter launch or native pass was produced. Follow docs/SILO-SECURITY-HARDENING.md for managed provisioning.'
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
