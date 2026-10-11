import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

from local_ai_appliance.asset_integrity import digest_file, entries, inference_pins, verify_inference, verify_tree
from local_ai_appliance.windows_session import WindowsSession

ROOT = Path(__file__).resolve().parents[1]


class AssetIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root/'profiles').mkdir()
        for name in ('nemotron-30b-4090-assets.json', 'nemotron-30b-4090-candidate.json',
                     'configuration-catalog.json', 'windows-python312-wheels.json'):
            shutil.copyfile(ROOT/'profiles'/name, self.root/'profiles'/name)
        self.inference = self.root/'artifacts/inference'
        self.inference.mkdir(parents=True)
        self.lock = inference_pins(self.root)

    def write_lock(self):
        (self.inference/'verified-assets.json').write_text(json.dumps(self.lock))

    def test_modified_ordinary_file_hashes_without_false_identity_change(self):
        path = self.root/'modified.txt'
        path.write_bytes(b'Original synthetic bytes')
        before = path.stat()
        expected = b'Edited synthetic bytes'
        path.write_bytes(expected)
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 10_000_000))
        self.assertEqual(digest_file(path), hashlib.sha256(expected).hexdigest())

    def test_same_size_mutation_with_restored_mtime_during_hash_is_rejected(self):
        path = self.root/'changed-during-read.txt'
        path.write_bytes(b'Original synthetic bytes')
        before = path.stat()
        def mutate():
            path.write_bytes(b'Changed! synthetic bytes')
            os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        with self.assertRaisesRegex(RuntimeError, 'Software changed'):
            digest_file(path, cancel=mutate)

    def test_empty_inventory_regression_before_any_executable_can_be_returned(self):
        self.lock['extracted_runtime'] = []
        self.write_lock()
        runtime = self.inference/'runtime-b11433-cuda12.4'
        runtime.mkdir()
        (runtime/'llama-server.exe').write_bytes(b'Inert unverified replacement.')
        session = WindowsSession.__new__(WindowsSession)
        session.root, session.cancelled = self.root, threading.Event()
        with self.assertRaisesRegex(RuntimeError, 'nonempty'):
            session.verify_assets()

    def test_omitted_or_altered_server_and_duplicate_entries_are_denied(self):
        original = self.lock['extracted_runtime']
        for replacement in ([e for e in original if e['path'] != 'llama-server.exe'],
                            [{**e, 'sha256': '0'*64} if e['path']=='llama-server.exe' else e for e in original],
                            original+[original[0]]):
            self.lock['extracted_runtime'] = replacement
            self.write_lock()
            with self.assertRaises(RuntimeError):
                verify_inference(self.root)

    def test_reviewed_lock_cannot_be_replaced_with_a_self_consistent_download_lock(self):
        path = self.root/'profiles/nemotron-30b-4090-assets.json'
        path.write_text(json.dumps({**self.lock, 'extracted_runtime': []}))
        with self.assertRaisesRegex(RuntimeError, 'reviewed inference lock'):
            inference_pins(self.root)

    def test_complete_synthetic_tree_and_model_then_tampering(self):
        data, model_data = b'Inert runtime fixture', b'Inert model fixture'
        entry = {'path':'llama-server.exe','size':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        expected = {'profile_id':'synthetic','runtime_source_revision':'a'*40,'extracted_runtime':[entry],
                    'assets':[{'role':'model','name':'fixture.gguf','size':len(model_data),'sha256':hashlib.sha256(model_data).hexdigest()}]}
        self.lock = expected
        self.write_lock()
        model = expected['assets'][0]
        (self.root/'profiles/nemotron-30b-4090-candidate.json').write_text(json.dumps({
            'profile_id':'synthetic','runtime':{'source_revision':'a'*40},
            'model':{'file':model['name'],'size':model['size'],'sha256':model['sha256']}}))
        runtime = self.inference/'runtime-b11433-cuda12.4'
        runtime.mkdir()
        (runtime/entry['path']).write_bytes(data)
        (self.inference/'downloads').mkdir()
        (self.inference/'downloads/fixture.gguf').write_bytes(model_data)
        with patch('local_ai_appliance.asset_integrity.inference_pins', return_value=expected):
            self.assertEqual(verify_inference(self.root)[0], runtime)
            (runtime/'injected.dll').write_bytes(b'Inert undeclared DLL')
            with self.assertRaisesRegex(RuntimeError, 'Undeclared'):
                verify_inference(self.root)
            (runtime/'injected.dll').unlink()
            (runtime/entry['path']).write_bytes(b'Changed')
            with self.assertRaises(RuntimeError):
                verify_inference(self.root)

    def test_links_aliases_and_unsafe_inventory_paths(self):
        for name in ('../x','C:/x','x:stream','NUL','a\\b'):
            with self.assertRaises(RuntimeError):
                entries([{'path':name,'size':1,'sha256':'a'*64}])
    @unittest.skipUnless(os.name == 'posix', 'Native Windows link creation requires separate privilege-qualified fixtures')
    def test_linked_software_is_rejected(self):
        file = self.root/'ordinary.txt'
        file.write_bytes(b'x')
        (self.root/'link.txt').symlink_to(file)
        with self.assertRaises(RuntimeError):
            verify_tree(self.root, [{'path':'ordinary.txt','size':1,'sha256':hashlib.sha256(b'x').hexdigest()}])


if __name__ == '__main__': unittest.main()
