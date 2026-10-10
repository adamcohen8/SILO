#Requires -Version 5.1
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$InstallationRoot,
      [Parameter(Mandatory=$true)][string]$ManifestSha256)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Native Windows is required.' }
. (Join-Path $PSScriptRoot 'Evaluation-Common.ps1')
# Verify the interpreter, dependencies, source, runtime and model before Python starts.
Test-EvaluationRelease $InstallationRoot $ManifestSha256
$payload = Join-Path $InstallationRoot 'payload'
$python = Join-Path $payload 'host\pythonw.exe'
$entry = Join-Path $payload 'app\scripts\start_windows_ui.py'
Start-Process -FilePath $python -ArgumentList @('-I', '-B', ('"'+$entry+'"')) -WorkingDirectory $payload
