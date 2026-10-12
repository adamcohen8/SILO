"""Portable install-plan contracts; synthetic signatures never qualify Windows."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption

from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.machine_security import MachineStore, TECHNICAL_CHECKS
from local_ai_appliance.managed_installation import parse_plan, validated_records, activate
from local_ai_appliance.model_management import builtin_profiles
from local_ai_appliance.release_readiness import signed_bundle, inventory
from local_ai_appliance.security_events import SecurityAudit
from local_ai_appliance.security_maintenance import sbom
from local_ai_appliance.signed_policy import sign_document, canonical

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'posix', 'Portable signed fixtures; not native acceptance')
class ManagedInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.release = self.root / 'release-1'
        self.payload = self.release / 'payload'
        self.app = self.payload / 'app'
        self.app.mkdir(parents=True)
        for name in ('machine', 'state', 'references', 'drafts'):
            (self.root / name).mkdir(mode=0o700)
        self.store = MachineStore(self.root / 'machine', development=True, writable=True)
        self.addCleanup(self.store.close)
        self.events = []
        self.audit = SecurityAudit(self.events.append)
        self.private = {}
        anchors = {}
        for role in ('trust', 'release', 'reviewer'):
            key = Ed25519PrivateKey.generate()
            self.private[role] = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
            public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
            anchors[role + '-anchor'] = {'key': base64.b64encode(public).decode(), 'sha256': hashlib.sha256(public).hexdigest()}
        self.profiles = builtin_profiles(ROOT)
        self.model_id = self.profiles[0]['id']
        # Tiny inert GGUF-header fixture. This exercises real size/hash checks
        # under a synthetic signed policy, without inference or real weights.
        model_bytes = b'GGUF Public inert model fixture'
        self.profiles[0]['model']['size'] = len(model_bytes)
        self.profiles[0]['model']['sha256'] = hashlib.sha256(model_bytes).hexdigest()
        models = self.root / 'state' / 'models'; models.mkdir(mode=0o700)
        self.model_path = models / (self.profiles[0]['model']['sha256'] + '.gguf')
        self.model_path.write_bytes(model_bytes)
        config = {'format_version': 1, 'evaluation_only': True, 'state_root': str(self.root / 'state'),
                  'worker': '../worker', 'qualification': 'evaluation_only_full_isolation_and_CUI_acceptance_pending',
                  'default_model_id': self.model_id}
        (self.app / 'evaluation-installation.json').write_text(json.dumps(config))
        (self.app / 'fixture.txt').write_text('Public inert source fixture')
        signed = signed_bundle(self.payload, version='0.1.0', configuration_id='synthetic-install', private_key=self.private['release'])
        release_digest = hashlib.sha256(signed).hexdigest()
        expires = time.time() + 3600
        self.policy = {'format': 1, 'sequence': 1, 'expires': expires, 'profiles': self.profiles,
                       'blocked_publishers': [], 'blocked_jurisdictions': []}
        self.advisories = {'format': 1, 'sequence': 1, 'expires': expires, 'coverage': [], 'advisories': []}
        self.maintenance = {'format': 1, 'sequence': 1, 'expires': expires, 'release_sha256': release_digest,
                            'sbom_sha256': hashlib.sha256(canonical(sbom(self.payload, inventory(self.payload)))).hexdigest(),
                            'advisory_snapshot_sha256': hashlib.sha256(canonical(self.advisories)).hexdigest(),
                            'status': 'accepted', 'native_components_reviewed': True}
        self.technical = {'format': 1, 'release_sha256': release_digest, 'native_version': 'synthetic-os',
                          'boundary': 'silo-lpac-managed-2', 'expires': expires,
                          'checks': {name: {'status': 'pass', 'evidence_sha256': 'a' * 64} for name in TECHNICAL_CHECKS}}
        self.plan = {'format': 1, 'source_id': 'a' * 16, 'release_name': self.release.name,
                     'user_sid': 'S-1-5-21-1-2-3-1001', 'state_root': str(self.root / 'state'),
                     'model_id': self.model_id, 'anchors': anchors,
                     'release_envelope': base64.b64encode(signed).decode(),
                     'settings': {'reference_roots': [str(self.root / 'references')],
                                  'draft_roots': [str(self.root / 'drafts')],
                                  'excluded_roots': [str(self.root / 'state')], 'allow_code': False,
                                  'allow_code_exports': False, 'allow_ocr': False, 'allow_schedules': False,
                                  'maximum_retention_days': 30}}
        for field, value, role in (('model_policy', self.policy, 'trust'), ('advisories', self.advisories, 'reviewer'),
                                   ('maintenance', self.maintenance, 'reviewer'), ('technical_receipt', self.technical, 'reviewer')):
            self.plan[field] = base64.b64encode(sign_document(value, self.private[role])).decode()

    def parsed(self, plan=None):
        data = canonical(self.plan if plan is None else plan)
        return parse_plan(data, hashlib.sha256(data).hexdigest())

    def validate(self, plan=None, **kwargs):
        return validated_records(self.parsed(plan), self.payload, self.release,
                                 source_id='a' * 16, user_sid=self.plan['user_sid'], native_version='synthetic-os', **kwargs)

    def enroll(self):
        return activate(self.parsed(), self.release, self.store, self.audit, source_id='a' * 16,
                        user_sid=self.plan['user_sid'], native_version='synthetic-os')

    def test_all_records_publish_once_and_exact_retry_does_not_replay_policy(self):
        result = self.enroll()
        self.assertTrue(result['activated'])
        self.assertFalse(result['model_launched'])
        self.assertFalse(result['deployment_ready'])
        self.assertEqual(self.store._read()['generation'], 1)
        before = (self.root / 'machine' / 'records.json').read_bytes()
        retry = self.enroll()
        self.assertFalse(retry['changed'])
        self.assertEqual((self.root / 'machine' / 'records.json').read_bytes(), before)
        self.assertEqual(set(self.store._read()['records']),
                         {'trust-anchor', 'release-anchor', 'reviewer-anchor', 'active-policy',
                          'advisory-snapshot', 'maintenance-review', 'deployment'})

    def test_failed_atomic_replace_preserves_the_entire_previous_state(self):
        self.store.put('unrelated-record', {'keep': True})
        before = (self.root / 'machine' / 'records.json').read_bytes()
        with patch('local_ai_appliance.machine_security.os.replace', side_effect=OSError('injected publication failure')):
            with self.assertRaises(OSError): self.enroll()
        self.assertEqual((self.root / 'machine' / 'records.json').read_bytes(), before)
        self.assertFalse(list((self.root / 'machine').glob('.admin-*')))
        self.enroll()
        self.assertEqual(self.store.get('unrelated-record'), {'keep': True})

    def test_invalid_receipt_never_enrolls_any_anchor_or_policy(self):
        for mutation in ('unsigned', 'wrong-key', 'skip', 'expired', 'os', 'release'):
            plan = copy.deepcopy(self.plan)
            receipt = copy.deepcopy(self.technical)
            if mutation == 'skip': receipt['checks']['network_ipv6']['status'] = 'skip'
            if mutation == 'expired': receipt['expires'] = 1
            if mutation == 'os': receipt['native_version'] = 'other-os'
            if mutation == 'release': receipt['release_sha256'] = 'b' * 64
            private = self.private['trust'] if mutation == 'wrong-key' else self.private['reviewer']
            data = canonical(receipt) if mutation == 'unsigned' else sign_document(receipt, private)
            plan['technical_receipt'] = base64.b64encode(data).decode()
            with self.subTest(mutation=mutation), self.assertRaises(AccessDenied): self.validate(plan)
            self.assertEqual(self.store._read()['records'], {})

    def test_digest_source_account_private_state_and_path_cannot_be_substituted(self):
        data = canonical(self.plan)
        with self.assertRaises(AccessDenied): parse_plan(data, '0' * 64)
        for field, value in (('source_id', 'b' * 16), ('user_sid', 'S-1-5-21-1-2-3-1002'),
                             ('state_root', str(self.root)), ('release_name', '../escape'),
                             ('release_name', 'CON'), ('release_name', 'same.'), ('model_id', 'unknown')):
            plan = copy.deepcopy(self.plan); plan[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(AccessDenied): self.validate(plan)
        plan = copy.deepcopy(self.plan); plan['settings']['excluded_roots'] = [str(self.root / 'references')]
        with self.assertRaises(AccessDenied): self.validate(plan)

    def test_changed_software_or_extra_file_cannot_use_signed_inventory(self):
        fixture = self.app / 'fixture.txt'
        original = fixture.read_bytes()
        fixture.write_bytes(b'Changed fixture')
        with self.assertRaises(RuntimeError): self.enroll()
        self.assertEqual(self.store._read()['records'], {})
        fixture.write_bytes(original)
        (self.app / 'unlisted.py').write_bytes(b'Inert extra executable fixture')
        with self.assertRaises(RuntimeError): self.enroll()
        self.assertEqual(self.store._read()['records'], {})

    def test_rotation_revocation_downgrade_and_conflicting_replay_denied(self):
        self.enroll(); old = self.store._read()['records']
        plan = copy.deepcopy(self.plan)
        plan['anchors']['trust-anchor'] = plan['anchors']['release-anchor']
        with self.assertRaises(AccessDenied): self.validate(plan, previous=old)
        for sequence in (0, 1):
            policy = copy.deepcopy(self.policy); policy['sequence'] = sequence; policy['expires'] += 1
            plan = copy.deepcopy(self.plan); plan['model_policy'] = base64.b64encode(sign_document(policy, self.private['trust'])).decode()
            with self.assertRaises(AccessDenied): self.validate(plan, previous=old)
        old['revoked-releases'] = [self.store.get('deployment')['release_sha256']]
        with self.assertRaises(AccessDenied): self.validate(previous=old)

    def test_prohibited_model_advisory_or_optional_execution_cannot_activate(self):
        policy = copy.deepcopy(self.policy); policy['blocked_publishers'] = policy['profiles'][0]['publishers']
        plan = copy.deepcopy(self.plan); plan['model_policy'] = base64.b64encode(sign_document(policy, self.private['trust'])).decode()
        with self.assertRaises(AccessDenied): self.validate(plan)
        plan = copy.deepcopy(self.plan); plan['settings']['allow_code'] = True
        with self.assertRaises(AccessDenied): self.validate(plan)
        plan = copy.deepcopy(self.plan)
        maintenance = copy.deepcopy(self.maintenance); maintenance['sbom_sha256'] = 'b' * 64
        plan['maintenance'] = base64.b64encode(sign_document(maintenance, self.private['reviewer'])).decode()
        with self.assertRaises(AccessDenied): self.validate(plan)

    def test_missing_or_changed_selected_model_is_denied_before_enrollment(self):
        original = self.model_path.read_bytes()
        self.model_path.write_bytes(b'Changed inert model')
        with self.assertRaises(AccessDenied): self.enroll()
        self.assertEqual(self.store._read()['records'], {})
        self.model_path.unlink()
        with self.assertRaises(FileNotFoundError): self.enroll()
        self.assertEqual(self.store._read()['records'], {})
        self.model_path.write_bytes(original)
        self.assertTrue(self.enroll()['activated'])

    def test_audit_failure_before_publication_and_after_publication_have_safe_retry(self):
        def fail(_): raise OSError('injected audit failure')
        self.audit = SecurityAudit(fail)
        with self.assertRaises(AccessDenied): self.enroll()
        self.assertEqual(self.store._read()['records'], {})
        calls = []
        def fail_after_publish(data):
            calls.append(data)
            if len(calls) == 2: raise OSError('injected audit completion failure')
        self.audit = SecurityAudit(fail_after_publish)
        with self.assertRaises(AccessDenied): self.enroll()
        self.assertIsNotNone(self.store.get('deployment'))
        self.audit = SecurityAudit(self.events.append)
        self.assertFalse(self.enroll()['changed'])

    def test_plan_builder_consumes_signed_material_and_refuses_existing_output(self):
        from local_ai_appliance.model import json_bytes
        inputs = self.root / 'approved'; inputs.mkdir()
        arguments = [sys.executable, str(ROOT / 'scripts/build_activation_plan.py'),
                     '--prepared-root', str(self.release), '--source-id', 'a' * 16,
                     '--release-name', self.release.name, '--user-sid', self.plan['user_sid'],
                     '--native-version', 'synthetic-os', '--settings', str(inputs / 'settings.json'),
                     '--output', str(inputs / 'plan.json')]
        (inputs / 'settings.json').write_bytes(json_bytes(self.plan['settings']))
        for role in ('trust', 'release', 'reviewer'):
            record = self.plan['anchors'][role + '-anchor']
            path = inputs / (role + '.pub'); path.write_bytes(base64.b64decode(record['key']))
            arguments += ['--' + role + '-key', str(path), '--' + role + '-key-sha256', record['sha256']]
        for field in ('model_policy', 'advisories', 'maintenance', 'release_envelope', 'technical_receipt'):
            path = inputs / (field + '.json'); path.write_bytes(base64.b64decode(self.plan[field]))
            arguments += ['--' + field.replace('_', '-'), str(path)]
        result = subprocess.run(arguments, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertFalse(receipt['activated']); self.assertFalse(receipt['native_validation_performed'])
        original = (inputs / 'plan.json').read_bytes()
        self.assertEqual(parse_plan(original, receipt['plan_sha256']), self.plan)
        retry = subprocess.run(arguments, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(retry.returncode, 0)
        self.assertEqual((inputs / 'plan.json').read_bytes(), original)
        self.assertEqual(self.store._read()['records'], {})

    @unittest.skipUnless(shutil.which('pwsh') or Path('/private/tmp/local-ai-powershell/pwsh').exists(),
                         'Optional portable PowerShell required')
    def test_pre_python_powershell_gate_checks_actual_bytes_and_rejects_extras(self):
        # Execute only the real payload pin/namespace function. Windows identity,
        # ACL/provisioning/UAC, native link checks and actual activation are absent.
        helper = (ROOT / 'installer/Activate-SILO.ps1').read_text()
        start = helper.index('function Hold-ApprovedPayload(')
        end = helper.index("\nif (-not ('SILOActivationFile'", start)
        script = self.root / 'held-payload.ps1'
        script.write_text('''
. $args[0]
function Test-LocalPath([string]$Path,[switch]$Directory) { return [IO.Path]::GetFullPath($Path) }
Add-Type -TypeDefinition 'public static class SILOActivationFile { public static void Check(Microsoft.Win32.SafeHandles.SafeFileHandle file) {} }'
''' + helper[start:end] + '''
$handles=[Collections.Generic.List[IDisposable]]::new()
try {
    $files=Get-Content -LiteralPath $args[2] -Raw | ConvertFrom-Json
    Hold-ApprovedPayload $args[1] $files $handles
    [IO.File]::AppendAllText($args[3],'verified')
} finally { foreach ($stream in $handles) { $stream.Dispose() } }
''', encoding='utf-8-sig')
        files = self.root / 'files.json'; files.write_text(json.dumps(inventory(self.payload)))
        receipt = self.root / 'pre-python-receipt'
        pwsh = shutil.which('pwsh') or '/private/tmp/local-ai-powershell/pwsh'
        def invoke():
            return subprocess.run([pwsh, '-NoLogo', '-NoProfile', '-File', str(script),
                                   str(ROOT / 'installer/Evaluation-Common.ps1'), str(self.release),
                                   str(files), str(receipt)], capture_output=True, text=True, timeout=30)
        result = invoke(); self.assertEqual(result.returncode, 0, result.stderr)
        original = (self.app / 'fixture.txt').read_bytes()
        (self.app / 'fixture.txt').write_bytes(b'Changed fixture')
        self.assertNotEqual(invoke().returncode, 0)
        (self.app / 'fixture.txt').write_bytes(original)
        (self.app / 'unlisted.py').write_bytes(b'Inert extra source')
        self.assertNotEqual(invoke().returncode, 0)
        self.assertEqual(receipt.read_text(), 'verified')


if __name__ == '__main__': unittest.main()
