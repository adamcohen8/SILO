"""Nine synthetic parser fixtures; never grants process/deployment readiness."""
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
import unittest


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root / 'src'), str(root / 'tests')]
    import test_documents
    cases = unittest.defaultTestLoader.loadTestsFromTestCase(test_documents.DocumentTests)
    suite = unittest.TestSuite(case for case in cases
                              if case._testMethodName != 'test_binary_source_revalidated_before_reviewed_copy')
    result = unittest.TextTestRunner(verbosity=2, stream=sys.stderr).run(suite)
    passed = result.wasSuccessful() and result.testsRun == 9 and not result.skipped
    print(json.dumps({'synthetic_parser_tests_passed': passed, 'tests_run': result.testsRun,
                      'failures': len(result.failures), 'errors': len(result.errors),
                      'skipped': len(result.skipped), 'process_containment_verified': False,
                      'deployment_ready': False}, indent=2))
    return 0 if passed else 1


if __name__ == '__main__': raise SystemExit(main())
