"""Python entrypoint for the separately qualified immutable offline build environment."""
import json
import os
from pathlib import Path
import runpy
import sys

if sys.flags.isolated!=1 or sys.flags.no_site!=1: raise RuntimeError('Isolated no-site startup required')
work,library,manifest,operation,entrypoint=sys.argv[1:]
root=Path(manifest).parent
v=json.loads(Path(manifest).read_text(encoding='utf-8'))
os.chdir(work); sys.dont_write_bytecode=True
sys.path[:]=[library,work]+[str(root/'payload'/p) for p in v['python_paths']]+[p for p in sys.path if p and 'site-packages' not in p]
sys.argv=[entrypoint]
if v['language']=='cpp':
    import subprocess
    command=v['commands']['build']
    args=[entrypoint if a=='{entrypoint}' else a.replace('{payload}',str(root/'payload')) for a in command['arguments']]
    status=subprocess.run([str(root/'payload'/command['executable']),*args],check=False).returncode
    if status:raise SystemExit(status)
    raise SystemExit(subprocess.run([str(Path(work)/'silo_build.exe')],check=False).returncode)
elif operation=='test':
    import unittest
    suite=unittest.defaultTestLoader.discover(str(Path(work)/Path(entrypoint).parent),pattern=Path(entrypoint).name,top_level_dir=work)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun==0:
        print('No tests were discovered; this is not a passed test run.',file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(0 if result.wasSuccessful() else 1)
elif operation=='check':
    import ast
    ast.parse((Path(work)/entrypoint).read_bytes(),filename=entrypoint)
else: runpy.run_path(str(Path(work)/entrypoint),run_name='__main__')
