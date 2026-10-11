"""Optional offline OCR adapter. A signed exact runtime inventory is required.

OCR is a separate native evaluation capability. This adapter reads image bytes
through the folder broker, passes bytes through pipes to an owned zero-capability
LPAC job, and returns uncertain OCR text with the original image digest. It never
silently substitutes OCR for text-PDF parsing or enables downloads.
"""
import hashlib
import os
from pathlib import Path
import threading

from .asset_integrity import ordinary, verify_tree
from .documents import Document
from .folders import AccessDenied


class OfflineOCR:
    def __init__(self,root,policy,*,container_factory=None):
        self.root,self.policy=Path(root),policy
        self.container_factory=container_factory
        self._guard=threading.RLock(); self.active=None; self.container=None

    def configuration(self):
        record=self.policy.vault.get('ocr-policy')
        if record is None: raise AccessDenied('OCR needs an administrator-signed offline runtime policy')
        import base64,time
        value=self.policy.verify(base64.b64decode(record['envelope'],validate=True))
        if (not isinstance(value,dict) or set(value)!={'format','feature','sequence','expires','files','language','native_acceptance'}
                or value['format']!=1 or value['feature']!='ocr-tesseract-1'
                or value['sequence']!=record['sequence'] or value['expires']<=self.policy.clock()
                or value['language']!='eng' or value['native_acceptance']!='pending'):
            raise AccessDenied('OCR policy is invalid, expired or unsupported')
        from .asset_integrity import entries
        files=entries(value['files'])
        if 'tesseract.exe' not in files or 'tessdata/eng.traineddata' not in files:
            raise AccessDenied('OCR runtime and English language data must be pinned')
        return value

    def enroll(self,envelope,*,development=False):
        import base64
        from .signed_policy import administrative_access
        administrative_access(development=development)
        value=self.policy.verify(envelope)
        previous=self.policy.vault.get('ocr-policy')
        if (not isinstance(value,dict) or type(value.get('sequence')) is not int or value['sequence']<1
                or previous and value['sequence']<=previous['sequence']):
            raise AccessDenied('OCR policy rollback or replay denied')
        candidate={'sequence':value['sequence'],'envelope':base64.b64encode(envelope).decode('ascii')}
        # Validate before committing, without temporarily publishing an invalid policy.
        class CandidateVault:
            def get(self,name):return candidate
        class CandidatePolicy:
            vault=CandidateVault()
            clock=staticmethod(self.policy.clock)
            verify=staticmethod(self.policy.verify)
        checker=OfflineOCR(self.root,CandidatePolicy(),container_factory=self.container_factory)
        checker.configuration()
        verify_tree(self.root,value['files'])
        with self.policy.vault.transaction():
            previous=self.policy.vault.get('ocr-policy')
            if previous and value['sequence']<=previous['sequence']:
                raise AccessDenied('OCR policy rollback or replay denied')
            self.policy.vault.put('ocr-policy',candidate)

    def read(self,workspace,folder_id,path):
        if Path(path).suffix.lower() not in {'.png','.jpg','.jpeg','.tif','.tiff'}:
            raise AccessDenied('OCR accepts one explicitly selected PNG, JPEG or TIFF image; PDF OCR requires a separately qualified conversion step')
        workspace.checkpoint()
        data=workspace.broker.read_file(folder_id,path)
        if not 0<len(data)<=8*1024*1024:raise AccessDenied('OCR image exceeds limit')
        value=self.configuration(); verify_tree(self.root,value['files'])
        if self.container_factory is None:
            if os.name!='nt':raise AccessDenied('OCR containment requires native Windows')
            from .windows_container import AppContainer
            factory=lambda:AppContainer(evaluation=True)
        else:factory=self.container_factory
        with self._guard:
            if self.active is not None:raise AccessDenied('OCR is already active')
            self.container=factory(); self.container.lpac=True
            try:
                self.container.allow_read(self.root,directory=True)
                command=[str(self.root/'tesseract.exe'),'stdin','stdout','--tessdata-dir',str(self.root/'tessdata'),'-l','eng']
                self.active=self.container.launch(command,cwd=self.root,memory_mib=512)
            except BaseException:
                self.container.close(); self.container=None; raise
        try:
            workspace.checkpoint()
            code,out,_=self.active.communicate(data,timeout=30,limit=512*1024)
            if code!=0:raise AccessDenied('Contained OCR failed or exceeded limits')
            text=out.decode('utf-8')
            if not text.strip():raise AccessDenied('OCR returned no readable text')
            if hashlib.sha256(workspace.broker.read_file(folder_id,path)).digest()!=hashlib.sha256(data).digest():
                raise AccessDenied('Image changed during OCR')
            return Document(folder_id,path,hashlib.sha256(data).hexdigest(),'ocr','image',
                ('OCR transcription; verify critical values against the source image.\n'+text,))
        finally:
            with self._guard:
                try:
                    if self.active:self.active.close()
                finally:
                    self.active=None
                    try:
                        if self.container:self.container.close()
                    finally:self.container=None

    def cancel(self):
        with self._guard:
            if self.active:self.active.kernel.TerminateJobObject(self.active.job,125)
