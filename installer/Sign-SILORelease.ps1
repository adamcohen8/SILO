# Explicit release-owner operation; no certificate enrollment or automatic signing.
param(
    [Parameter(Mandatory=$true)][string]$PayloadRoot,
    [Parameter(Mandatory=$true)][string]$CertificateThumbprint
)
$ErrorActionPreference = 'Stop'
$certificate = Get-Item -LiteralPath "Cert:\CurrentUser\My\$CertificateThumbprint"
if (-not $certificate.HasPrivateKey) { throw 'Selected signing certificate has no private key.' }
$files = Get-ChildItem -LiteralPath $PayloadRoot -Recurse -File |
    Where-Object { $_.Extension -eq '.ps1' }
if (-not $files) { throw 'No PowerShell bootstrap files found.' }
foreach ($file in $files) {
    if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Refusing linked bootstrap file.' }
    $signature = Set-AuthenticodeSignature -LiteralPath $file.FullName -Certificate $certificate -HashAlgorithm SHA256
    if ($signature.Status -ne 'Valid') { throw "Signing failed: $($file.Name)" }
}
Write-Output 'Bootstrap scripts signed. Build the final inventory and detached manifest after signing.'
