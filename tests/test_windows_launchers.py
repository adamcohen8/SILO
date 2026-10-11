"""Native batch-launcher process contracts; inert child, no model qualification."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(os.name == 'nt', 'Native Windows batch launcher required')
class WindowsTerminalLauncherTests(unittest.TestCase):
    def fixture(self, legacy):
        temporary = tempfile.TemporaryDirectory(prefix='silo launcher ')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        app = root/'payload'/'app'
        app.mkdir(parents=True)
        (app/'scripts').mkdir()
        shutil.copyfile(ROOT/'Start-SILO-Terminal.cmd', app/'Start-SILO-Terminal.cmd')
        (app/'scripts'/'start_windows_terminal.py').write_text(
            'import json,sys;print(json.dumps(sys.argv[1:]));sys.exit(23)', encoding='utf-8')
        python = (app/'artifacts/windows-evaluation/venv/Scripts' if legacy else root/'payload/host')
        python.mkdir(parents=True)
        base = Path(sys.base_prefix)
        archive = base/f'python{sys.version_info.major}{sys.version_info.minor}.zip'
        if not archive.is_file():
            self.skipTest('Matching embedded development interpreter required')
        shutil.copyfile(sys.executable, python/'python.exe')
        for name in (f'python{sys.version_info.major}{sys.version_info.minor}.dll', 'vcruntime140.dll', 'vcruntime140_1.dll'):
            if (base/name).is_file():
                shutil.copyfile(base/name, python/name)
        (python/f'python{sys.version_info.major}{sys.version_info.minor}._pth').write_text(str(archive)+'\n.\n', encoding='utf-8')
        return app

    def check_route(self, legacy):
        app = self.fixture(legacy)
        args = ['--synthetic', 'literal path with spaces', 'caf\u00e9']
        result = subprocess.run([os.environ['COMSPEC'], '/d', '/c', 'call', str(app/'Start-SILO-Terminal.cmd'), *args],
                                capture_output=True, text=True, timeout=15, encoding='utf-8', errors='replace')
        self.assertEqual(result.returncode, 23, result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout), args)

    def test_installed_child_failure_and_literal_arguments_propagate(self):
        self.check_route(False)

    def test_legacy_child_failure_and_literal_arguments_propagate(self):
        self.check_route(True)