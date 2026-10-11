"""Artifact-checker decoder fixtures; fabricated records are not native evidence."""
import hashlib
import io
import json
from pathlib import Path
import unittest
import warnings
import zipfile

from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.milestone import inspect_milestone
from local_ai_appliance.silo_plot import bar_chart

FIXTURES=Path(__file__).resolve().parent/'fixtures/silo-milestone'


class MilestoneCheckerTests(unittest.TestCase):
    def artifact(self,*,boundary='native-lpac-fixed-ntfs-vhd',capacity=108,chart=None,missing_run=False,duplicate=False):
        # Deliberately inert scripts and invented metadata test decoding only.
        # Never execute these bytes or present them as actual native results.
        expected=json.loads((FIXTURES/'expected.json').read_bytes())
        files={'analyze.py':b'# INERT DECODER FIXTURE\n','tests.py':b'# INERT DECODER FIXTURE\n',
            'results.json':json.dumps({'capacity_kg':capacity,'contributions_kg':expected['eligible_contributions_kg'],
                                      'excluded_assets':expected['excluded_assets']}).encode(),
            'report.md':b'108 kg. [source:S1:line:2]',
            'capacity.png':chart or bar_chart(['SYN-001','SYN-002'],[48,60])}
        inputs=[{'staged_path':'inputs/'+name,'sha256':hashlib.sha256((FIXTURES/name).read_bytes()).hexdigest(),
                 'source_reference':f'[source:S{i+1}]'} for i,name in enumerate(
                    ['policy.txt','inventory.csv',*expected['rejected_inputs']])]
        pins=[{'path':p,'sha256':hashlib.sha256(b).hexdigest(),'size':len(b)} for p,b in sorted(files.items())]
        runs=[{'entrypoint':'analyze.py','arguments':[name],'boundary':boundary,
                'script_sha256':hashlib.sha256(files['analyze.py']).hexdigest(),'exit_code':0 if name=='inventory.csv' else 2}
              for name in ['inventory.csv',*expected['rejected_inputs']]]
        runs.append({'entrypoint':'tests.py','arguments':[],'boundary':boundary,
                'script_sha256':hashlib.sha256(files['tests.py']).hexdigest(),'exit_code':0})
        if missing_run: runs.pop(1)
        manifest={'files':pins,'inputs':inputs,'runs':runs}
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as archive:
            for p,b in files.items(): archive.writestr(p,b)
            archive.writestr('silo-manifest.json',json.dumps(manifest))
            if duplicate:
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore',UserWarning); archive.writestr('report.md',files['report.md'])
        return stream.getvalue()

    def test_decoder_accepts_consistent_fixture_but_never_certifies_isolation_or_model(self):
        result=inspect_milestone(self.artifact(),FIXTURES)
        self.assertEqual(result['capacity_kg'],108)
        self.assertFalse(result['full_isolation_acceptance']); self.assertFalse(result['cui_authorized'])
        self.assertIn('requires separate',result['real_model_quality'])

    def test_simulation_missing_negative_run_wrong_result_chart_and_duplicate_refused(self):
        for options in ({'boundary':'simulated-tests-only'},{'missing_run':True},{'capacity':109},
                        {'chart':bar_chart(['SYN-001','SYN-002'],[48,61])},{'duplicate':True}):
            with self.subTest(options=options):
                with self.assertRaises(AccessDenied): inspect_milestone(self.artifact(**options),FIXTURES)


if __name__=='__main__': unittest.main()
