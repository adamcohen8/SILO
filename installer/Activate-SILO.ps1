#Requires -Version 5.1
# Consume a separately reviewed plan. Never generate keys, evidence or relaxed policy.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$PreparedRoot,
      [Parameter(Mandatory=$true)][string]$ActivationPlan,
      [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{64}$')][string]$ActivationPlanSha256,
      [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{16}$')][string]$SourceId,
      [ValidateSet('Terminal','Desktop')][string]$Interface='Terminal',
      [switch]$NoShortcut)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitProcess) { throw 'Native 64-bit Windows required.' }
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=[Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Approved managed activation requires an elevated PowerShell session for the same target account.'
}
. (Join-Path $PSScriptRoot 'Evaluation-Common.ps1')

function Assert-ManagedDirectory([string]$Path) {
    Test-LocalPath $Path -Directory | Out-Null
    $acl=Get-Acl -LiteralPath $Path
    if (-not $acl.AreAccessRulesProtected -or
        $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -notin @('S-1-5-18','S-1-5-32-544')) {
        throw 'Existing managed directory has unsafe ownership or inheritance; it was not changed.'
    }
    $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    $expected=@{'S-1-5-18'=2032127; 'S-1-5-32-544'=2032127; 'S-1-5-32-545'=1179817; 'S-1-15-2-2'=1179817}
    $seen=@{}
    if ($rules.Count -ne 4) { throw 'Unexpected managed directory ACL; it was not changed.' }
    foreach ($rule in $rules) {
        $sid=$rule.IdentityReference.Value
        if (-not $expected.ContainsKey($sid) -or $seen.ContainsKey($sid) -or
            $rule.AccessControlType -ne 'Allow' -or [int]$rule.FileSystemRights -ne $expected[$sid] -or
            $rule.IsInherited -or [int]$rule.InheritanceFlags -ne 3 -or [int]$rule.PropagationFlags -ne 0) {
            throw 'Unexpected managed directory ACL; it was not changed.'
        }
        $seen[$sid]=$true
    }
}

function New-ManagedDirectory([string]$Path) {
    Test-LocalPath $Path -Directory | Out-Null
    if (-not (Test-Path -LiteralPath $Path)) {
        $acl=[Security.AccessControl.DirectorySecurity]::new()
        $acl.SetSecurityDescriptorSddlForm('O:BAD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;0x1200a9;;;BU)(A;OICI;0x1200a9;;;S-1-15-2-2)')
        $directory=[IO.DirectoryInfo]::new($Path)
        if ($PSVersionTable.PSEdition -eq 'Core') { [IO.FileSystemAclExtensions]::Create($directory,$acl) | Out-Null }
        else { $directory.Create($acl) }
    }
    Assert-ManagedDirectory $Path
}

function Hold-ApprovedPayload([string]$Root, $Files, $Handles) {
    $payload=Join-Path $Root 'payload'
    Test-LocalPath $payload -Directory | Out-Null
    $seen=@{}; $directories=@{}
    if ($Files.Count -lt 1 -or $Files.Count -gt 10000) { throw 'Invalid approved payload inventory.' }
    foreach ($file in $Files) {
        Test-RelativeName $file.path
        if ($seen.ContainsKey($file.path) -or $file.sha256 -notmatch '^[a-f0-9]{64}$') { throw 'Invalid approved payload pin.' }
        $seen[$file.path]=$file.path
        $components=$file.path.Split('/')
        for ($i=1; $i -lt $components.Count; $i++) { $directories[($components[0..($i-1)] -join '/')]= $true }
        $path=Test-LocalPath (Join-Path $payload $file.path.Replace('/','\'))
        $stream=[IO.File]::Open($path,'Open','Read','Read')
        $Handles.Add($stream)
        # OrdinaryFile checks link count on Windows without loading payload code.
        [SILOActivationFile]::Check($stream.SafeFileHandle)
        if ($stream.Length -ne [long]$file.size) { throw 'Approved payload size changed.' }
        $hash=[Security.Cryptography.SHA256]::Create()
        try { $actual=([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
        finally { $hash.Dispose() }
        if ($actual -cne $file.sha256) { throw 'Approved payload hash changed.' }
    }
    foreach ($item in @(Get-ChildItem -LiteralPath $payload -Recurse -Force)) {
        Test-LocalPath $item.FullName -Directory:$item.PSIsContainer | Out-Null
        $relative=$item.FullName.Substring($payload.Length+1).Replace('\','/')
        if ($item.PSIsContainer) {
            if (-not $directories.ContainsKey($relative)) { throw 'Undeclared approved payload directory.' }
        } elseif (-not $seen.ContainsKey($relative) -or $seen[$relative] -cne $relative) {
            throw 'Undeclared approved payload file.'
        }
    }
}

if (-not ('SILOActivationFile' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class SILOActivationFile {
    [StructLayout(LayoutKind.Sequential)] public struct Info {
        public uint Attributes, CreationLow, CreationHigh, AccessLow, AccessHigh,
                    WriteLow, WriteHigh, Volume, SizeHigh, SizeLow, Links, IndexHigh, IndexLow;
    }
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool GetFileInformationByHandle(SafeFileHandle file, out Info info);
    public static void Check(SafeFileHandle file) {
        Info info;
        if (!GetFileInformationByHandle(file,out info) || info.Links != 1 ||
            (info.Attributes & 0x441400u) != 0)
            throw new InvalidOperationException("Linked or recalled install input refused.");
    }
}
'@
}

$planPath=Test-LocalPath $ActivationPlan
$planStream=[IO.File]::Open($planPath,'Open','Read','Read')
$held=[Collections.Generic.List[IDisposable]]::new()
try {
    [SILOActivationFile]::Check($planStream.SafeFileHandle)
    if ($planStream.Length -gt 8388608) { throw 'Install plan exceeds its size bound.' }
    $hash=[Security.Cryptography.SHA256]::Create()
    try { $digest=([BitConverter]::ToString($hash.ComputeHash($planStream))).Replace('-','').ToLowerInvariant() }
    finally { $hash.Dispose() }
    if ($digest -ne $ActivationPlanSha256) { throw 'Install plan integrity failed.' }
    $planStream.Position=0
    $reader=[IO.StreamReader]::new($planStream,[Text.Encoding]::UTF8,$true,4096,$true)
    try { $plan=ConvertFrom-Json -InputObject $reader.ReadToEnd() } finally { $reader.Dispose() }
    if ($plan.source_id -cne $SourceId -or $plan.user_sid -cne $identity.User.Value -or
        $plan.release_name -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$' -or $plan.release_name.EndsWith('.')) {
        throw 'Install plan belongs to a different source/account or has an unsafe release name.'
    }
    Test-RelativeName $plan.release_name
    $prepared=Test-LocalPath $PreparedRoot -Directory
    $envelope=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($plan.release_envelope)) | ConvertFrom-Json
    # The independently pinned plan authenticates these bytes before Python.
    # Python then verifies the independent Ed25519 signatures and native receipt.
    Hold-ApprovedPayload $prepared $envelope.payload.files $held
    $silo=Join-Path ([Environment]::GetFolderPath('ProgramFiles')) 'SILO'
    New-ManagedDirectory $silo
    $releases=Join-Path $silo 'Releases'
    New-ManagedDirectory $releases
    $release=Join-Path $releases $plan.release_name
    if (Test-Path -LiteralPath $release) {
        # Retry may reuse only a complete protected matching release. Never repair
        # unknown or partially copied bytes in place; retain them for inspection.
        Assert-ManagedDirectory $release
    } else {
        New-ManagedDirectory $release
        foreach ($file in $envelope.payload.files) {
            Test-RelativeName $file.path
            $source=Join-Path $prepared ('payload\'+$file.path.Replace('/','\'))
            $target=Join-Path $release ('payload\'+$file.path.Replace('/','\'))
            [IO.Directory]::CreateDirectory((Split-Path -Parent $target)) | Out-Null
            $incoming=[IO.File]::Open($source,'Open','Read','Read')
            try {
                $outgoing=[IO.File]::Open($target,'CreateNew','Write','None')
                try { $incoming.CopyTo($outgoing); $outgoing.Flush($true) } finally { $outgoing.Dispose() }
            } finally { $incoming.Dispose() }
        }
        foreach ($name in @('release-manifest.json','release-manifest.sha256')) {
            [IO.File]::Copy((Join-Path $prepared $name),(Join-Path $release $name),$false)
        }
        # Keep Internet provenance. Authenticode must be applied before inventory
        # signing; an unsigned managed launcher remains subject to script policy.
        foreach ($script in @(Get-ChildItem -LiteralPath (Join-Path $release 'payload') -Recurse -File -Filter '*.ps1')) {
            Set-Content -LiteralPath ($script.FullName+':Zone.Identifier') -Encoding ASCII -Value "[ZoneTransfer]`r`nZoneId=3"
        }
        & (Join-Path $PSScriptRoot 'Protect-SILORelease.ps1') -ReleaseRoot $release
    }
    # Recheck the protected copy before executing any interpreter from it.
    Hold-ApprovedPayload $release $envelope.payload.files $held
    $launcher=Join-Path $release 'payload\app\installer\Start-SILOManaged.ps1'
    if ((Get-AuthenticodeSignature -FilePath $launcher).Status -ne 'Valid') {
        throw 'The approved managed launcher needs a valid trusted Authenticode signature before activation.'
    }
    # Run only protected verified software, with native loader environment and
    # current directory restricted just as in the ordinary first-stage launcher.
    $python=Join-Path $release 'payload\host\python.exe'
    $entry=Join-Path $release 'payload\app\scripts\install_managed.py'
    $savedEnvironment=@{}
    $savedPath=$env:PATH
    $pushed=$false
    try {
        foreach ($environmentEntry in @(Get-ChildItem Env:)) {
            if ($environmentEntry.Name -like 'QT_*' -or $environmentEntry.Name -like 'PYTHON*' -or
                $environmentEntry.Name -in @('QML_IMPORT_PATH','QML2_IMPORT_PATH','OPENSSL_CONF','OPENSSL_MODULES')) {
                $savedEnvironment[$environmentEntry.Name]=$environmentEntry.Value
                Remove-Item -LiteralPath ('Env:'+ $environmentEntry.Name)
            }
        }
        $env:PATH=[Environment]::SystemDirectory+';'+[Environment]::GetFolderPath('Windows')
        Push-Location -LiteralPath (Join-Path $release 'payload\host')
        $pushed=$true
        $checkArguments=@('-I','-B',$entry,'--plan',$planPath,'--plan-sha256',$ActivationPlanSha256,
                          '--prepared-root',$release,'--source-id',$SourceId,'--user-sid',$identity.User.Value)
        & $python @checkArguments --validate-only
        if ($LASTEXITCODE -ne 0) { throw 'Protected release verification failed; no deployment was enrolled.' }
        & (Join-Path $PSScriptRoot 'Register-SILOAudit.ps1')
        $machine=Join-Path ([Environment]::GetFolderPath('CommonApplicationData')) 'SILO-Security'
        if (-not (Test-Path -LiteralPath $machine)) {
            & $python -I -B (Join-Path $release 'payload\app\scripts\manage_security.py') init-machine
            if ($LASTEXITCODE -ne 0) { throw 'Machine store creation failed; no deployment was enrolled.' }
        }
        & $python @checkArguments
        if ($LASTEXITCODE -ne 0) { throw 'Managed enrollment did not complete. Retain the candidate and inspect machine/audit state before retrying.' }
        if (-not $NoShortcut) {
            $desktop=[Environment]::GetFolderPath('DesktopDirectory')
            $shortcutPath=Join-Path $desktop 'SILO Managed.lnk'
            if (Test-Path -LiteralPath $shortcutPath) {
                Write-Warning 'An existing SILO Managed shortcut was preserved; use the protected launcher or inspect that shortcut.'
            } else {
                $shell=New-Object -ComObject WScript.Shell
                $temporaryShortcut=Join-Path $desktop ('.SILO-'+[Guid]::NewGuid().ToString('N')+'.lnk')
                $shortcut=$shell.CreateShortcut($temporaryShortcut)
                $shortcut.TargetPath=Join-Path ([Environment]::GetFolderPath('Windows')) 'System32\WindowsPowerShell\v1.0\powershell.exe'
                $shortcut.Arguments='-NoLogo -NoProfile -File "'+(Join-Path $release 'payload\app\installer\Start-SILOManaged.ps1')+'" -Interface '+$Interface
                $shortcut.WorkingDirectory=Join-Path $release 'payload\host'
                Set-EvaluationShortcutIcon $shortcut (Join-Path $release 'payload\app\assets\branding\silo.ico')
                $shortcut.Save()
                # Publish without replacing a concurrently created desktop item.
                [IO.File]::Move($temporaryShortcut,$shortcutPath)
            }
        }
        Write-Host 'Managed deployment enrolled. Open SILO Managed from the ordinary, non-elevated target account. No model was launched by installation.'
    } finally {
        if ($pushed) { Pop-Location }
        foreach ($name in $savedEnvironment.Keys) { Set-Item -LiteralPath ('Env:'+ $name) -Value $savedEnvironment[$name] }
        $env:PATH=$savedPath
    }
} finally {
    foreach ($stream in $held) { $stream.Dispose() }
    $planStream.Dispose()
}
