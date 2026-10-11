import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.ocr import OfflineOCR
from local_ai_appliance.project_store import LocalVault
from local_ai_appliance.release_readiness import inventory
from local_ai_appliance.signed_policy import SignedPolicyStore,sign_document
from local_ai_appliance.workspace import Workspace

class ContainerFixture:
    """Inert pipe contract fixture. Does not execute OCR or qualify containment."""
    def __init__(self):self.closed=False;self.process=self;self.output=b'Synthetic OCR: 108 kg';self.input=None
    def allow_read(self,path,*,directory):self.read=(path,directory)
    def launch(self,command,**kwargs):self.command=command;self.options=kwargs;return self
    def communicate(self,data,**kwargs):self.input=data;self.limits=kwargs;return 0,self.output,b''
    def close(self):self.closed=True

@unittest.skipUnless(os.name=='posix','Portable OCR pipe fixture; native execution requires separate acceptance')
class OCRTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();state=self.root/'state';state.mkdir(mode=0o700)
        self.vault=LocalVault(state);self.addCleanup(self.vault.close)
        self.policy=SignedPolicyStore(self.vault,clock=lambda:1000)
        key=Ed25519PrivateKey.generate();self.private=key.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption())
        public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        self.policy.enroll(public,hashlib.sha256(public).hexdigest(),development=True)
        self.runtime=self.root/'runtime';(self.runtime/'tessdata').mkdir(parents=True)
        (self.runtime/'tesseract.exe').write_bytes(b'Inert fixture exe; never execute')
        (self.runtime/'tessdata/eng.traineddata').write_bytes(b'Inert fixture language')
        self.value={'format':1,'feature':'ocr-tesseract-1','sequence':1,'expires':2000,
                    'files':inventory(self.runtime),'language':'eng','native_acceptance':'pending'}
        self.fixture=ContainerFixture();self.reader=OfflineOCR(self.runtime,self.policy,container_factory=lambda:self.fixture)
        self.workspace=Workspace();self.addCleanup(self.workspace.close)
        folder=self.root/'images';folder.mkdir();(folder/'image.png').write_bytes(b'Inert image fixture; never parsed')
        self.folder=folder;self.grant=self.workspace.grant(folder,'read-only')

    def test_missing_configuration_denies_without_launch(self):
        with self.assertRaises(AccessDenied):self.reader.read(self.workspace,self.grant.id,'image.png')
        self.assertFalse(self.fixture.closed);self.assertIsNone(self.fixture.input)

    def test_signed_runtime_pipe_limits_lpac_uncertainty_and_cleanup(self):
        self.reader.enroll(sign_document(self.value,self.private),development=True)
        result=self.reader.read(self.workspace,self.grant.id,'image.png')
        self.assertEqual(result.unit_kind,'image');self.assertIn('verify critical',result.units[0])
        self.assertTrue(self.fixture.lpac);self.assertTrue(self.fixture.closed)
        self.assertEqual(self.fixture.command[1:3],['stdin','stdout'])
        self.assertEqual(self.fixture.options['memory_mib'],512);self.assertEqual(self.fixture.limits['timeout'],30)
        self.assertEqual(result.sha256,hashlib.sha256(self.fixture.input).hexdigest())

    def test_drift_language_replay_and_unsupported_pdf_denied(self):
        self.reader.enroll(sign_document(self.value,self.private),development=True)
        with self.assertRaises(AccessDenied):self.reader.enroll(sign_document(self.value,self.private),development=True)
        with self.assertRaises(AccessDenied):self.reader.read(self.workspace,self.grant.id,'image.pdf')
        (self.runtime/'tesseract.exe').write_bytes(b'changed')
        with self.assertRaises(RuntimeError):self.reader.read(self.workspace,self.grant.id,'image.png')
        self.assertIsNone(self.fixture.input)

    def test_unconfigured_model_tool_does_not_create_process_authority(self):
        from local_ai_appliance.agent import DocumentAgent
        agent=DocumentAgent.__new__(DocumentAgent);agent.workspace=self.workspace
        with self.assertRaises(AccessDenied):agent._dispatch('read_image_ocr',{'folder_id':self.grant.id,'path':'image.png'},[])
