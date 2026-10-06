#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$KitRoot,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedManifestSha256
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($KitRoot).TrimEnd([IO.Path]::DirectorySeparatorChar)
function Assert-OrdinaryItem([string]$Path, [bool]$Directory) {
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.PSIsContainer -ne $Directory -or ([int64]$item.Attributes -band 0x441400)) {
        throw 'Test kit contains a reparse/offline/recall or unsupported item.'
    }
}
$ancestor = $root
while ($ancestor) {
    Assert-OrdinaryItem $ancestor $true
    $parent = Split-Path -Parent $ancestor
    if ($parent -eq $ancestor) { break }
    $ancestor = $parent
}
$manifestPath = Join-Path $root 'TEST-KIT-MANIFEST.json'
Assert-OrdinaryItem $manifestPath $false
if ((Get-Item -LiteralPath $manifestPath).Length -gt 1MB -or
    (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedManifestSha256) {
    throw 'Test kit manifest does not match the independently supplied hash.'
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.format_version -ne 1 -or $manifest.source_revision -notmatch '^[0-9a-f]{40}$' -or
    $manifest.scope -ne 'source_and_synthetic_validation_only' -or $manifest.deployment_ready -ne $false -or
    $manifest.files.Count -lt 3 -or $manifest.files.Count -gt 4096) { throw 'Unsupported test kit manifest.' }
$expected = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
$folded = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
$expectedDirectories = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
[void]$expected.Add('TEST-KIT-MANIFEST.json'); [void]$folded.Add('TEST-KIT-MANIFEST.json')
foreach ($file in $manifest.files) {
    if ($file.path -notmatch '^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$' -or
        $file.sha256 -notmatch '^[0-9a-f]{64}$' -or $file.size -lt 1 -or $file.size -gt 8MB -or
        -not $expected.Add($file.path) -or -not $folded.Add($file.path)) { throw 'Ambiguous or unsupported test kit entry.' }
    $components = $file.path.Split('/')
    foreach ($component in $components) {
        if ($component -in @('.', '..') -or $component -match '[. ]$' -or
            $component -match '^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])($|\.)') { throw 'Unsafe test kit path.' }
    }
    $selected = $root
    for ($i = 0; $i -lt $components.Count; $i++) {
        $selected = Join-Path $selected $components[$i]
        Assert-OrdinaryItem $selected ($i -lt $components.Count - 1)
        if ($i -lt $components.Count - 1) { [void]$expectedDirectories.Add(($components[0..$i] -join '/')) }
    }
    if ((Get-Item -LiteralPath $selected).Length -ne $file.size -or
        (Get-FileHash -LiteralPath $selected -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) {
        throw 'Test kit file is missing or changed.'
    }
}
# Inspect children without following a reparse point; recurse only after check.
function Visit-Directory([string]$Path, [string]$Prefix) {
    foreach ($item in Get-ChildItem -LiteralPath $Path -Force) {
        $relative = $Prefix + $item.Name
        Assert-OrdinaryItem $item.FullName $item.PSIsContainer
        if ($item.PSIsContainer) {
            if (-not $expectedDirectories.Contains($relative)) { throw 'Undeclared directory in test kit.' }
            Visit-Directory $item.FullName ($relative + '/')
        } elseif (-not $expected.Contains($relative)) { throw 'Undeclared file in test kit.' }
    }
}
Visit-Directory $root ''
[ordered]@{ source_revision = $manifest.source_revision; test_kit_integrity_verified = $true;
    signature_verified = $false; deployment_ready = $false } | ConvertTo-Json
