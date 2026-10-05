#Requires -Version 5.1
<#
.SYNOPSIS
Read-only target inventory for Local AI Appliance development.
.DESCRIPTION
Prints JSON to stdout. Does not install software, change policy, probe the
network, read documents, or collect host/user identifiers. Missing capabilities
are reported as missing or unknown, never as successful security validation.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Run this inspection on the target Windows computer.' }

$report = [ordered]@{
    schema_version = 1
    collected_utc = [DateTime]::UtcNow.ToString('o')
    inspection_only = $true
    windows_validation = 'not_performed'
    isolation_validation = 'not_performed'
    installation_ready = $false
}

try {
    $osInfo = Get-CimInstance Win32_OperatingSystem
    $report.os = [ordered]@{
        caption = $osInfo.Caption
        version = $osInfo.Version
        build = $osInfo.BuildNumber
        architecture = $osInfo.OSArchitecture
        ram_gib = [math]::Round($osInfo.TotalVisibleMemorySize / 1MB, 1)
    }
} catch { $report.os = @{ status = 'unknown' } }

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$report.elevated = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

$features = [ordered]@{}
foreach ($featureName in @('Microsoft-Windows-Subsystem-Linux', 'VirtualMachinePlatform')) {
    try {
        $feature = Get-WindowsOptionalFeature -Online -FeatureName $featureName
        $features[$featureName] = [string]$feature.State
    } catch { $features[$featureName] = 'unknown (may require elevation)' }
}
$report.features = $features

$wslCommand = Get-Command wsl.exe -ErrorAction SilentlyContinue
$report.wsl_command_present = ($null -ne $wslCommand)
$wslPackage = Get-AppxPackage -Name MicrosoftCorporationII.WindowsSubsystemForLinux -ErrorAction SilentlyContinue
$report.wsl_store_package_present = ($null -ne $wslPackage)
# Avoid invoking an uninstalled WSL launcher, which can offer installation.
# MSI/inbox installations without this package are conservatively left unknown.
if ($wslCommand -and $wslPackage) {
    $versionOutput = & $wslCommand.Source --version 2>&1
    $report.wsl_version_exit_code = $LASTEXITCODE
    $report.wsl_version = (($versionOutput | Out-String) -replace "`0", '').Trim()
    # Report a count only: distro names may identify unrelated workloads.
    $distroOutput = & $wslCommand.Source --list --quiet 2>&1
    if ($LASTEXITCODE -eq 0) {
        $clean = (($distroOutput | Out-String) -replace "`0", '')
        $report.existing_distro_count = @($clean.Split("`n") | Where-Object { $_.Trim() }).Count
    } else { $report.existing_distro_count = 'unknown' }
} else { $report.wsl_version = 'not queried without an installed WSL Store package' }
$report.existing_wslconfig = Test-Path -LiteralPath (Join-Path $env:USERPROFILE '.wslconfig')
$report.hyperv_firewall_cmdlets_present = ($null -ne (Get-Command Get-NetFirewallHyperVVMSetting -ErrorAction SilentlyContinue))

$gpuCommand = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
$report.nvidia_smi_present = ($null -ne $gpuCommand)
if ($gpuCommand) {
    $gpuOutput = & $gpuCommand.Source --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits 2>&1
    $report.gpu_query_exit_code = $LASTEXITCODE
    if ($LASTEXITCODE -eq 0) { $report.gpus = @($gpuOutput | ForEach-Object { [string]$_ }) }
}

$report | ConvertTo-Json -Depth 6
