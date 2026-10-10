# Shared by the evaluation bootstrap and pre-Python launch gate. No policy bypass.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Test-LocalPath([string]$Path, [switch]$Directory) {
    $absolute = [IO.Path]::GetFullPath($Path)
    if ($absolute -notmatch '^[A-Za-z]:\\[^\\]' -or $absolute.Contains('%') -or $absolute.Contains('"')) {
        throw 'Use an ordinary absolute local path without percent or quote characters.'
    }
    $drive = New-Object IO.DriveInfo([IO.Path]::GetPathRoot($absolute))
    if ($drive.DriveType -ne [IO.DriveType]::Fixed -or $drive.DriveFormat -ne 'NTFS') {
        throw 'Evaluation installation storage requires a fixed local NTFS drive.'
    }
    $ancestor = $absolute
    while ($ancestor) {
        if (Test-Path -LiteralPath $ancestor) {
            $item = Get-Item -LiteralPath $ancestor -Force
            if ([int64]$item.Attributes -band 0x441400) { throw 'Reparse, offline and recalled storage is unavailable.' }
        }
        $parent = Split-Path -Parent $ancestor
        if ($parent -eq $ancestor) { break }
        $ancestor = $parent
    }
    if (Test-Path -LiteralPath $absolute) {
        $item = Get-Item -LiteralPath $absolute -Force
        if ($Directory -and -not $item.PSIsContainer) { throw 'Expected a local directory.' }
        if (-not $Directory -and $item.PSIsContainer) { throw 'Expected a local file.' }
    }
    return $absolute
}

function New-PrivateDirectory([string]$Path) {
    $pathValue = Test-LocalPath $Path -Directory
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    if (-not (Test-Path -LiteralPath $pathValue)) {
        if (-not (Test-Path -LiteralPath (Split-Path -Parent $pathValue))) { throw 'The private directory parent must exist.' }
        $acl = New-Object Security.AccessControl.DirectorySecurity
        $acl.SetAccessRuleProtection($true, $false)
        $acl.SetOwner($sid)
        foreach ($principal in @($sid, (New-Object Security.Principal.SecurityIdentifier('S-1-5-18')),
                                     (New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')))) {
            $rule = New-Object Security.AccessControl.FileSystemAccessRule($principal, 'FullControl',
                     'ContainerInherit, ObjectInherit', 'None', 'Allow')
            $acl.AddAccessRule($rule)
        }
        $directoryInfo = New-Object IO.DirectoryInfo($pathValue)
        if ($PSVersionTable.PSEdition -eq 'Core') { [IO.FileSystemAclExtensions]::Create($directoryInfo, $acl) | Out-Null }
        else { $directoryInfo.Create($acl) }
    }
    $existing = Get-Acl -LiteralPath $pathValue
    if (-not $existing.AreAccessRulesProtected -or $existing.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $sid.Value) {
        throw 'Existing installation storage must be privately owned with a protected ACL; it was not changed.'
    }
    $rules = @($existing.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
    $allowed = @($sid.Value, 'S-1-5-18', 'S-1-5-32-544')
    if ($rules.Count -ne 3) { throw 'Existing private storage has unexpected ACL entries; it was not changed.' }
    $seen = @{}
    foreach ($rule in $rules) {
        if ($rule.IdentityReference.Value -notin $allowed -or $rule.AccessControlType -ne 'Allow' -or
            $rule.FileSystemRights -ne 'FullControl' -or $rule.IsInherited -or
            [int]$rule.InheritanceFlags -ne 3 -or [int]$rule.PropagationFlags -ne 0 -or $seen.ContainsKey($rule.IdentityReference.Value)) {
            throw 'Existing private storage has unexpected permissions; it was not changed.'
        }
        $seen[$rule.IdentityReference.Value] = $true
    }
    return $pathValue
}

function Test-RelativeName([string]$Name) {
    if (-not $Name -or $Name.Length -gt 4096 -or $Name -match '[\\:<>"|?*\x00-\x1f\x7f]' -or $Name.Split('/').Count -gt 64) {
        throw 'Unsafe payload path.'
    }
    foreach ($component in $Name.Split('/')) {
        if (-not $component -or $component -in @('.', '..') -or $component -match '[ .]$' -or
            $component -match '^(CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9\u00b9\u00b2\u00b3]|LPT[1-9\u00b9\u00b2\u00b3])(?:\.|$)') {
            throw 'Unsafe payload path component.'
        }
    }
}

function Test-PinnedFile([string]$Path, $Pin) {
    $pathValue = Test-LocalPath $Path
    $item = Get-Item -LiteralPath $pathValue -Force
    if ($Pin.sha256 -notmatch '^[0-9a-f]{64}$' -or $item.Length -ne [long]$Pin.size -or
        (Get-FileHash -LiteralPath $pathValue -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Pin.sha256) {
        throw 'A file failed its reviewed size or SHA-256 check.'
    }
}

function Get-PinnedDownload($Pin, [string]$Cache, [switch]$Offline) {
    Test-RelativeName $Pin.filename
    if ($Pin.filename.Contains('/') -or $Pin.url -notmatch '^https://' -or [long]$Pin.size -le 0) { throw 'Invalid bootstrap pin.' }
    $target = Join-Path $Cache $Pin.filename
    if (Test-Path -LiteralPath $target) { Test-PinnedFile $target $Pin; return $target }
    if ($Offline) { throw ('Offline cache is missing ' + $Pin.filename) }
    $partial = $target + '.partial'
    $offset = 0L
    if (Test-Path -LiteralPath $partial) {
        Test-LocalPath $partial | Out-Null
        $offset = (Get-Item -LiteralPath $partial).Length
    }
    if ($offset -gt [long]$Pin.size) { throw 'Oversized bootstrap download; inspect the cache before retrying.' }
    if ($offset -lt [long]$Pin.size) {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $request = [Net.HttpWebRequest]::Create($Pin.url)
        $request.Timeout = 30000
        $request.ReadWriteTimeout = 30000
        $request.AllowAutoRedirect = $false
        if ($offset) { $request.AddRange($offset) }
        $response = $request.GetResponse()
        try {
            if ($response.ResponseUri.Scheme -ne 'https' -or [int]$response.StatusCode -notin @(200, 206) -or ($offset -and
                ([int]$response.StatusCode -ne 206 -or $response.Headers['Content-Range'] -notlike "bytes $offset-*"))) {
                throw 'Unsafe bootstrap redirect or invalid download resumption.'
            }
            $mode = if (Test-Path -LiteralPath $partial) { [IO.FileMode]::Append } else { [IO.FileMode]::CreateNew }
            $output = [IO.File]::Open($partial, $mode, [IO.FileAccess]::Write, [IO.FileShare]::None)
            $inputStream = $response.GetResponseStream()
            try {
                $buffer = New-Object byte[] (1024 * 1024)
                while (($count = $inputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                    $offset += $count
                    if ($offset -gt [long]$Pin.size) { throw 'Oversized bootstrap download.' }
                    $output.Write($buffer, 0, $count)
                }
                $output.Flush($true)
            } finally { $output.Dispose(); $inputStream.Dispose() }
        } finally { $response.Dispose() }
    }
    Test-PinnedFile $partial $Pin
    [IO.File]::Move($partial, $target)
    return $target
}

function Expand-PythonArchive([string]$Archive, [string]$Destination, $Pin) {
    # Hold a read-only sharing handle through hashing and extraction. On Windows
    # this denies concurrent writes/deletion, including in a selected shared cache.
    $file = [IO.File]::Open($Archive, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    $stream = $null
    try {
        $sha = [Security.Cryptography.SHA256]::Create()
        try { $digest = ([BitConverter]::ToString($sha.ComputeHash($file))).Replace('-', '').ToLowerInvariant() }
        finally { $sha.Dispose() }
        if ($Pin.sha256 -notmatch '^[0-9a-f]{64}$' -or $file.Length -ne [long]$Pin.size -or $digest -ne $Pin.sha256) {
            throw 'Interpreter archive changed before extraction.'
        }
        $file.Position = 0
        $stream = [IO.Compression.ZipArchive]::new($file, [IO.Compression.ZipArchiveMode]::Read, $true)
        $total = 0L; $seen = @{}
        if ($stream.Entries.Count -gt 10000) { throw 'Oversized interpreter archive.' }
        foreach ($entry in $stream.Entries) {
            $name = $entry.FullName.TrimEnd('/')
            Test-RelativeName $name
            $total += $entry.Length
            if ($total -gt 1024L * 1024 * 1024 -or $seen.ContainsKey($name) -or
                (($entry.ExternalAttributes -shr 16) -band 0xF000) -notin @(0, 0x8000, 0x4000)) { throw 'Unsafe interpreter archive.' }
            $seen[$name] = $true
            $target = Join-Path $Destination $name.Replace('/', '\')
            if ($entry.FullName.EndsWith('/')) { [IO.Directory]::CreateDirectory($target) | Out-Null; continue }
            [IO.Directory]::CreateDirectory((Split-Path -Parent $target)) | Out-Null
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $false)
        }
    } finally { if ($stream) { $stream.Dispose() }; $file.Dispose() }
}

function Test-EvaluationRelease([string]$Root, [string]$ManifestSha256) {
    Test-LocalPath $Root -Directory | Out-Null
    $manifest = Join-Path $Root 'release-manifest.json'
    if ($ManifestSha256 -notmatch '^[0-9a-f]{64}$' -or (Get-Item -LiteralPath $manifest).Length -gt 8 * 1024 * 1024) { throw 'Invalid release manifest.' }
    Test-PinnedFile $manifest @{size=(Get-Item -LiteralPath $manifest).Length; sha256=$ManifestSha256}
    $value = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($value.format_version -ne 1 -or $value.evaluation_only -ne $true -or $value.deployment_ready -ne $false -or
        $value.files.Count -lt 1 -or $value.files.Count -gt 10000) { throw 'Invalid evaluation release.' }
    $expected = @{}; $directories = @{}
    foreach ($entry in $value.files) {
        Test-RelativeName $entry.path
        if ($expected.ContainsKey($entry.path)) { throw 'Duplicate release file.' }
        $expected[$entry.path] = $entry
        $components = $entry.path.Split('/')
        for ($i = 1; $i -lt $components.Count; $i++) { $directories[($components[0..($i-1)] -join '/')] = $true }
    }
    $payload = Join-Path $Root 'payload'
    $queue = New-Object 'Collections.Generic.Queue[string]'
    $queue.Enqueue($payload)
    $seen = @{}
    while ($queue.Count) {
        $directory = $queue.Dequeue()
        Test-LocalPath $directory -Directory | Out-Null
        foreach ($item in @(Get-ChildItem -LiteralPath $directory -Force)) {
            $relative = $item.FullName.Substring($payload.Length + 1).Replace('\', '/')
            if ($item.PSIsContainer) {
                if (-not $directories.ContainsKey($relative)) { throw 'Undeclared payload directory.' }
                Test-LocalPath $item.FullName -Directory | Out-Null
                $queue.Enqueue($item.FullName)
            } else {
                if (-not $expected.ContainsKey($relative) -or $seen.ContainsKey($relative) -or
                    $expected[$relative].path -cne $relative) { throw 'Undeclared or aliased payload file.' }
                Test-PinnedFile $item.FullName $expected[$relative]
                $seen[$relative] = $true
            }
        }
    }
    if ($seen.Count -ne $expected.Count) { throw 'Installed payload is incomplete.' }
}
