"""Pinned entrypoint inside the native runner; never run on the host as fallback."""
import os
from pathlib import Path
import runpy
import sys

# Host supplies fixed work/input/library paths, never executable or shell text.
work,inputs,library,entrypoint,*args=sys.argv[1:]
if sys.flags.isolated != 1 or sys.flags.no_site != 1:
    raise RuntimeError('Contained Python requires verified isolated/no-site startup')
os.chdir(work)
sys.path[:]=[library,work]+[p for p in sys.path if p and 'site-packages' not in p]
sys.dont_write_bytecode=True
sys.argv=[entrypoint]+[str(Path(inputs)/arg) for arg in args]
runpy.run_path(str(Path(work)/entrypoint),run_name='__main__')
