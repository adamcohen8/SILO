import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from local_ai_appliance.bundle import BundleError, MANIFEST_NAME
from local_ai_appliance.installation import operate


def synthetic_bundle(root):
    artifacts = []
    for path, role, data in [('app/source.txt', 'application', b'Synthetic application, never execute.'),
                             ('runtime/runtime.txt', 'runtime', b'Synthetic runtime, not executable.'),
                             ('model/model.txt', 'model', b'Synthetic model, not real weights.')]:
        target = root / path; target.parent.mkdir(exist_ok=True); target.write_bytes(data)
        artifacts.append({'path': path, 'role': role, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                          'version': 'fixture-1', 'license': 'CC0-1.0', 'source': 'Synthetic local fixture'})
    data = json.dumps({'format_version': 1, 'bundle_id': 'synthetic-fixture', 'target': 'windows-amd64',
                       'artifacts': artifacts}).encode()
    (root / MANIFEST_NAME).write_bytes(data)
    return hashlib.sha256(data).hexdigest()


@unittest.skipUnless(os.name == 'posix', 'Portable POSIX installation framework fixtures')
class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.bundle = self.root / 'bundle'; self.bundle.mkdir()
        self.store = self.root / 'private'; self.store.mkdir(mode=0o700)
        self.digest = synthetic_bundle(self.bundle)
        self.payload = self.store / ('tx-' + self.digest) / 'payload'

    def run_action(self, action, **kwargs):
        return operate(action, self.bundle, self.digest, state_root=self.store, development=True, **kwargs)

    def test_plan_read_only_and_default_mutation_denied(self):
        value = operate('plan', self.bundle, self.digest)
        self.assertTrue(value['payload_integrity_verified'])
        self.assertFalse(value['deployment_ready'])
        self.assertEqual(list(self.store.iterdir()), [])
        with self.assertRaises(BundleError): operate('stage', self.bundle, self.digest, state_root=self.store)

    def test_stage_idempotence_and_no_payload_execution(self):
        with patch('subprocess.run', side_effect=AssertionError('No execution')):
            value = self.run_action('stage')
        self.assertEqual(value['phase'], 'staged')
        self.assertFalse(value['payload_execution_performed'])
        self.assertFalse(value['deployment_ready'])
        self.assertTrue(self.run_action('stage')['idempotent'])
        self.assertEqual(self.run_action('status')['phase'], 'staged')

    def test_reboot_requires_changed_boot_then_validation(self):
        self.run_action('stage')
        self.run_action('pause-for-reboot', boot_id='2026-10-05T12:00:00Z')
        with self.assertRaises(BundleError): self.run_action('resume', boot_id='2026-10-05T12:00:00Z')
        value = self.run_action('resume', boot_id='2026-10-06T12:00:00Z')
        self.assertEqual(value['phase'], 'pending_validation')
        self.assertTrue(value['prerequisite_recheck_required'])
        self.assertFalse(value['deployment_ready'])

    def test_rollback_owned_payload_only_and_journal_retained(self):
        unrelated = self.store / 'unrelated.txt'; unrelated.write_text('Preserve')
        self.run_action('stage'); value = self.run_action('rollback')
        self.assertEqual(value['phase'], 'rolled_back')
        self.assertFalse(self.payload.exists())
        self.assertTrue((self.payload.parent / 'journal').exists())
        self.assertEqual(unrelated.read_text(), 'Preserve')
        self.assertTrue(self.run_action('rollback')['idempotent'])
        self.assertEqual(self.run_action('stage')['phase'], 'staged')

    def test_modified_or_unowned_content_preserved(self):
        self.run_action('stage')
        target = self.payload / 'model' / 'model.txt'; target.write_bytes(b'Changed')
        with self.assertRaises(BundleError): self.run_action('rollback')
        self.assertEqual(target.read_bytes(), b'Changed')
        target.write_bytes((self.bundle / 'model' / 'model.txt').read_bytes())
        outsider = self.payload / 'do-not-delete.txt'; outsider.write_text('Keep')
        with self.assertRaises(BundleError): self.run_action('rollback')
        self.assertTrue(outsider.exists())

    def test_source_corruption_and_staging_failure_never_ready(self):
        (self.bundle / 'model' / 'model.txt').write_bytes(b'Bad')
        with self.assertRaises(BundleError): self.run_action('stage')
        self.assertEqual(self.run_action('status')['phase'], 'failed')
        self.assertFalse((self.payload / 'model' / 'model.txt').exists())
        self.assertEqual(self.run_action('rollback')['phase'], 'rolled_back')

    def test_staged_corruption_blocks_resume_and_idempotence(self):
        self.run_action('stage'); self.run_action('pause-for-reboot', boot_id='1')
        (self.payload / 'model' / 'model.txt').write_bytes(b'Bad')
        with self.assertRaises(BundleError): self.run_action('resume', boot_id='2')

    def test_changed_journal_symlink_and_public_storage_rejected(self):
        self.store.chmod(0o755)
        with self.assertRaises(BundleError): self.run_action('stage')
        self.store.chmod(0o700); self.run_action('stage')
        journal = self.payload.parent / 'journal' / '000001.json'
        value = json.loads(journal.read_bytes()); value['phase'] = 'ready'; journal.write_text(json.dumps(value))
        with self.assertRaises(BundleError): self.run_action('status')

    def test_symlink_payload_store_or_lock_refused(self):
        alias = self.root / 'alias'; alias.symlink_to(self.store, target_is_directory=True)
        with self.assertRaises(OSError): operate('stage', self.bundle, self.digest, state_root=alias, development=True)
        (self.store / '.installer-lock').write_text('Existing owner or crash marker')
        with self.assertRaises(FileExistsError): self.run_action('stage')
        self.assertTrue((self.store / '.installer-lock').exists())

    def test_no_space_or_bad_boot_id_denied(self):
        from collections import namedtuple
        usage = namedtuple('Usage', 'total used free')(100, 100, 0)
        with patch('local_ai_appliance.installation.shutil.disk_usage', return_value=usage):
            with self.assertRaises(BundleError): self.run_action('stage')
        with self.assertRaises(BundleError): self.run_action('pause-for-reboot', boot_id='host-name')


if __name__ == '__main__': unittest.main()
