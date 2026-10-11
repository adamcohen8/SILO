#Requires -Version 5.1
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$InstallationRoot,
      [Parameter(Mandatory=$true)][string]$ManifestSha256)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Native Windows is required.' }
# User-selected roots and adjacent hashes are preparation integrity checks,
# not startup authority. The managed launcher reads fixed protected enrollment.
& (Join-Path $PSScriptRoot 'Start-SILOManaged.ps1') -Interface Desktop
exit $LASTEXITCODE
