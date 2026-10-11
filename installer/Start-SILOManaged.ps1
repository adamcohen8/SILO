# Sign and deploy this launcher through the organization's trusted mechanism.
# It executes only the enrolled, administrator-protected SILO interpreter/script.
param([ValidateSet('Terminal','Desktop')][string]$Interface='Terminal',[switch]$Candidate)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
if (-not ('SILOFileIdentity' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class SILOFileIdentity {
    [StructLayout(LayoutKind.Sequential)] public struct Info {
        public uint Attributes, CreationLow, CreationHigh, AccessLow, AccessHigh,
                    WriteLow, WriteHigh, Volume, SizeHigh, SizeLow, Links, IndexHigh, IndexLow;
    }
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool GetFileInformationByHandle(SafeFileHandle file, out Info info);
    public static void Check(SafeFileHandle file) {
        Info info;
        if (!GetFileInformationByHandle(file,out info) || info.Links != 1 ||
            (info.Attributes & (0x400u | 0x1000u)) != 0)
            throw new InvalidOperationException("Linked or recalled release file refused.");
    }
}
'@
}

function Assert-LocalObject([string]$Path) {
    $item=Get-Item -LiteralPath $Path -Force
    while ($null -ne $item) {
        if ($item.Attributes -band ([IO.FileAttributes]::ReparsePoint -bor [IO.FileAttributes]::Offline)) {
            throw 'Linked, recalled or synchronized-placeholder storage is forbidden.'
        }
        if ($item -is [IO.FileInfo]) { $item=$item.Directory } else { $item=$item.Parent }
    }
}

function Assert-AdminProtection([string]$Path, [bool]$PublicRuntime=$false) {
    $acl=Get-Acl -LiteralPath $Path
    $owner=([Security.Principal.NTAccount]$acl.Owner).Translate([Security.Principal.SecurityIdentifier]).Value
    if ($owner -notin @('S-1-5-18','S-1-5-32-544')) { throw 'Release must be owned by SYSTEM or Administrators.' }
    foreach ($rule in $acl.Access) {
        $sid=$rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
        if ($rule.AccessControlType -ne 'Allow') { throw 'Unexpected deployment ACL.' }
        if ($sid -in @('S-1-5-18','S-1-5-32-544')) { continue }
        $readRights=[Security.AccessControl.FileSystemRights]::ReadAndExecute -bor [Security.AccessControl.FileSystemRights]::Synchronize
        $readers=@('S-1-5-32-545')
        if ($PublicRuntime) { $readers+= 'S-1-15-2-2' }
        if ($sid -notin $readers -or ($rule.FileSystemRights -band (-bnot $readRights))) {
            throw 'Ordinary users must have read/execute access only.'
        }
    }
}

# This first stage must itself be delivered in administrator-owned storage.
Assert-LocalObject $PSCommandPath
Assert-AdminProtection $PSCommandPath $true
Assert-AdminProtection $PSScriptRoot $true

$machine=Join-Path ([Environment]::GetFolderPath('CommonApplicationData')) 'SILO-Security'
$records=Join-Path $machine 'records.json'
Assert-LocalObject $machine
Assert-AdminProtection $machine
Assert-AdminProtection $records
$streams=[Collections.Generic.List[IDisposable]]::new()
try {
    $stateStream=[IO.File]::Open($records,'Open','Read','Read')
    $streams.Add($stateStream)
    [SILOFileIdentity]::Check($stateStream.SafeFileHandle)
    if ($stateStream.Length -gt 8388608) { throw 'Machine records exceed limit.' }
    $reader=[IO.StreamReader]::new($stateStream,[Text.Encoding]::UTF8,$true,4096,$true)
    try { $state=ConvertFrom-Json -InputObject $reader.ReadToEnd() } finally { $reader.Dispose() }
    if ($Candidate) {
        $principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
        if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
            throw 'Synthetic candidate evaluation requires explicit administrator access.'
        }
        $deployment=$state.records.'evaluation-deployment'
    } else { $deployment=$state.records.deployment }
    if ($state.format -ne 1 -or $deployment.format -ne 1) { throw 'Incomplete deployment enrollment.' }
    $envelope=[Convert]::FromBase64String($deployment.release_envelope)
    $hash=[Security.Cryptography.SHA256]::Create()
    try { $digest=([BitConverter]::ToString($hash.ComputeHash($envelope))).Replace('-','').ToLowerInvariant() }
    finally { $hash.Dispose() }
    if ($digest -ne $deployment.release_sha256) { throw 'Approved release envelope differs from protected enrollment.' }
    if ($null -ne $state.records.PSObject.Properties['revoked-releases'] -and $digest -in $state.records.'revoked-releases') {
        throw 'Application release revoked.'
    }
    # Enrollment verified the independent signature; this protected exact digest
    # authenticates the envelope before any downloaded interpreter is executed.
    $manifest=ConvertFrom-Json -InputObject ([Text.Encoding]::UTF8.GetString($envelope))
    $payload=[IO.Path]::GetFullPath((Join-Path $deployment.release_root 'payload'))
    $releases=Join-Path ([Environment]::GetFolderPath('ProgramFiles')) 'SILO\Releases'
    if ([IO.Path]::GetFullPath((Split-Path -Parent $deployment.release_root)) -ne [IO.Path]::GetFullPath($releases)) {
        throw 'Managed release must be under Windows Program Files SILO Releases.'
    }
    Assert-AdminProtection $releases $true
    Assert-AdminProtection (Split-Path -Parent $releases) $true
    Assert-AdminProtection $deployment.release_root $true
    Assert-LocalObject $payload
    Assert-AdminProtection $payload $true
    $seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($file in $manifest.payload.files) {
        if ($file.path -match '(^/|\\|:|(^|/)\.\.?(/|$)|[\x00-\x1f])' -or -not $seen.Add($file.path)) {
            throw 'Unsafe or duplicate release path.'
        }
        $path=[IO.Path]::GetFullPath((Join-Path $payload $file.path))
        if (-not $path.StartsWith($payload+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {
            throw 'Release path escapes payload.'
        }
        Assert-LocalObject $path
        Assert-AdminProtection $path $true
        $stream=[IO.File]::Open($path,'Open','Read','Read')
        $streams.Add($stream)
        [SILOFileIdentity]::Check($stream.SafeFileHandle)
        if ($stream.Length -ne $file.size) { throw 'Release file size changed.' }
        $hash=[Security.Cryptography.SHA256]::Create()
        try { $actual=([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
        finally { $hash.Dispose() }
        if ($actual -ne $file.sha256) { throw 'Release file hash changed.' }
    }
    # Refuse unlisted files that Python/site/DLL loading might consume.
    foreach ($item in Get-ChildItem -LiteralPath $payload -Force -Recurse) {
        Assert-LocalObject $item.FullName
        Assert-AdminProtection $item.FullName $true
        if (-not $item.PSIsContainer) {
            $relative=$item.FullName.Substring($payload.Length+1).Replace('\','/')
            if (-not $seen.Contains($relative)) { throw 'Unlisted release file.' }
        }
    }
    $python=Join-Path $payload 'host\python.exe'
    $script=Join-Path $payload ('app\scripts\start_windows_'+$(if($Interface -eq 'Terminal'){'terminal'}else{'ui'})+'.py')
    # Native extension/plugin loaders also consume environment and current
    # directory settings; Python -I alone does not isolate those loaders.
    foreach ($entry in @(Get-ChildItem Env:)) {
        if ($entry.Name -like 'QT_*' -or $entry.Name -like 'PYTHON*' -or $entry.Name -in
            @('QML_IMPORT_PATH','QML2_IMPORT_PATH','OPENSSL_CONF','OPENSSL_MODULES')) {
            Remove-Item -LiteralPath ('Env:'+ $entry.Name)
        }
    }
    $env:PATH=[Environment]::SystemDirectory+';'+[Environment]::GetFolderPath('Windows')
    Push-Location -LiteralPath (Join-Path $payload 'host')
    try {
        if ($Candidate) { & $python -I -B $script --evaluation } else { & $python -I -B $script }
        $result=$LASTEXITCODE
    } finally { Pop-Location }
    exit $result
} finally {
    foreach ($stream in $streams) { $stream.Dispose() }
}
