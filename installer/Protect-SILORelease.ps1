# Explicit provisioning of one new managed release; never accepts arbitrary trees.
param([Parameter(Mandatory=$true)][string]$ReleaseRoot)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
if (-not ('SILOFileIdentity' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class SILOFileIdentity {
    [StructLayout(LayoutKind.Sequential)] public struct Info {
        public uint Attributes, CreationLow, CreationHigh, AccessLow, AccessHigh,
                    WriteLow, WriteHigh, Volume, SizeHigh, SizeLow, Links, IndexHigh, IndexLow;
    }
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool GetFileInformationByHandle(SafeFileHandle file, out Info info);
    public static void Check(SafeFileHandle file) {
        Info info;
        if (!GetFileInformationByHandle(file,out info) || info.Links != 1 ||
            (info.Attributes & (0x400u | 0x1000u)) != 0)
            throw new InvalidOperationException("Linked or recalled release file refused.");
    }
}
'@
}
$principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Administrator release provisioning required.'
}
$parent=Join-Path ([Environment]::GetFolderPath('ProgramFiles')) 'SILO\Releases'
$root=[IO.Path]::GetFullPath($ReleaseRoot)
if ((Split-Path -Parent $root) -ne [IO.Path]::GetFullPath($parent) -or (Split-Path -Leaf $root) -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$') {
    throw 'Only one named release directly under Program Files SILO Releases is accepted.'
}
$objects=@((Get-Item -LiteralPath (Split-Path -Parent $parent)),(Get-Item -LiteralPath $parent),
           (Get-Item -LiteralPath $root)) + @(Get-ChildItem -LiteralPath $root -Force -Recurse)
foreach ($item in $objects) {
    if ($item.Attributes -band ([IO.FileAttributes]::ReparsePoint -bor [IO.FileAttributes]::Offline)) {
        throw 'Release contains a linked or recalled object; no ACL changes were made.'
    }
    if (-not $item.PSIsContainer) {
        $stream=[IO.File]::Open($item.FullName,'Open','Read','Read')
        try { [SILOFileIdentity]::Check($stream.SafeFileHandle) } finally { $stream.Dispose() }
    }
}
foreach ($item in $objects) {
    $acl=if($item.PSIsContainer){[Security.AccessControl.DirectorySecurity]::new()}else{[Security.AccessControl.FileSecurity]::new()}
    # Public software only. This LPAC RX grant never applies to machine policy,
    # private project keys, prompts, operational documents or output storage.
    $acl.SetSecurityDescriptorSddlForm('O:BAD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;0x1200a9;;;BU)(A;OICI;0x1200a9;;;S-1-15-2-2)')
    Set-Acl -LiteralPath $item.FullName -AclObject $acl
}
Write-Output 'Selected managed release now has administrator ownership and ordinary-user read/execute access. Verify its signed inventory before enrollment.'
