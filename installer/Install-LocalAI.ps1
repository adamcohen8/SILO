#Requires -Version 5.1
<#
.SYNOPSIS
Offline installation framework candidate. Does not activate an AI appliance.
.DESCRIPTION
Plan verifies payload bytes. Explicit development modes stage bytes in private
storage, keep checkpoints, and roll back owned payloads. No downloads, feature
changes, firewall changes, payload execution, scheduled tasks, or reboot occur.
#>
[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Stage', 'Status', 'PauseForReboot', 'Resume', 'Rollback')]
    [string]$Mode = 'Plan',
    [Parameter(Mandatory = $true)][string]$BundlePath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ManifestSha256,
    [Parameter(Mandatory = $true)][string]$PythonExe,
    [string]$StateRoot = (Join-Path $env:LOCALAPPDATA 'LocalAI-Appliance-Validation'),
    [switch]$DevelopmentCandidate
)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'This entry point requires Windows.' }
if ($Mode -ne 'Plan' -and -not $DevelopmentCandidate) {
    throw 'Production activation is unavailable. Explicit development candidate mode is required.'
}
$pythonItem = Get-Item -LiteralPath $PythonExe -Force
if ($pythonItem.PSIsContainer -or ($pythonItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'Select an approved native Python executable.'
}
& $pythonItem.FullName -I -c 'import ctypes,os,sys; sys.exit(0 if os.name=="nt" and ctypes.sizeof(ctypes.c_void_p)==8 and sys.version_info>=(3,11) else 2)'
if ($LASTEXITCODE -ne 0) { throw 'Approved native 64-bit Windows Python 3.11+ is required.' }
# Work only in a reviewed source/test kit. No bundle-supplied code is executed.
$entryPoint = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts\install_framework.py'
$frameworkArgs = @($entryPoint, $Mode.ToLowerInvariant(), '--bundle', $BundlePath,
                   '--manifest-sha256', $ManifestSha256, '--windows-validation')
if ($Mode -eq 'PauseForReboot') { $frameworkArgs[1] = 'pause-for-reboot' }
if ($Mode -ne 'Plan') {
    $absoluteRoot = [IO.Path]::GetFullPath($StateRoot)
    if ($absoluteRoot -notmatch '^[A-Za-z]:\\[^\\]') { throw 'Select private local drive storage.' }
    $driveInfo = New-Object IO.DriveInfo([IO.Path]::GetPathRoot($absoluteRoot))
    if ($driveInfo.DriveType -ne [IO.DriveType]::Fixed -or $driveInfo.DriveFormat -ne 'NTFS') {
        throw 'State storage requires a fixed local NTFS drive.'
    }
    # Refuse cloud/reparse ancestors before creating anything. Native opens and
    # ACL checks in the Python candidate must check again through held handles.
    $ancestor = $absoluteRoot
    while ($ancestor) {
        if (Test-Path -LiteralPath $ancestor) {
            $item = Get-Item -LiteralPath $ancestor -Force
            if (-not $item.PSIsContainer -or ([int64]$item.Attributes -band 0x441400)) {
                throw 'State storage has a reparse/offline/recall ancestor.'
            }
        }
        $parent = Split-Path -Parent $ancestor
        if ($parent -eq $ancestor) { break }
        $ancestor = $parent
    }
    if (-not (Test-Path -LiteralPath $absoluteRoot)) {
        if ($Mode -ne 'Stage') { throw 'No state storage exists for this operation.' }
        if (-not (Test-Path -LiteralPath (Split-Path -Parent $absoluteRoot))) {
            throw 'State storage must be a new child of an existing approved local directory.'
        }
        # Supply the private ACL at directory creation, rather than first
        # creating an inherited/public directory and tightening it afterward.
        $acl = New-Object Security.AccessControl.DirectorySecurity
        $acl.SetAccessRuleProtection($true, $false)
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $acl.SetOwner($identity.User)
        foreach ($sid in @($identity.User, (New-Object Security.Principal.SecurityIdentifier('S-1-5-18')),
                           (New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')))) {
            $rule = New-Object Security.AccessControl.FileSystemAccessRule($sid, 'FullControl',
                'ContainerInherit, ObjectInherit', 'None', 'Allow')
            $acl.AddAccessRule($rule)
        }
        # Windows PowerShell 5.1/.NET Framework overload. PowerShell 7 hosts use
        # FileSystemAclExtensions; neither branch changes existing ACLs.
        $directory = New-Object IO.DirectoryInfo($absoluteRoot)
        if ($PSVersionTable.PSEdition -eq 'Core') {
            [IO.FileSystemAclExtensions]::Create($directory, $acl)
        } else { $directory.Create($acl) }
    }
    $frameworkArgs += @('--state-root', $absoluteRoot, '--development')
}
if ($Mode -in @('PauseForReboot', 'Resume')) {
    $boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')
    $frameworkArgs += @('--boot-id', $boot)
}
& $pythonItem.FullName @frameworkArgs
exit $LASTEXITCODE
