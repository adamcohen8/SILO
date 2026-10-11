import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.windows_code_runner import WindowsCodeRunner,BOUNDARY_TESTS,qualify
from local_ai_appliance.windows_code_storage import provision_script,require_clean_state
from local_ai_appliance.configuration_catalog import authorize_configuration

ROOT=Path(__file__).resolve().parents[1]


class BoundaryTests(unittest.TestCase):
    def record(self):
        self.configuration={'release_sha256':'independently_tested_release','policy':{'version':1,'memory_mib':512,'network':'deny'}}
        return {'format_version':1,'scope':'synthetic_code_evaluation','native_os':'Windows',
            'configuration':self.configuration,'checks':{p:{'status':'passed','evidence_sha256':'a'*64} for p in BOUNDARY_TESTS}}

    def test_complete_record_requires_reviewed_digest_and_every_native_check(self):
        data=json.dumps(self.record()).encode(); sha=hashlib.sha256(data).hexdigest()
        self.assertEqual(qualify(data,sha,self.configuration)['scope'],'synthetic_code_evaluation')
        with self.assertRaises(AccessDenied): qualify(data,'b'*64,self.configuration)
        with self.assertRaises(AccessDenied): qualify(data,sha,{'release_sha256':'changed'})
        with self.assertRaises(AccessDenied): qualify(data,sha,self.configuration|{'policy':{'memory_mib':2048}})
        record=self.record(); record['configuration']['policy']['version']=True
        boolean=json.dumps(record).encode()
        with self.assertRaises(AccessDenied):
            qualify(boolean,hashlib.sha256(boolean).hexdigest(),{'release_sha256':'independently_tested_release',
                'policy':{'version':1,'memory_mib':512,'network':'deny'}})
        for state in ('failed','skipped','pending',True):
            record=self.record(); record['checks']['disk']['status']=state
            changed=json.dumps(record).encode()
            with self.assertRaises(AccessDenied): qualify(changed,hashlib.sha256(changed).hexdigest(),self.configuration)

    def test_missing_check_and_observation_reports_cannot_enable_code(self):
        record=self.record(); del record['checks']['ipc']
        for value in (record,{'scope':'candidate_observations_only'},self.record()|{'format_version':True}):
            data=json.dumps(value).encode()
            with self.assertRaises(AccessDenied): qualify(data,hashlib.sha256(data).hexdigest(),self.configuration)

    def test_no_portable_runner_fallback_and_only_synthetic_code_catalog_scope(self):
        if os.name!='nt':
            with self.assertRaises(AccessDenied): WindowsCodeRunner(ROOT,ROOT,ROOT)
        authorize_configuration(ROOT,'nemotron-4090-cp314-evaluation-1',operation='launch',workload='code_evaluation')
        for scope in ('public','cui'):
            with self.assertRaises(RuntimeError):
                authorize_configuration(ROOT,'nemotron-4090-cp314-evaluation-1',operation='launch',workload='code_evaluation',data_scope=scope)
        with self.assertRaises(RuntimeError):
            authorize_configuration(ROOT,'nemotron-4090-cp312-evaluation-1',operation='launch',workload='code_evaluation')

    def test_owned_fixed_volume_command_and_stale_lease_refusal(self):
        script=provision_script('C:\\owned\\workspace.vhd','Z',16)
        self.assertIn('type=fixed',script); self.assertIn('maximum=16',script)
        self.assertNotIn('select disk',script); self.assertNotIn('clean',script)
        for image,drive,size in [('C:\\bad"\nselect disk 0.vhd','Z',16),('x.vhd','C',16),('x.vhd','Z',True)]:
            with self.assertRaises(AccessDenied): provision_script(image,drive,size)
        with tempfile.TemporaryDirectory() as temp:
            state=Path(temp).resolve(); require_clean_state(state)
            (state/'lease.json').write_text('{}')
            with self.assertRaises(AccessDenied): require_clean_state(state)


if __name__=='__main__': unittest.main()
