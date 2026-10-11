#Requires -Version 5.1
<# Portable syntax/archive checks. These do not qualify Windows ACLs or execution. #>
[CmdletBinding()]
param([string]$PythonArchive)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$scripts = @(Get-ChildItem -LiteralPath (Join-Path $root 'installer') -Filter '*.ps1')
$scripts += Get-Item -LiteralPath $PSCommandPath
foreach ($script in $scripts) {
    $tokens = $null; $errors = $null
    [Management.Automation.Language.Parser]::ParseFile($script.FullName, [ref]$tokens, [ref]$errors) | Out-Null
    if ($errors.Count) { throw ('PowerShell syntax failed: '+$script.Name) }
}
. (Join-Path $root 'installer/Evaluation-Common.ps1')
# Resolve these before ZipFile.Open can lazily load dependent assemblies.
# This reproduces interpreter extraction in a fresh Windows PowerShell 5.1 process.
foreach ($archiveType in @([IO.Compression.ZipArchive], [IO.Compression.ZipArchiveMode],
                            [IO.Compression.ZipFile], [IO.Compression.ZipFileExtensions])) {
    if (-not $archiveType) { throw 'Pinned archive support was not initialized.' }
}
$bad = @('../escape', '/absolute', 'C:/absolute', 'a\b', 'a:stream', 'a//b',
         'NUL', 'COM1.txt', 'LPT9', 'a.', 'a ')
foreach ($name in $bad) {
    $denied = $false
    try { Test-RelativeName $name } catch { $denied = $true }
    if (-not $denied) { throw ('Unsafe path accepted: '+$name) }
}
Test-RelativeName 'Lib/site-packages/package/__init__.py'
$temporary = Join-Path ([IO.Path]::GetTempPath()) ('local-ai-bootstrap-test-'+[Guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($temporary) | Out-Null
$cases = @(
    @{names=@('python.exe'); attributes=0; rejected=$false},
    @{names=@('../escape'); attributes=0; rejected=$true},
    @{names=@('a','A'); attributes=0; rejected=$true},
    @{names=@('link'); attributes=(0xA000 -shl 16); rejected=$true}
)
try {
    $index = 0
    foreach ($case in $cases) {
        $index++
        $archive = Join-Path $temporary ($index.ToString()+'.zip')
        $zip = [IO.Compression.ZipFile]::Open($archive, [IO.Compression.ZipArchiveMode]::Create)
        try {
            foreach ($name in $case.names) {
                $entry = $zip.CreateEntry($name)
                $entry.ExternalAttributes = $case.attributes
                $output = $entry.Open()
                try { $bytes = [Text.Encoding]::ASCII.GetBytes('Inert synthetic bytes'); $output.Write($bytes, 0, $bytes.Length) }
                finally { $output.Dispose() }
            }
        } finally { $zip.Dispose() }
        $pin = @{size=(Get-Item -LiteralPath $archive).Length; sha256=(Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()}
        $target = Join-Path $temporary ('expanded-'+$index)
        [IO.Directory]::CreateDirectory($target) | Out-Null
        $rejected = $false
        try { Expand-PythonArchive $archive $target $pin } catch { $rejected = $true }
        if ($rejected -ne $case.rejected) { throw 'Synthetic archive acceptance did not match its expected outcome.' }
        if (-not $case.rejected) {
            $pin.sha256 = '0'*64
            $tamperTarget = Join-Path $temporary 'wrong-digest'
            [IO.Directory]::CreateDirectory($tamperTarget) | Out-Null
            $denied = $false
            try { Expand-PythonArchive $archive $tamperTarget $pin } catch { $denied = $true }
            if (-not $denied -or @(Get-ChildItem -LiteralPath $tamperTarget -Force).Count) {
                throw 'Unverified interpreter bytes reached extraction.'
            }
        }
    }
    if ($PythonArchive) {
        $profile = Get-Content -LiteralPath (Join-Path $root 'profiles/windows-evaluation-installer.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        $target = Join-Path $temporary 'official-python'
        [IO.Directory]::CreateDirectory($target) | Out-Null
        Expand-PythonArchive $PythonArchive $target $profile.python
        if (-not (Test-Path -LiteralPath (Join-Path $target 'python.exe'))) { throw 'Pinned interpreter extraction failed.' }
    }
    @{scripts_parsed=$scripts.Count; unsafe_paths_denied=$bad.Count; archive_cases=$cases.Count;
      digest_denied_before_extraction=$true; official_archive_checked=[bool]$PythonArchive;
      native_Windows_acceptance='not_run'} | ConvertTo-Json
} finally {
    # Retire only this invocation's fresh synthetic test directory.
    Remove-Item -LiteralPath $temporary -Recurse -Force
}
