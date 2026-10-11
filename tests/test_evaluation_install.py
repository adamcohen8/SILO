import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from local_ai_appliance.evaluation_install import HTTPSRedirects, copy_pinned, obtain, prepare, release_id, unpack, verify_release


class EvaluationInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source, self.destination, self.cache, self.state = [self.root/n for n in ('source','transaction','cache','state')]
        for path in (self.source,self.destination,self.cache,self.state): path.mkdir()
        self.pins = {}
        self.cpu_pins = {}

    def cached(self, name, content):
        (self.cache/name).write_bytes(content)
        return {'filename':name,'size':len(content),'sha256':hashlib.sha256(content).hexdigest(),
                'url':'https://example.invalid/'+name}

    def archive(self, name, files):
        out = io.BytesIO()
        with zipfile.ZipFile(out,'w') as stream:
            for path, content in files.items(): stream.writestr(path, content)
        return self.cached(name,out.getvalue())

    def fixture(self):
        (self.source/'src/local_ai_appliance').mkdir(parents=True)
        (self.source/'scripts').mkdir()
        (self.source/'installer').mkdir()
        (self.source/'profiles').mkdir()
        (self.source/'tests').mkdir()
        (self.source/'assets/branding').mkdir(parents=True)
        for name in ('AGENTS.md','Start-LocalAI.cmd','Start-SILO-Terminal.cmd','src/local_ai_appliance/evaluation_install.py',
                     'src/local_ai_appliance/__init__.py','scripts/contained_agent_worker.py','tests/synthetic_documents.py',
                     'assets/branding/silo.png','assets/branding/silo.ico'):
            (self.source/name).write_bytes(b'' if '__init__' in name else b'Inert public fixture; never execute.')
        python = self.archive('python.zip', {'python.exe':b'Inert interpreter', 'pythonw.exe':b'Inert GUI interpreter',
                    'python314.zip':b'Inert standard library', 'python314._pth':b'python314.zip\n.\n'})
        wheel = {**self.archive('agent.whl', {'agent/__init__.py':b'', 'agent/module.py':b'Inert fixture'}),'ui_only':False}
        ui = {**self.archive('ui.whl', {'Qt/module.py':b'Inert UI fixture'}),'ui_only':True}
        profile = {'format_version':1,'evaluation_only':True,'deployment_ready':False,'python':python,'wheels':[wheel,ui]}
        (self.source/'profiles/windows-evaluation-installer.json').write_text(json.dumps(profile))
        runtime = self.archive('runtime.zip', {'llama-server.exe':b'Inert runtime'})
        runtime.update(name=runtime.pop('filename'), role='runtime')
        model = self.cached('model.gguf',b'Inert model')
        model.update(name=model.pop('filename'), role='model')
        self.pins = {'assets':[runtime,model], 'profile_id':'synthetic',
                     'extracted_runtime':[{'path':'llama-server.exe','size':len(b'Inert runtime'),'sha256':hashlib.sha256(b'Inert runtime').hexdigest()}]}
        cpu_runtime = self.archive('cpu-runtime.zip', {'llama-server.exe':b'Inert CPU runtime'})
        cpu_runtime.update(name=cpu_runtime.pop('filename'), role='runtime')
        self.cpu_pins = {'assets':[cpu_runtime], 'extracted_runtime':[
            {'path':'llama-server.exe','size':len(b'Inert CPU runtime'),
             'sha256':hashlib.sha256(b'Inert CPU runtime').hexdigest()}]}
        (self.source/'profiles/windows-cpu-inference-assets.json').write_text(json.dumps(self.cpu_pins))
        for name in ('nemotron-30b-4090-assets.json','nemotron-30b-4090-candidate.json'):
            (self.source/'profiles'/name).write_text(json.dumps(self.pins))
        (self.source/'profiles/windows-python312-wheels.json').write_text('{}')
        (self.source/'profiles/model-catalog.json').write_text('{}')
        # Synthetic publisher pins use a test-only independently supplied policy digest.
        catalog=json.loads((Path(__file__).resolve().parents[1]/'profiles/configuration-catalog.json').read_text())
        for entry in catalog['configurations']:
            for pin in entry['profile_pins']:
                pin['sha256']=hashlib.sha256((self.source/pin['path']).read_bytes()).hexdigest()
        (self.source/'profiles/configuration-catalog.json').write_text(json.dumps(catalog))

    def build(self, **options):
        with patch('local_ai_appliance.evaluation_install.inference_pins', return_value=self.pins), \
             patch('local_ai_appliance.evaluation_install.cpu_runtime_pins', return_value=self.cpu_pins), \
             patch('local_ai_appliance.configuration_catalog.CATALOG_SHA256',
                   hashlib.sha256((self.source/'profiles/configuration-catalog.json').read_bytes()).hexdigest()), \
             patch('local_ai_appliance.evaluation_install.shutil.disk_usage') as space, \
             patch('urllib.request.urlopen', side_effect=AssertionError('Offline preparation must not contact a network')):
            space.return_value.free = 100*1024**3
            return prepare(self.source,self.destination,self.cache,self.state,offline=True,progress=lambda _:None,**options)

    def test_application_update_does_not_download_or_reinstall_models(self):
        self.fixture()
        (self.cache/'model.gguf').unlink()
        models = self.state/'models'; models.mkdir()
        saved = models/'previous.gguf'; saved.write_bytes(b'Inert previously installed model')
        result = self.build(include_model=False)
        self.assertEqual(list(models.iterdir()), [saved])
        self.assertEqual(saved.read_bytes(), b'Inert previously installed model')
        verify_release(self.destination, result['manifest_sha256'])

    def test_offline_preparation_supplies_interpreters_source_workers_and_ui_separately(self):
        self.fixture()
        result = self.build()
        self.assertFalse(result['deployment_ready'])
        self.assertEqual(result['native_acceptance'],'not_run')
        payload = self.destination/'payload'
        for path in ('host/python.exe','host/pythonw.exe','worker/python.exe','worker/contained_agent_worker.py',
                     'host/Lib/site-packages/Qt/module.py','worker/Lib/site-packages/agent/module.py',
                     'worker/Lib/site-packages/local_ai_appliance/evaluation_install.py','app/AGENTS.md',
                     'app/Start-LocalAI.cmd',
                     'app/artifacts/inference/runtime-b11433-cpu-x64/llama-server.exe',
                     'app/profiles/windows-cpu-inference-assets.json',
                     'app/assets/branding/silo.png','app/assets/branding/silo.ico'):
            self.assertTrue((payload/path).is_file(),path)
        self.assertFalse((payload/'worker/Lib/site-packages/Qt').exists())
        model_pin = next(p for p in self.pins['assets'] if p['role'] == 'model')
        model = self.state/'models'/(model_pin['sha256']+'.gguf')
        self.assertEqual(model.read_bytes(), b'Inert model')
        self.assertFalse((payload/'app/artifacts/inference/downloads').exists())
        model.unlink()
        self.assertIn('Lib/site-packages', (payload/'host/python314._pth').read_text())
        self.assertEqual((payload/'code/python314._pth').read_text(),'python314.zip\n.\n')
        self.assertFalse((payload/'code/Lib/site-packages').exists())
        self.assertTrue((payload/'app/Start-SILO-Terminal.cmd').is_file())
        verify_release(self.destination,result['manifest_sha256'])
        icon = payload/'app/assets/branding/silo.ico'
        original_icon = icon.read_bytes()
        icon.write_bytes(b'Changed shortcut icon')
        with self.assertRaises(RuntimeError): verify_release(self.destination,result['manifest_sha256'])
        icon.write_bytes(original_icon)
        (payload/'worker/python.exe').write_bytes(b'Changed')
        with self.assertRaises(RuntimeError): verify_release(self.destination,result['manifest_sha256'])

    def test_inventory_authentication_extra_files_and_state_separation(self):
        self.fixture(); result=self.build()
        (self.state/'AGENTS.md').write_text('User preferences may change.')
        verify_release(self.destination,result['manifest_sha256'])
        with self.assertRaises(RuntimeError): verify_release(self.destination,'0'*64)
        extra=self.destination/'payload/host/injected.pth'; extra.write_text('Inert hook')
        with self.assertRaises(RuntimeError): verify_release(self.destination,result['manifest_sha256'])

    def test_offline_missing_corrupt_or_oversized_cached_assets_fail_closed(self):
        pin=self.cached('test.bin',b'Good')
        (self.cache/'test.bin').write_bytes(b'Bad')
        with self.assertRaises(RuntimeError): obtain(pin,self.cache,offline=True)
        (self.cache/'test.bin').unlink()
        with patch('urllib.request.urlopen',side_effect=AssertionError('No network')):
            with self.assertRaisesRegex(RuntimeError,'missing'): obtain(pin,self.cache,offline=True)

    def test_archive_escape_link_alias_and_wheel_hook_rejected(self):
        for names in (['../escape'], ['C:/escape'], ['NUL'], ['a','a'], ['a','A'], ['hook.pth']):
            out=io.BytesIO()
            with zipfile.ZipFile(out,'w') as stream:
                for name in names: stream.writestr(name,b'Inert')
            path=self.root/'unsafe.zip'; path.write_bytes(out.getvalue())
            with tempfile.TemporaryDirectory(dir=self.root) as target:
                with self.assertRaises((RuntimeError,ValueError)):
                    unpack(path,Path(target),wheel=True)
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as stream:
            info=zipfile.ZipInfo('link'); info.external_attr=(0o120777<<16)
            stream.writestr(info,b'target')
        (self.root/'link.zip').write_bytes(out.getvalue())
        with self.assertRaises(RuntimeError): unpack(self.root/'link.zip',self.root/'out')

    def test_source_identity_and_no_existing_transaction_overwrite(self):
        self.fixture(); before=release_id(self.source)
        (self.source/'AGENTS.md').write_text('Changed preferences')
        self.assertNotEqual(before,release_id(self.source))
        self.build()
        with self.assertRaisesRegex(RuntimeError,'empty transaction'): self.build()

    def test_wheel_cli_wrappers_are_not_installed(self):
        pin = self.archive('cli.whl', {'jsonpatch.py':b'Inert library', 'jsonpatch.data/scripts/jsonpatch':b'Inert CLI'})
        target = self.root/'vendored'
        unpack(self.cache/pin['filename'], target, wheel=True)
        self.assertEqual((target/'jsonpatch.py').read_bytes(), b'Inert library')
        self.assertFalse((target/'jsonpatch.data').exists())

    def test_zero_byte_and_valid_range_download_resumption(self):
        for prefix in (b'', b'Go'):
            pin = self.cached('resumed.bin', b'Good')
            (self.cache/'resumed.bin').unlink()
            partial = self.cache/'resumed.bin.partial'
            partial.write_bytes(prefix)
            response = io.BytesIO(b'Good'[len(prefix):])
            response.url = pin['url']
            response.status = 206 if prefix else 200
            response.headers = {'Content-Range': 'bytes 2-3/4'} if prefix else {}
            with patch('urllib.request.build_opener') as build:
                build.return_value.open.return_value = response
                result = obtain(pin, self.cache, progress=lambda _:None)
                request = build.return_value.open.call_args.args[0]
                self.assertEqual(request.get_header('Range'), 'bytes=2-' if prefix else None)
            self.assertEqual(result.read_bytes(), b'Good')
            self.assertFalse(partial.exists())
            result.unlink()

    def test_server_ignoring_range_and_tls_downgrade_are_denied(self):
        pin = self.cached('resumed.bin', b'Good')
        (self.cache/'resumed.bin').unlink()
        partial = self.cache/'resumed.bin.partial'
        partial.write_bytes(b'Go')
        response = io.BytesIO(b'Good'); response.url = pin['url']; response.status = 200; response.headers = {}
        with patch('urllib.request.build_opener') as build:
            build.return_value.open.return_value = response
            with self.assertRaisesRegex(RuntimeError, 'resumption'):
                obtain(pin, self.cache, progress=lambda _:None)
        self.assertEqual(partial.read_bytes(), b'Go')
        with self.assertRaisesRegex(RuntimeError, 'HTTPS'):
            HTTPSRedirects().redirect_request(None, None, 302, '', {}, 'http://example.invalid/download')

    def test_shared_cache_drift_is_rejected_before_extraction_or_execution(self):
        self.fixture()
        real_obtain = obtain
        def drift_after_check(item, *args, **kwargs):
            path = real_obtain(item, *args, **kwargs)
            if path.name == 'python.zip':
                path.write_bytes(b'Altered after the cache check')
            return path
        with patch('local_ai_appliance.evaluation_install.obtain', side_effect=drift_after_check):
            with self.assertRaisesRegex(RuntimeError, 'private copy'):
                self.build()
        self.assertFalse((self.destination/'payload/host/python.exe').exists())
        self.assertFalse((self.destination/'release-manifest.json').exists())

    def test_private_copy_rechecks_actual_bytes_and_never_replaces_existing_file(self):
        pin = self.cached('copy.bin', b'Good')
        target = self.destination/'copy.bin'
        copy_pinned(self.cache/'copy.bin', target, pin)
        self.assertEqual(target.read_bytes(), b'Good')
        with self.assertRaises(FileExistsError): copy_pinned(self.cache/'copy.bin', target, pin)
        (self.cache/'copy.bin').write_bytes(b'Evil')
        with self.assertRaisesRegex(RuntimeError, 'private copy'):
            copy_pinned(self.cache/'copy.bin', self.destination/'changed.bin', pin)


if __name__ == '__main__': unittest.main()
