"""Collect native candidate observations; never fabricate an acceptance digest.

Run on a synthetic, prepared standalone Windows installation. Untested network,
IPC, resource and lifecycle cases remain pending and cannot enable code tools.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from local_ai_appliance.execution_policy import ExecutionPolicy
from local_ai_appliance.windows_code_runner import WindowsCodeRunner,BOUNDARY_TESTS


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if os.name!='nt':
        print('Native Windows required; no generated code or native probe was executed.')
        return 2
    if args.output.exists(): raise RuntimeError('Use a new observation report path')
    from local_ai_appliance.evaluation_install import installed_config
    config=installed_config(ROOT)
    if config is None: raise RuntimeError('Standalone CPython 3.14 installation required')
    runner=WindowsCodeRunner(ROOT,ROOT.parent/'code',Path(config['state_root'])/'code-runs')
    report={'format_version':1,'scope':'candidate_observations_only','configuration':runner.configuration,
            'native_os':'Windows','code_tools_enabled':False,
            'checks':{name:{'status':'pending'} for name in sorted(BOUNDARY_TESTS)}}
    # Fixed developer-authored script, never model output. This initial probe
    # exercises functional write/read, immutable inputs/runtime, and child denial.
    probe='''import json,sys,subprocess
from pathlib import Path
checks={}
checks['input_read']=Path('inputs/control.txt').read_bytes()==b'SYNTHETIC CONTROL'
Path('result.txt').write_text('SYNTHETIC OUTPUT')
for name,path in [('inputs_readonly',Path('inputs/control.txt')),('runtime_readonly',Path(sys.executable))]:
    try:
        with path.open('r+b'): pass
        checks[name]=False
    except PermissionError: checks[name]=True
try:
    subprocess.run([sys.executable,'-I','-S','-c','pass'],check=True,timeout=2)
    checks['child_process']=False
except OSError as e: checks['child_process']=getattr(e,'winerror',None)==367
print(json.dumps(checks))
'''
    try:
        result=runner._execute_candidate({'probe.py':probe.encode()},{'control.txt':b'SYNTHETIC CONTROL'},
                                          'probe.py',(),ExecutionPolicy(timeout_seconds=10))
        if result.exit_code==0:
            checks=json.loads(result.stdout)
            for name in ('inputs_readonly','runtime_readonly','child_process'):
                report['checks'][name]={'status':'passed' if checks.get(name) is True else 'failed',
                    'evidence_sha256':hashlib.sha256(result.stdout.encode()).hexdigest()}
            report['functional_control']=checks.get('input_read') is True and dict(result.files).get('result.txt')==b'SYNTHETIC OUTPUT'
        else: report['functional_control']=False
        report['cleanup_observed']=not any(runner.state.iterdir())
    except Exception as error:
        report['functional_control']=False; report['failure_type']=type(error).__name__
    finally:
        runner.close()
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 0 if report.get('functional_control') else 1


if __name__=='__main__': raise SystemExit(main())
