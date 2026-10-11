"""Opt-in native candidate probes. Skips never establish boundary acceptance.

SILO_NATIVE_TEST_ROOT must name payload/app in a newly prepared synthetic
installation. These fixed developer probes cannot activate model code tools.
"""
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest

from local_ai_appliance.execution_policy import ExecutionPolicy
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.windows_code_runner import WindowsCodeRunner


@unittest.skipUnless(os.name=='nt' and os.environ.get('SILO_NATIVE_TEST_ROOT'),
                     'Native Windows and explicit prepared synthetic installation required')
class NativeCodeRunnerTests(unittest.TestCase):
    def setUp(self):
        root=Path(os.environ['SILO_NATIVE_TEST_ROOT']).resolve()
        from local_ai_appliance.evaluation_install import installed_config
        config=installed_config(root)
        self.runner=WindowsCodeRunner(root,root.parent/'code',Path(config['state_root'])/'code-native-tests')
        self.addCleanup(self.runner.close)
        result=self.probe("print('SYNTHETIC POSITIVE CONTROL')")
        self.assertEqual(result.exit_code,0); self.assertIn('SYNTHETIC POSITIVE CONTROL',result.stdout)
        self.assertFalse(any(self.runner.state.iterdir()))

    def probe(self,body,**limits):
        return self.runner._execute_candidate({'probe.py':body.encode()},{'control.txt':b'SYNTHETIC INPUT'},
                    'probe.py',(),ExecutionPolicy(**limits))

    def test_candidate_control_cannot_activate_generated_code(self):
        self.assertFalse(self.runner.available)
        with self.assertRaises(AccessDenied): self.runner.execute({}, {},'probe.py',(),ExecutionPolicy())

    def test_input_and_runtime_readonly_and_child_denial(self):
        result=self.probe("""import json,sys,subprocess
from pathlib import Path
checks={}
for name,path in [('input',Path('inputs/control.txt')),('runtime',Path(sys.executable))]:
    try:
        with path.open('r+b'): pass
        checks[name]=False
    except PermissionError: checks[name]=True
try:
    subprocess.run([sys.executable,'-I','-S','-c','pass'],check=True,timeout=2)
    checks['child']=False
except OSError as e: checks['child']=getattr(e,'winerror',None)==367
print(json.dumps(checks))
""")
        self.assertEqual(result.exit_code,0)
        self.assertEqual(json.loads(result.stdout),{'input':True,'runtime':True,'child':True})

    def test_unrelated_user_file_is_unreadable(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'synthetic-secret.txt'; path.write_text('SYNTHETIC PRIVATE CONTROL')
            body=f"from pathlib import Path\np=Path({str(path)!r})\ntry:\n p.read_bytes()\nexcept PermissionError:\n print('DENIED')\nelse:\n raise RuntimeError('Outside read succeeded')\n"
            self.assertEqual(path.read_text(),'SYNTHETIC PRIVATE CONTROL')
            result=self.probe(body)
            self.assertEqual(result.exit_code,0); self.assertEqual(result.stdout.strip(),'DENIED')

    def test_loopback_denial_with_reachable_host_control(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0)); listener.listen()
            address=listener.getsockname()
            with socket.create_connection(address,timeout=2): pass
            body=f"import socket\ntry:\n socket.create_connection({address!r},timeout=2)\nexcept PermissionError:\n print('DENIED')\nelse:\n raise RuntimeError('Loopback connection succeeded')\n"
            result=self.probe(body)
            self.assertEqual(result.exit_code,0); self.assertEqual(result.stdout.strip(),'DENIED')

    def test_timeout_kills_and_cleans_owned_execution(self):
        with self.assertRaises(TimeoutError): self.probe('while True: pass',timeout_seconds=1)
        self.assertFalse(any(self.runner.state.iterdir()))

    def test_cancel_waits_for_owned_cleanup_and_refuses_late_result(self):
        results=[]; errors=[]
        def execute():
            try: results.append(self.probe('while True: pass',timeout_seconds=60))
            except Exception as error: errors.append(error)
        thread=threading.Thread(target=execute); thread.start()
        try:
            deadline=time.monotonic()+40
            while self.runner.active is None and thread.is_alive() and time.monotonic()<deadline:
                time.sleep(.1)
            self.assertIsNotNone(self.runner.active)
        finally:
            self.runner.cancel(); self.runner.wait(); thread.join(5)
        self.assertFalse(thread.is_alive()); self.assertEqual(results,[])
        self.assertTrue(errors); self.assertFalse(any(self.runner.state.iterdir()))

    def test_combined_output_limit_kills_and_cleans(self):
        with self.assertRaises(OSError):
            self.probe("import sys\nsys.stdout.write('x'*40000);sys.stdout.flush()\nsys.stderr.write('y'*40000);sys.stderr.flush()")
        self.assertFalse(any(self.runner.state.iterdir()))

    def test_memory_limit_with_positive_startup_control(self):
        result=self.probe("chunks=[]\ntry:\n for _ in range(640): chunks.append(bytearray(1024*1024))\nexcept MemoryError:\n print('MEMORY DENIED')\nelse:\n print('UNBOUNDED')",timeout_seconds=30)
        self.assertTrue(result.exit_code!=0 or 'MEMORY DENIED' in result.stdout)
        self.assertNotIn('UNBOUNDED',result.stdout)
        self.assertFalse(any(self.runner.state.iterdir()))

    def test_fixed_disk_exhaustion_with_bounded_cleanup(self):
        result=self.probe("""import errno
from pathlib import Path
p=Path('growth.txt')
try:
    with p.open('wb') as f:
        for _ in range(20): f.write(b'x'*(1024*1024)); f.flush()
except OSError as e:
    if e.errno==errno.ENOSPC or getattr(e,'winerror',None)==112: print('DISK DENIED')
    else: raise
else: print('UNBOUNDED')
finally: p.unlink(missing_ok=True)
""",timeout_seconds=30)
        self.assertEqual(result.exit_code,0); self.assertEqual(result.stdout.strip(),'DISK DENIED')
        self.assertFalse(any(self.runner.state.iterdir()))


if __name__=='__main__': unittest.main()
