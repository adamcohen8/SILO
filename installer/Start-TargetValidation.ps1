#Requires -Version 5.1
<# Read-only inventory + synthetic native fixtures. No dependency installation. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedManifestSha256,
    [Parameter(Mandatory = $true)][string]$PythonExe,
    [ValidateSet('Folders', 'Installer')][string]$Scope = 'Folders'
)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Use native Windows for target validation.' }
$root = Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot 'Verify-TestKit.ps1') -KitRoot $root -ExpectedManifestSha256 $ExpectedManifestSha256
$pythonItem = Get-Item -LiteralPath $PythonExe -Force
if ($pythonItem.PSIsContainer -or ($pythonItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'Select the approved native Python executable.'
}
& $pythonItem.FullName -I -c 'import ctypes,os,sys; sys.exit(0 if os.name=="nt" and ctypes.sizeof(ctypes.c_void_p)==8 and sys.version_info>=(3,11) else 2)'
if ($LASTEXITCODE -ne 0) { throw 'Approved native 64-bit Windows Python 3.11+ is required.' }
& (Join-Path $PSScriptRoot 'Test-Target.ps1')
$runner = if ($Scope -eq 'Folders') { 'validate_windows_folders.py' } else { 'validate_windows_installation.py' }
& $pythonItem.FullName -I -B (Join-Path $root ('scripts\' + $runner))
exit $LASTEXITCODE
