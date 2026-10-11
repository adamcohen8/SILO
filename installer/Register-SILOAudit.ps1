# Explicit administrative provisioning; no machine policy or log ACL is loosened.
param()
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run the explicit event-source provisioning command as administrator.'
}
if ([Diagnostics.EventLog]::SourceExists('SILO')) {
    if ([Diagnostics.EventLog]::LogNameFromSourceName('SILO','.') -ne 'Application') {
        throw 'Existing SILO source belongs to another log; inspect it.'
    }
} else {
    New-EventLog -LogName Application -Source SILO
}
Write-Output 'SILO Application event source registered. Review log ACL, size, retention and forwarding under host policy; this script changes none of them.'
