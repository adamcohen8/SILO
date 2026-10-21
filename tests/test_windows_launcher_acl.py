"""Native launcher ACL unit checks; no provisioning, ACL writes or inference."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PS = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"


@unittest.skipUnless(os.name == "nt" and PS.is_file(), "Native Windows PowerShell ACL checks")
class WindowsLauncherAclTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="silo-launcher-acl-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.file = self.root / "inert.txt"
        self.file.write_text("Synthetic ACL fixture; never executed", encoding="utf-8")
        source = (ROOT / "installer/Start-SILOManaged.ps1").read_text(encoding="utf-8-sig")
        start = source.index("function Assert-AdminProtection(")
        end = source.index("\n# This first stage", start)
        # Isolate the reviewed function as in other native PowerShell unit tests.
        # The provider-backed descriptor is changed only in memory; no Set-Acl.
        fixture = r"""
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
foreach($name in @('Microsoft.PowerShell.Utility','Microsoft.PowerShell.Security','Microsoft.PowerShell.Management')) {
    Import-Module -Name (Join-Path $PSHOME ('Modules\'+$name+'\'+$name+'.psd1')) -Force
}
$script:fixtureAcl=Get-Acl -LiteralPath $args[0]
$script:fixtureAcl.SetSecurityDescriptorSddlForm($args[1])
function Get-Acl { param([string]$LiteralPath) return $script:fixtureAcl }
""" + source[start:end] + r"""
Assert-AdminProtection 'unit-only-no-file-open' ($args[2] -ceq 'public')
Write-Output 'allowed'
"""
        self.script = self.root / "check.ps1"
        self.script.write_text(fixture, encoding="utf-8-sig")
        self.env = {key: value for key, value in os.environ.items()
                    if key.upper() != "PSMODULEPATH"}

    def check_acl(self, sddl, *, public, allowed, refusal=None):
        before = self.file.read_bytes()
        result = subprocess.run(
            [str(PS), "-NoProfile", "-ExecutionPolicy", "RemoteSigned",
             "-File", str(self.script), str(self.file), sddl,
             "public" if public else "private"],
            env=self.env, cwd=self.root, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode == 0, allowed, result.stdout + result.stderr)
        if allowed:
            self.assertIn("allowed", result.stdout)
        else:
            self.assertIn(refusal, result.stdout + result.stderr)
            self.assertNotIn("IdentityNotMappedException", result.stderr)
        self.assertEqual(self.file.read_bytes(), before)

    def test_public_runtime_allows_restricted_package_sid_rx(self):
        self.check_acl("O:SYG:SYD:P(A;;FA;;;SY)(A;;FA;;;BA)"
                       "(A;;0x1200a9;;;BU)(A;;0x1200a9;;;S-1-15-2-2)",
                       public=True, allowed=True)

    def test_private_store_allows_only_expected_readers(self):
        self.check_acl("O:SYG:SYD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;0x1200a9;;;BU)",
                       public=False, allowed=True)

    def test_restricted_package_sid_is_rejected_for_private_storage(self):
        self.check_acl("O:SYG:SYD:P(A;;FA;;;SY)(A;;0x1200a9;;;S-1-15-2-2)",
                       public=False, allowed=False,
                       refusal="Ordinary users must have read/execute access only")

    def test_ordinary_write_is_rejected(self):
        self.check_acl("O:SYG:SYD:P(A;;FA;;;SY)(A;;FA;;;BU)",
                       public=True, allowed=False,
                       refusal="Ordinary users must have read/execute access only")

    def test_unexpected_trustee_is_rejected(self):
        self.check_acl("O:SYG:SYD:P(A;;FA;;;SY)(A;;0x1200a9;;;BG)",
                       public=True, allowed=False,
                       refusal="Ordinary users must have read/execute access only")

    def test_deny_entry_is_rejected(self):
        self.check_acl("O:SYG:SYD:P(D;;GW;;;BU)(A;;FA;;;SY)",
                       public=True, allowed=False, refusal="Unexpected deployment ACL")

    def test_ordinary_owner_is_rejected(self):
        self.check_acl("O:BUG:SYD:P(A;;FA;;;SY)(A;;0x1200a9;;;BU)",
                       public=True, allowed=False,
                       refusal="Release must be owned by SYSTEM or Administrators")


if __name__ == "__main__":
    unittest.main()
