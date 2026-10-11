"""Native validator dependencies must resolve under the documented -I command."""
from pathlib import Path
import subprocess
import sys
import tempfile
import importlib.util
import unittest

ROOT=Path(__file__).resolve().parents[1]


class ModelValidatorCliTests(unittest.TestCase):
    def test_isolated_cli_loads_support_before_refusing_an_uninstalled_root(self):
        with tempfile.TemporaryDirectory(prefix='silo-validator-cli-') as temp:
            run=subprocess.run([sys.executable,'-I','-B',str(ROOT/'scripts/validate_windows_model.py'),
                '--root',str(ROOT),'--output',str(Path(temp)/'result.json'),'--model-id','synthetic'],
                capture_output=True,text=True,timeout=30)
            self.assertNotEqual(run.returncode,0)
            self.assertIn('Standalone disposable installation required',run.stderr)
            self.assertNotIn('ModuleNotFoundError',run.stderr)
            self.assertFalse((Path(temp)/'result.json').exists())


    @unittest.skipUnless(importlib.util.find_spec('PySide6'), 'Optional Qt validator dependency required')
    def test_isolated_qt_cli_loads_support_before_refusing_an_uninstalled_root(self):
        with tempfile.TemporaryDirectory(prefix='silo-qt-validator-cli-') as temp:
            evidence=Path(temp)/'new-evidence'
            run=subprocess.run([sys.executable,'-I','-B',str(ROOT/'scripts/validate_windows_ui.py'),
                '--root',str(ROOT),'--evidence',str(evidence),'--model-id','synthetic'],
                capture_output=True,text=True,timeout=30)
            self.assertNotEqual(run.returncode,0)
            self.assertIn('A disposable standalone installation is required.',run.stderr)
            self.assertNotIn('ModuleNotFoundError',run.stderr)
            self.assertFalse(evidence.exists())


if __name__=='__main__':unittest.main()
