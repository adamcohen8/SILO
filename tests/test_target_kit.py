import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('kit_builder', ROOT / 'scripts' / 'build_target_kit.py')
builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)


class TargetKitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        lines = []
        for name in ('pypdf', 'defusedxml'):
            data = ('Inert wheel fixture for ' + name).encode()
            (self.root / (name + '-1.0-py3-none-any.whl')).write_bytes(data)
            lines.append(name + '==1.0 --hash=sha256:' + hashlib.sha256(data).hexdigest())
        self.source = {'requirements/documents-offline.txt': ('\n'.join(lines) + '\n').encode(),
                       'docs/WINDOWS-TEST-KIT.md': b'Synthetic kit instructions.',
                       'src/source.py': b'# Synthetic source, no execution.'}

    def test_complete_manifest_and_synthetic_payload_only(self):
        payload, digest = builder.assemble(self.source, 'a' * 40, self.root)
        manifest_data = payload['TEST-KIT-MANIFEST.json']; manifest = json.loads(manifest_data)
        self.assertEqual(hashlib.sha256(manifest_data).hexdigest(), digest)
        self.assertFalse(manifest['deployment_ready'])
        expected = {item['path']: item for item in manifest['files']}
        self.assertEqual(set(expected), set(payload) - {'TEST-KIT-MANIFEST.json'})
        for path, item in expected.items():
            self.assertEqual(item['size'], len(payload[path]))
            self.assertEqual(item['sha256'], hashlib.sha256(payload[path]).hexdigest())
        self.assertIn('fixtures/read-only/training.pdf', payload)
        self.assertIn('fixtures/read-only/training.docx', payload)
        self.assertFalse(any('.git/' in path or 'token' in path for path in payload))

    def test_archive_reproducible_and_no_overwrite(self):
        first, h1 = builder.assemble(self.source, 'a' * 40, self.root)
        second, h2 = builder.assemble(self.source, 'a' * 40, self.root)
        self.assertEqual(h1, h2)
        a, b = self.root / 'a.zip', self.root / 'b.zip'
        builder.write_archive(first, a, 'kit'); builder.write_archive(second, b, 'kit')
        self.assertEqual(a.read_bytes(), b.read_bytes())
        with zipfile.ZipFile(a) as file:
            self.assertTrue(all(name.startswith('kit/') for name in file.namelist()))
        with self.assertRaises(FileExistsError): builder.write_archive(first, a, 'kit')

    def test_bad_or_missing_wheel_and_revision_fail(self):
        with self.assertRaises(ValueError): builder.assemble(self.source, 'not-a-commit', self.root)
        (self.root / 'pypdf-1.0-py3-none-any.whl').write_bytes(b'Changed')
        with self.assertRaises(ValueError): builder.assemble(self.source, 'a' * 40, self.root)
        (self.root / 'pypdf-1.0-py3-none-any.whl').unlink()
        with self.assertRaises(ValueError): builder.assemble(self.source, 'a' * 40, self.root)


if __name__ == '__main__': unittest.main()
