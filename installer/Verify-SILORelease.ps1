# First-stage trust check: run using the organization's already trusted launcher.
param(
    [Parameter(Mandatory=$true)][string]$Bootstrap,
    [Parameter(Mandatory=$true)][string]$ExpectedSignerThumbprint
)
$ErrorActionPreference = 'Stop'
$item = Get-Item -LiteralPath $Bootstrap
if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked bootstrap is forbidden.' }
$signature = Get-AuthenticodeSignature -LiteralPath $item.FullName
if ($signature.Status -ne 'Valid' -or
    $signature.SignerCertificate.Thumbprint -ne $ExpectedSignerThumbprint) {
    throw 'Bootstrap signature does not match the independently configured organization signer.'
}
Write-Output 'Bootstrap signer verified. Continue through the trusted deployment procedure.'
