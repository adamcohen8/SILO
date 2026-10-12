#Requires -Version 5.1
<#
.SYNOPSIS
One-command, application-local Windows evaluation installation.
.DESCRIPTION
Run from the reviewed source ZIP. Downloads pinned public assets on the host,
or uses -Offline -CachePath. Supplies Python; no Codex runtime, pip setup hooks,
execution-policy changes, global firewall changes, driver installation or CUI
activation. -PrepareOnly prepares an inactive candidate. -Activate consumes a
separately reviewed exact-host plan with independent signatures/native acceptance.
#>
[CmdletBinding()]
param([string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'LocalAI-Evaluation'),
      [string]$CachePath,
      [switch]$Offline,
      [switch]$NoLaunch,
      [switch]$NoShortcut,
      [switch]$Repair,
      [switch]$Rollback,
      [string]$ModelId,
      [switch]$Activate,
      [string]$ActivationPlan,
      [string]$ActivationPlanSha256,
      [ValidateSet('Terminal','Desktop')][string]$Interface='Terminal',
      [switch]$PrepareOnly)
$ErrorActionPreference = 'Stop'
if ($Rollback -or ($PrepareOnly -eq $Activate)) { throw 'Choose exactly one of -PrepareOnly or -Activate. Managed rollback requires separate administrative review.' }
if (-not $Activate -and ($ActivationPlan -or $ActivationPlanSha256)) { throw 'Activation inputs require -Activate.' }
if ($Activate -and (-not $ActivationPlan -or $ActivationPlanSha256 -notmatch '^[a-f0-9]{64}$')) { throw 'Activation requires a reviewed plan and its independently supplied SHA-256.' }
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitProcess) { throw 'Run native 64-bit Windows PowerShell.' }
. (Join-Path $PSScriptRoot 'Evaluation-Common.ps1')
$source = Split-Path -Parent $PSScriptRoot
$activationStream=$null
if ($Activate) {
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    $principal=[Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Use an approved elevated PowerShell session for the same target account; no automatic elevation is attempted.' }
    $ActivationPlan=Test-LocalPath $ActivationPlan
    $activationStream=[IO.File]::Open($ActivationPlan,'Open','Read','Read')
    try {
        if ($activationStream.Length -gt 8388608) { throw 'Install plan is oversized.' }
        $hash=[Security.Cryptography.SHA256]::Create()
        try { $digest=([BitConverter]::ToString($hash.ComputeHash($activationStream))).Replace('-','').ToLowerInvariant() }
        finally { $hash.Dispose() }
        if ($digest -ne $ActivationPlanSha256) { throw 'Install plan integrity failed.' }
        $activationStream.Position=0
        $reader=[IO.StreamReader]::new($activationStream,[Text.Encoding]::UTF8,$true,4096,$true)
        try { $activation=ConvertFrom-Json -InputObject $reader.ReadToEnd() } finally { $reader.Dispose() }
        if ($activation.format -ne 1 -or $activation.user_sid -cne $identity.User.Value -or
            [IO.Path]::GetFullPath($activation.state_root) -cne (Join-Path ([IO.Path]::GetFullPath($InstallRoot)) 'state')) {
            throw 'Install plan names a different target account or private state path.'
        }
        if ($ModelId -and $ModelId -cne $activation.model_id) { throw 'Explicit model differs from install approval.' }
        $ModelId=$activation.model_id
    } catch { $activationStream.Dispose(); throw }
}
try {
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
    if ($Activate -and $sourceId -cne $activation.source_id) { throw 'Install plan names different source; no application/model payload was prepared.' }
    . {
        $transaction = New-PrivateDirectory (Join-Path $versions ('.pending-'+[Guid]::NewGuid().ToString('N')))
        $arguments = @('-I', '-B', $entry, '--destination', $transaction, '--cache', $CachePath, '--state-root', $state)
        if ($Offline) { $arguments += '--offline' }
        if ($ModelId) { $arguments += @('--model-id', $ModelId) }
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
        $preparedRoot=Join-Path $versions $version
        Write-Host ('Inactive candidate prepared at: '+$preparedRoot)
        if ($Activate) {
            & (Join-Path $PSScriptRoot 'Activate-SILO.ps1') -PreparedRoot $preparedRoot -ActivationPlan $ActivationPlan -ActivationPlanSha256 $ActivationPlanSha256 -SourceId $sourceId -Interface $Interface -NoShortcut:$NoShortcut
        } else {
            Write-Host 'No shortcut, active record, application/model launch or native pass was produced. Follow docs/SILO-SECURITY-HARDENING.md for managed provisioning.'
        }
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
} finally { if ($activationStream) { $activationStream.Dispose() } }
