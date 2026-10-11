"""Record source/native fixture results; skips never count as passing acceptance."""
import argparse, datetime, hashlib, json, os, pathlib, sys, time, unittest
sys.dont_write_bytecode = True
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=pathlib.Path, required=True)
parser.add_argument('--pattern', default='test_*.py', help='Comma-separated unittest discovery patterns')
parser.add_argument('--output', type=pathlib.Path, required=True)
args = parser.parse_args()
root = args.source.resolve()
output = args.output.resolve()
if output.exists():
    raise SystemExit('Use a new report path; earlier evidence is preserved.')
if root == output or root in output.parents:
    raise SystemExit('Keep raw evidence outside the source checkout.')
os.chdir(root)
sys.path[:0] = [str(root / name) for name in ('src', 'tests', 'scripts')]
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
clock = time.monotonic()
suite = unittest.TestSuite(unittest.defaultTestLoader.discover(str(root / 'tests'), pattern=pattern) for pattern in args.pattern.split(','))
class RecordingResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.passed_ids=[]
    def addSuccess(self,test):
        super().addSuccess(test)
        self.passed_ids.append(test.id())
result = unittest.TextTestRunner(verbosity=2,resultclass=RecordingResult).run(suite)
summary = {
    'pattern': args.pattern, 'tests_run': result.testsRun,
    'passed': len(result.passed_ids),
    'passed_tests': result.passed_ids,
    'skipped_methods': len({getattr(test,'test_case',test).id() for test, reason in result.skipped}),
    'skipped_cases': len(result.skipped),
    'failures': [{'test': str(test), 'traceback': detail} for test, detail in result.failures],
    'errors': [{'test': str(test), 'traceback': detail} for test, detail in result.errors],
    'skips': [{'test': str(test), 'reason': reason} for test, reason in result.skipped],
    'regressions_passed': result.wasSuccessful() and result.testsRun > 0,
    'deployment_ready': False, 'native_code_acceptance': False,
    'test_driver_sha256': hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
    'python': sys.version, 'os': sys.platform, 'started_utc': started,
    'ended_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'duration_seconds': round(time.monotonic()-clock, 3),
    'source_hashes': {str(p.relative_to(root)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                      for directory in ('src', 'scripts', 'tests') for p in sorted((root/directory).rglob('*.py'))},
}
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
print(json.dumps({k: summary[k] for k in ('pattern','tests_run','passed','duration_seconds','regressions_passed')}))
raise SystemExit(0 if summary['regressions_passed'] else 1)