import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.signed_policy import sign_document
from local_ai_appliance.release_readiness import CHECKS,new_evidence,readiness,signed_bundle,verify_signed_bundle

class ReleaseReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.payload=self.root/'payload';self.payload.mkdir()
        (self.payload/'app.py').write_text('# inert fixture\n')
        key=Ed25519PrivateKey.generate()
        self.private=key.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption())
        self.public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        self.sha=hashlib.sha256(self.public).hexdigest()

    def test_signed_complete_inventory_then_changed_extra_and_missing_file_denied(self):
        envelope=signed_bundle(self.payload,version='0.1.0',configuration_id='fixture',private_key=self.private)
        self.assertEqual(verify_signed_bundle(self.payload,envelope,self.public,self.sha)['version'],'0.1.0')
        path=self.payload/'app.py';original=path.read_bytes();path.write_bytes(original+b'changed')
        with self.assertRaises(RuntimeError):verify_signed_bundle(self.payload,envelope,self.public,self.sha)
        path.write_bytes(original);extra=self.payload/'extra.py';extra.write_text('undeclared')
        with self.assertRaises(RuntimeError):verify_signed_bundle(self.payload,envelope,self.public,self.sha)
        extra.unlink();path.unlink()
        with self.assertRaises(RuntimeError):verify_signed_bundle(self.payload,envelope,self.public,self.sha)

    def test_untrusted_key_and_invalid_version_denied(self):
        for version in ('latest','../../escape',True):
            with self.assertRaises(AccessDenied):signed_bundle(self.payload,version=version,configuration_id='fixture',private_key=self.private)
        envelope=signed_bundle(self.payload,version='0.1.0',configuration_id='fixture',private_key=self.private)
        with self.assertRaises(AccessDenied):verify_signed_bundle(self.payload,envelope,self.public,'0'*64)

    def test_symbolic_link_denied(self):
        try:
            (self.payload/'link').symlink_to(self.root/'payload/app.py')
        except OSError as error:
            if getattr(error, 'winerror', None) == 1314:
                self.skipTest('Windows symlink privilege unavailable; native link coverage incomplete')
            raise
        with self.assertRaises(RuntimeError):signed_bundle(self.payload,version='0.1.0',configuration_id='fixture',private_key=self.private)

    def test_hard_link_denied(self):
        (self.payload/'hardlink').hardlink_to(self.payload/'app.py')
        with self.assertRaises(RuntimeError):
            signed_bundle(self.payload,version='0.1.0',configuration_id='fixture',private_key=self.private)

    def test_no_pending_failed_or_skipped_check_counts_as_acceptance(self):
        value=new_evidence('fixture','a'*64)
        self.assertEqual(len(value['checks']),len(CHECKS))
        for name,status in zip(CHECKS,('skip','fail','pending')):value['checks'][name]['status']=status
        report=readiness(value,self.root,configuration_id='fixture',release_sha256='a'*64)
        self.assertFalse(report['deployment_ready']);self.assertEqual(report['passed'],0)
        with self.assertRaises(AccessDenied):readiness(value,self.root,configuration_id='different',release_sha256='a'*64)
        del value['checks'][CHECKS[0]]
        with self.assertRaises(AccessDenied):readiness(value,self.root,configuration_id='fixture',release_sha256='a'*64)

    def test_claimed_pass_requires_unchanged_native_reviewed_receipt(self):
        value=new_evidence('fixture','a'*64);name=CHECKS[0]
        receipt={'check':name,'configuration_id':'fixture','release_sha256':'a'*64,'status':'pass',
                 'native':True,'reviewed':True,'reviewer':'Synthetic test-only reviewer'}
        path=self.root/'receipt.json';path.write_bytes(sign_document(receipt,self.private))
        value['checks'][name]={'status':'pass','receipt':'receipt.json','sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        with self.assertRaises(AccessDenied):readiness(value,self.root,configuration_id='fixture',release_sha256='a'*64)
        report=readiness(value,self.root,configuration_id='fixture',release_sha256='a'*64,
            reviewer_public_key=self.public,reviewer_key_sha256=self.sha)
        self.assertEqual(report['passed'],1);self.assertFalse(report['deployment_ready'])
        path.write_bytes(sign_document(dict(receipt,native=False),self.private))
        value['checks'][name]['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaises(AccessDenied):readiness(value,self.root,configuration_id='fixture',release_sha256='a'*64,
            reviewer_public_key=self.public,reviewer_key_sha256=self.sha)
