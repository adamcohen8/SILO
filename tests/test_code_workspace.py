"""Host authority tests with a simulated runner; no generated code executes."""
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

from local_ai_appliance.agent import Source
from local_ai_appliance.code_workspace import CodeWorkspace,RunResult,code_path
from local_ai_appliance.execution_policy import DisabledExecutionService,ExecutionPolicy
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.silo_plot import bar_chart
from local_ai_appliance.code_artifacts import png_pixels,png_preview
from local_ai_appliance.workspace import Workspace

ROOT=Path(__file__).resolve().parents[1]


class SimulatedRunner:
    available=True
    def __init__(self): self.results=[]; self.cancelled=False; self.closed=False
    def execute(self,files,inputs,entrypoint,arguments,policy):
        self.results.append((files,inputs,entrypoint,arguments))
        # Deliberately no exec, subprocess, compile, or actual calculation.
        # The result is clearly labelled simulation, not native acceptance.
        files={**files,'results.json':b'{"capacity_kg":108}',
            'capacity.png':bar_chart(['SYN-001','SYN-002'],[48,60]),
            'report.md':b'Synthetic expected total is 108 kg. [source:S1:line:2]\n'}
        return RunResult(0,'simulated result','',tuple(sorted(files.items())),'simulated-tests-only')
    def cancel(self): self.cancelled=True
    def close(self): self.closed=True


@unittest.skipUnless(os.name=='posix','Portable authority fixture uses the POSIX broker')
class CodeWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve(); self.reference=self.root/'ref'; self.reference.mkdir()
        self.destination=self.root/'dest'; self.destination.mkdir()
        self.original=(ROOT/'tests/fixtures/silo-milestone/policy.txt').read_bytes()
        (self.reference/'policy.txt').write_bytes(self.original)
        self.workspace=Workspace(); self.addCleanup(self.workspace.close)
        self.ro=self.workspace.grant(self.reference,'read-only'); self.rw=self.workspace.grant(self.destination,'editable')
        self.source=Source('S1',self.ro.id,'policy.txt',hashlib.sha256(self.original).hexdigest(),1,7,self.original.decode())
        self.runner=SimulatedRunner(); self.code=CodeWorkspace(self.workspace,self.runner,configuration='test-simulation')
        self.addCleanup(self.code.close)

    def executed(self):
        self.code.stage(self.source,'policy.txt'); self.code.write('analyze.py','# inert simulated entrypoint')
        self.code.run('analyze.py')

    def export(self):
        return self.code.prepare_export(self.rw.id,'artifact-set.zip')['export_id']

    def test_staging_preserves_exact_bytes_and_authority(self):
        item=self.code.stage(self.source,'policy.txt')
        self.assertEqual(item['sha256'],self.source.sha256)
        self.assertEqual(self.code.inputs['policy.txt'],self.original)
        for path in ('../escape.py','inputs/policy.txt','C:/host.py','CON.py','a:stream.py','silo_plot.py'):
            with self.assertRaises(AccessDenied): self.code.write(path,'anything')
        self.assertEqual((self.reference/'policy.txt').read_bytes(),self.original)

    def test_edit_compare_hash_and_case_alias_rejection(self):
        item=self.code.write('test.py','old')
        with self.assertRaises(AccessDenied): self.code.write('test.py','new')
        self.code.write('test.py','new',item['sha256'])
        with self.assertRaises(AccessDenied): self.code.write('TEST.py','aliased')
        self.assertEqual(self.code.read('test.py')['text'],'new')

    def test_disabled_execution_and_shell_arguments_cannot_run(self):
        self.code.write('test.py','# no execution')
        self.code.runner=DisabledExecutionService()
        with self.assertRaises(AccessDenied): self.code.run('test.py')
        self.code.runner=self.runner
        for args in (['-c'],['a','b'],['../host.py']):
            with self.assertRaises(AccessDenied): self.code.run('test.py',args)
        self.assertEqual(self.runner.results,[])

    def test_exact_artifact_set_host_review_atomic_zip_and_replay(self):
        self.executed(); identifier=self.export()
        self.assertEqual(list(self.destination.iterdir()),[])
        with self.assertRaises(AccessDenied): self.code.approve(identifier)
        reviewed=self.code.review(identifier); self.code.approve(identifier)
        data=(self.destination/'artifact-set.zip').read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),reviewed.sha256)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            manifest=json.loads(archive.read('silo-manifest.json'))
            self.assertEqual(manifest['inputs'][0]['sha256'],self.source.sha256)
            self.assertEqual(manifest['runs'][0]['boundary'],'simulated-tests-only')
            self.assertEqual(json.loads(archive.read('results.json'))['capacity_kg'],108)
            for pin in manifest['files']:
                self.assertEqual(hashlib.sha256(archive.read(pin['path'])).hexdigest(),pin['sha256'])
        with self.assertRaises(AccessDenied): self.code.approve(identifier)

    def test_source_change_revocation_and_collisions_refuse_export(self):
        self.executed(); identifier=self.export(); self.code.review(identifier)
        (self.reference/'policy.txt').write_text('changed')
        with self.assertRaises(AccessDenied): self.code.approve(identifier)
        (self.reference/'policy.txt').write_bytes(self.original)
        self.code.run('analyze.py'); identifier=self.export()
        (self.destination/'artifact-set.zip').write_bytes(b'existing')
        with self.assertRaises(AccessDenied): self.code.review(identifier)
        self.workspace.revoke(self.ro.id)
        with self.assertRaises(AccessDenied): self.code.run('analyze.py')

    def test_edit_or_new_staging_invalidates_review_and_execution_evidence(self):
        self.executed(); identifier=self.export(); self.code.review(identifier)
        self.code.write('analyze.py','# changed',self.code.read('analyze.py')['sha256'])
        with self.assertRaises(AccessDenied): self.code.approve(identifier)
        with self.assertRaises(AccessDenied): self.export()

    def test_budget_invalid_output_and_cancelled_late_result(self):
        self.executed()
        with self.assertRaises(AccessDenied): self.code.write('huge.py','x'*(1024*1024+1))
        for _ in range(7): self.code.run('analyze.py')
        with self.assertRaises(AccessDenied): self.code.run('analyze.py')
        self.code.cancel()
        with self.assertRaises(AccessDenied): self.export()

    def test_cancel_while_blocked_runner_prevents_acceptance(self):
        self.code.write('test.py','# inert')
        entered,release=threading.Event(),threading.Event(); errors=[]
        original=self.runner.execute
        def block(*args): entered.set(); release.wait(3); return original(*args)
        self.runner.execute=block
        def run():
            try: self.code.run('test.py')
            except BaseException as error: errors.append(error)
        thread=threading.Thread(target=run); thread.start()
        try: self.assertTrue(entered.wait(2)); self.code.cancel()
        finally: release.set(); thread.join(4)
        self.assertIsInstance(errors[0],AccessDenied); self.assertEqual(self.code.runs,[])

    def test_unregistered_or_malformed_artifacts_are_refused(self):
        self.executed()
        self.runner.execute=lambda *a:RunResult(0,'','',(('../host.py',b'bad'),),'simulated')
        with self.assertRaises(AccessDenied): self.code.run('analyze.py')
        self.assertTrue(self.code.cancelled)
        self.assertEqual(self.code.runs,[])
        with self.assertRaises(AccessDenied): self.export()


class ChartTests(unittest.TestCase):
    def test_png_opens_with_bounded_pixels_and_visible_bar_preview(self):
        data=bar_chart(['SYN-001','SYN-002'],[48,60])
        width,height,raw=png_pixels(data)
        self.assertEqual((width,height),(640,360))
        self.assertIn('#',png_preview(data)); self.assertIn(b'SYN-001=48 kg',data)
        bad=bytearray(data); bad[-1]^=1
        with self.assertRaises(AccessDenied): png_pixels(bytes(bad))
        for values in ([float('nan')],[-1],[float('inf')]):
            with self.assertRaises(ValueError): bar_chart(['SYN-001'],values)


if __name__=='__main__': unittest.main()
