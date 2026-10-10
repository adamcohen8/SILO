"""Run native synthetic fixtures; reject skips and non-Windows qualification."""

import ctypes
import json
import os
from pathlib import Path
import sys
sys.dont_write_bytecode = True
import unittest


def main():
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        print(json.dumps({"native_tests_passed": False, "deployment_ready": False,
                          "reason": "Native 64-bit Windows is required"}))
        return 2
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_windows_native.py")
    result = unittest.TextTestRunner(verbosity=2, stream=sys.stderr).run(suite)
    passed = result.wasSuccessful() and result.testsRun == 14 and not result.skipped
    print(json.dumps({"native_tests_passed": passed, "tests_run": result.testsRun,
                      "failures": len(result.failures), "errors": len(result.errors),
                      "skipped": len(result.skipped), "deployment_ready": False,
                      "scope": "synthetic Windows folder fixtures only"}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
