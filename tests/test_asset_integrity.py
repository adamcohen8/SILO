import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from contextlib import contextmanager

from local_ai_appliance.asset_integrity import digest_file, entries, inference_pins, verify_inference, verify_tree
from local_ai_appliance.windows_session import WindowsSession

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def fixture_stream(path):
    """Synthetic metadata fixtures exercise neither Windows IO nor acceptance."""
    with Path(path).open('rb') as stream:
        yield stream, None


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
        try:
            with self.assertRaisesRegex(RuntimeError, 'Software changed'):
                digest_file(path, cancel=mutate)
        except OSError as error:
            # The native read lease now prevents this write in the first place.
            # Only a real Windows sharing violation with unchanged bytes is an
            # acceptable alternative to detecting an already performed write.
            if os.name != 'nt' or error.winerror != 32:
                raise
            self.assertEqual(path.read_bytes(), b'Original synthetic bytes')

    def test_windows_path_and_descriptor_ctime_can_differ_without_mutation(self):
        from local_ai_appliance import asset_integrity
        path = self.root/'windows-stat-fixture.txt'
        content = b'SYNTHETIC WINDOWS STAT FIXTURE'
        path.write_bytes(content)
        def stamp(value, *, descriptor=False):
            return SimpleNamespace(**{name: getattr(value, name) for name in
                ('st_dev', 'st_ino', 'st_size', 'st_nlink', 'st_mtime_ns')},
                st_birthtime_ns=123,
                st_ctime_ns=value.st_ctime_ns + (100 if descriptor else 0))
        native_fstat = os.fstat
        with patch.object(asset_integrity, 'ordinary', side_effect=lambda p: stamp(Path(p).stat())), \
             patch.object(asset_integrity, '_verification_stream', fixture_stream), \
             patch.object(asset_integrity, 'os', SimpleNamespace(name='nt',
                fstat=lambda fd: stamp(native_fstat(fd), descriptor=True))):
            self.assertEqual(digest_file(path), hashlib.sha256(content).hexdigest())

    def test_windows_final_path_metadata_change_is_rejected(self):
        from local_ai_appliance import asset_integrity
        path = self.root/'windows-final-stat-fixture.txt'
        original = b'Original synthetic bytes'
        path.write_bytes(original)
        before = path.stat()
        path_checks = []
        def stamp(value):
            return SimpleNamespace(**{name: getattr(value, name) for name in
                ('st_dev', 'st_ino', 'st_size', 'st_nlink', 'st_mtime_ns')},
                st_birthtime_ns=123, st_ctime_ns=value.st_ctime_ns)
        def path_stat(p):
            path_checks.append(p)
            if len(path_checks) == 2:
                path.write_bytes(b'Changed! synthetic bytes')
                os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
                # Simulate the changed path metadata timestamp independently
                # of the platform's timestamp granularity.
                value = stamp(path.stat())
                value.st_ctime_ns = before.st_ctime_ns + 100
                return value
            return stamp(path.stat())
        native_fstat = os.fstat
        with patch.object(asset_integrity, 'ordinary', side_effect=path_stat), \
             patch.object(asset_integrity, '_verification_stream', fixture_stream), \
             patch.object(asset_integrity, 'os', SimpleNamespace(name='nt',
                fstat=lambda fd: stamp(native_fstat(fd)))):
            with self.assertRaisesRegex(RuntimeError, 'identity changed after'):
                digest_file(path)

    def test_native_change_time_detects_mutation_when_python_timestamps_are_unchanged(self):
        from local_ai_appliance import asset_integrity
        path = self.root/'native-change-time-fixture.txt'
        path.write_bytes(b'Original synthetic bytes')
        frozen = path.stat()
        changed = False
        native_stamps = []
        def mutate():
            nonlocal changed
            path.write_bytes(b'Changed! synthetic bytes')
            os.utime(path, ns=(frozen.st_atime_ns, frozen.st_mtime_ns))
            changed = True
        def native_stamp():
            native_stamps.append(changed)
            return ('held-file', 101 if changed else 100)
        @contextmanager
        def held_fixture(p):
            with Path(p).open('rb') as stream:
                yield stream, native_stamp
        with patch.object(asset_integrity, 'ordinary', return_value=frozen), \
             patch.object(asset_integrity, '_verification_stream', held_fixture), \
             patch.object(asset_integrity.os, 'fstat', return_value=frozen):
            with self.assertRaisesRegex(RuntimeError, 'Software changed'):
                digest_file(path, cancel=mutate)
        self.assertEqual(native_stamps, [False, True])

    def test_final_path_check_and_native_snapshot_run_before_lease_release(self):
        from local_ai_appliance import asset_integrity
        path = self.root/'held-until-final-check.txt'
        content = b'UNCHANGED SYNTHETIC CONTROL'
        path.write_bytes(content)
        held, checks = False, []
        native_ordinary = asset_integrity.ordinary
        @contextmanager
        def lease(p):
            nonlocal held
            with Path(p).open('rb') as stream:
                held = True
                try:
                    yield stream, lambda: ('stable', held)
                finally:
                    held = False
        def check(p):
            checks.append(held)
            return native_ordinary(p)
        with patch.object(asset_integrity, '_verification_stream', lease), \
             patch.object(asset_integrity, 'ordinary', side_effect=check):
            self.assertEqual(digest_file(path), hashlib.sha256(content).hexdigest())
        self.assertEqual(checks, [False, True])
        self.assertFalse(held)

    def test_cancel_exception_is_preserved_and_read_lease_is_released(self):
        path = self.root/'cancelled-hash.txt'
        path.write_bytes(b'SYNTHETIC CANCELLATION')
        marker = RuntimeError('synthetic cancellation')
        def cancel():
            raise marker
        with self.assertRaises(RuntimeError) as caught:
            digest_file(path, cancel=cancel)
        self.assertIs(caught.exception, marker)
        path.write_bytes(b'WRITE AFTER CANCELLATION')

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
