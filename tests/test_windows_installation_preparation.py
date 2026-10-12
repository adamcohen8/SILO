"""Native PowerShell refusal tests. No activation, trust or model execution."""
import ctypes
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PS = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"


@unittest.skipUnless(os.name == "nt", "Native Windows PowerShell installer fixture")
class WindowsInstallerRefusalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="si-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.install = self.root / "candidate"
        self.env = {k: v for k, v in os.environ.items() if k.upper() != "PSMODULEPATH"}

    def invoke(self, *arguments, script="Install-Evaluation.ps1"):
        # Process-only RemoteSigned is the permitted development test policy.
        return subprocess.run(
            [str(PS), "-NoProfile", "-ExecutionPolicy", "RemoteSigned",
             "-File", str(ROOT / "installer" / script), *map(str, arguments)],
            env=self.env, cwd=self.root, capture_output=True, text=True, timeout=30)

    def denied(self, arguments, message):
        result = self.invoke("-InstallRoot", self.install, *arguments)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message, result.stdout + result.stderr)
        self.assertFalse(self.install.exists(), "Refusal must precede creating an install tree")

    def test_missing_mode_refuses_before_any_installation(self):
        self.denied([], "Choose exactly one")

    def test_conflicting_modes_refuse_before_any_installation(self):
        self.denied(["-PrepareOnly", "-Activate"], "Choose exactly one")

    def test_rollback_refuses_before_any_installation(self):
        self.denied(["-PrepareOnly", "-Rollback"], "Choose exactly one")

    def test_activation_fields_cannot_be_used_for_preparation(self):
        self.denied(["-PrepareOnly", "-ActivationPlan", self.root / "absent.json"],
                    "Activation inputs require -Activate")

    def test_activation_requires_plan_and_independent_digest(self):
        for options in ([], ["-ActivationPlan", self.root / "absent.json"],
                        ["-ActivationPlan", self.root / "absent.json",
                         "-ActivationPlanSha256", "not-a-digest"]):
            with self.subTest(options=options):
                self.denied(["-Activate", *options], "Activation requires a reviewed plan")

    def test_ordinary_user_activation_refuses_before_reading_plan(self):
        if ctypes.windll.shell32.IsUserAnAdmin():
            self.skipTest("Ordinary-user refusal requires a non-elevated test process")
        self.denied(["-Activate", "-ActivationPlan", self.root / "absent.json",
                     "-ActivationPlanSha256", "a" * 64], "approved elevated")

    def test_direct_activation_refuses_ordinary_user_without_machine_changes(self):
        if ctypes.windll.shell32.IsUserAnAdmin():
            self.skipTest("Ordinary-user refusal requires a non-elevated test process")
        result = self.invoke("-PreparedRoot", self.install, "-ActivationPlan",
                             self.root / "absent.json", "-ActivationPlanSha256", "a" * 64,
                             "-SourceId", "a" * 16, script="Activate-SILO.ps1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("elevated PowerShell session", result.stdout + result.stderr)
        self.assertFalse(self.install.exists())

    def test_incomplete_offline_cache_preserves_state_without_active_record(self):
        cache = self.root / "cache"
        cache.mkdir()
        result = self.invoke("-InstallRoot", self.install, "-PrepareOnly", "-Offline",
                             "-CachePath", cache, "-NoLaunch", "-NoShortcut")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Offline cache is missing", result.stdout + result.stderr)
        self.assertEqual(list(cache.iterdir()), [])
        self.assertEqual(list((self.install / "versions").iterdir()), [])
        self.assertEqual(list((self.install / "state").iterdir()), [])
        self.assertFalse((self.install / "active.json").exists())
        self.assertEqual(list(self.install.glob(".bootstrap-*")), [])


if __name__ == "__main__":
    unittest.main()
