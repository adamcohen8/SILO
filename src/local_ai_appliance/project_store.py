"""Explicit, encrypted local projects. Host-only; never a model tool.

The Windows key is protected for the current account with DPAPI. Directory ACLs
and handle-relative I/O use the existing private Store. POSIX is a development
implementation. Code workspaces and pending approvals are never serialized.
"""
from dataclasses import asdict, replace
from contextlib import contextmanager
import ctypes as C
import hashlib
import os
from pathlib import Path
import re
import secrets
import threading
import time

from .contracts import Project
from .conversation import Conversation
from .agent import Source
from .folders import AccessDenied
from .install_store import Store
from .model import json_bytes, strict_json

MAX_RECORD = 4 * 1024 * 1024


def dpapi(data, *, decrypt=False):
    """No UI, no machine-wide flag, no hardcoded entropy or recovery key."""
    if os.name != 'nt':
        raise AccessDenied('DPAPI requires native Windows')
    class Blob(C.Structure):
        _fields_ = [('size', C.c_uint32), ('data', C.POINTER(C.c_ubyte))]
    crypt = C.WinDLL('crypt32', use_last_error=True)
    kernel = C.WinDLL('kernel32', use_last_error=True)
    buffer = (C.c_ubyte * len(data)).from_buffer_copy(data)
    source, result = Blob(len(data), buffer), Blob()
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [C.POINTER(Blob), C.c_void_p, C.c_void_p, C.c_void_p,
                         C.c_void_p, C.c_uint32, C.POINTER(Blob)]
    function.restype = C.c_int
    kernel.LocalFree.argtypes = [C.c_void_p]
    kernel.LocalFree.restype = C.c_void_p
    if not function(C.byref(source), None, None, None, None, 1, C.byref(result)):
        raise AccessDenied('Current-account key protection failed')
    try:
        if not 0 < result.size <= 16384:
            raise AccessDenied('Invalid protected key')
        return C.string_at(result.data, result.size)
    finally:
        kernel.LocalFree(result.data)


class LocalVault:
    def __init__(self, path, *, windows_validation=False):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        self.path = Path(path).absolute()
        self.store = Store(path, windows_validation=windows_validation)
        self._guard = threading.RLock()
        self._transaction_depth = 0
        try:
            with self.store.lock():
                if 'vault.key' not in self.store.names():
                    key = secrets.token_bytes(32)
                    protected = dpapi(key) if os.name == 'nt' else key
                    self.store.write('vault.key', lambda write: write(protected))
                protected = self.store.read('vault.key', limit=16384)
                key = dpapi(protected, decrypt=True) if os.name == 'nt' else protected
                if len(key) != 32:
                    raise AccessDenied('Invalid project key')
                self._key = key
                self.cipher = AESGCM(key)
                self.key_id = hashlib.sha256(key).hexdigest()
        except BaseException:
            self.store.close()
            raise

    @staticmethod
    def _name(name):
        if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9_-]{1,80}', name):
            raise AccessDenied('Invalid private record name')
        return name

    def _versions(self, name):
        pattern = re.compile(re.escape(self._name(name)) + r'-(\d{20})\.seal')
        return sorted((int(match[1]), item) for item in self.store.names()
                      if (match := pattern.fullmatch(item)))

    def names(self, prefix):
        with self.transaction():
            self._name(prefix)
            return sorted({item.rsplit('-', 1)[0] for item in self.store.names()
                           if re.fullmatch(re.escape(prefix) + r'[a-z0-9_-]*-\d{20}\.seal', item)})

    @contextmanager
    def transaction(self):
        """Serialize host read/modify/write operations across threads and clients."""
        with self._guard:
            if self._transaction_depth:
                self._transaction_depth += 1
                try: yield
                finally: self._transaction_depth -= 1
            else:
                with self.store.lock():
                    self._transaction_depth = 1
                    try: yield
                    finally: self._transaction_depth = 0

    def get(self, name, default=None):
        with self.transaction():
            versions = self._versions(name)
            if not versions:
                return default
            _, filename = versions[-1]
            data = self.store.read(filename, limit=MAX_RECORD + 64)
            try:
                if data[:5] != b'SILO1' or len(data) < 33:
                    raise ValueError()
                clear = self.cipher.decrypt(data[5:17], data[17:], filename.encode('ascii'))
                return strict_json(clear)
            except Exception as error:
                raise AccessDenied('Private record authentication failed; no context restored') from error

    def put(self, name, value):
        clear = json_bytes(value)
        if len(clear) > MAX_RECORD:
            raise AccessDenied('Private record exceeds storage limit')
        with self.transaction():
            versions = self._versions(name)
            sequence = versions[-1][0] + 1 if versions else 1
            filename = f'{self._name(name)}-{sequence:020d}.seal'
            nonce = secrets.token_bytes(12)
            data = b'SILO1' + nonce + self.cipher.encrypt(nonce, clear, filename.encode('ascii'))
            self.store.write(filename, lambda write: write(data))
            # Immutable new version is durable before old versions are retired.
            for _, old in versions:
                self.store.remove(old)

    def delete(self, name):
        with self.transaction():
            for _, old in self._versions(name):
                self.store.remove(old)

    def backup(self):
        """Opaque account-bound archive; deliberately excludes the local key."""
        import base64
        with self.transaction():
            files = {name: base64.b64encode(self.store.read(name, limit=MAX_RECORD+64)).decode('ascii')
                     for name in self.store.names() if re.fullmatch(
                         r'(?:project-[a-f0-9]{32}|active-project|schedules)-\d{20}\.seal', name)}
            if len(files) > 256:
                raise AccessDenied('Backup inventory exceeds limit')
            result = json_bytes({'format': 1, 'key_id': self.key_id, 'files': files})
            if len(result) > 64*1024*1024: raise AccessDenied('Backup exceeds 64 MiB')
            return result

    def restore(self, data):
        """Explicit host operation. Verify every record before writing any file."""
        import base64
        if len(data) > 64 * 1024 * 1024:
            raise AccessDenied('Backup is oversized')
        value = strict_json(data)
        key_id = self.key_id
        if (set(value) != {'format', 'key_id', 'files'} or value['format'] != 1
                or value['key_id'] != key_id or not isinstance(value['files'], dict)
                or len(value['files']) > 256):
            raise AccessDenied('Backup belongs to a different account key or is malformed')
        prepared = []
        for filename, encoded in value['files'].items():
            if not re.fullmatch(r'[a-z0-9_-]{1,80}-\d{20}\.seal', filename):
                raise AccessDenied('Invalid backup record')
            try:
                sealed = base64.b64decode(encoded, validate=True)
                if len(sealed) > MAX_RECORD+64 or sealed[:5] != b'SILO1':
                    raise ValueError()
                restored = strict_json(self.cipher.decrypt(sealed[5:17], sealed[17:], filename.encode('ascii')))
                if filename.startswith('schedules-'):
                    for item in restored['items'].values():
                        item['enabled'] = False; item['state'] = 'unknown'
                    nonce = secrets.token_bytes(12)
                    sealed = b'SILO1'+nonce+self.cipher.encrypt(nonce,json_bytes(restored),filename.encode('ascii'))
            except Exception as error:
                raise AccessDenied('Backup authentication failed') from error
            name = filename.rsplit('-', 1)[0]
            if not (name in {'active-project','schedules'} or re.fullmatch(r'project-[a-f0-9]{32}',name)):
                raise AccessDenied('Project backups cannot restore policy, trust anchors or model selection')
            if self._versions(name):
                raise AccessDenied('Restore into an empty vault; existing records are never overwritten')
            prepared.append((filename, sealed))
        with self.transaction():
            # Recheck under the same cross-client lock as publication.
            for filename, _ in prepared:
                if self._versions(filename.rsplit('-', 1)[0]):
                    raise AccessDenied('Restore into an empty vault; existing records are never overwritten')
            for filename, sealed in prepared:
                self.store.write(filename, lambda write, block=sealed: write(block))

    @staticmethod
    def _recovery_cipher(password,salt):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
        if not isinstance(password,str) or not 12 <= len(password) <= 1024:
            raise AccessDenied('Use a recovery password of 12 to 1024 characters')
        return AESGCM(Scrypt(salt=salt,length=32,n=2**16,r=8,p=1).derive(password.encode('utf-8')))

    def recovery_backup(self,password):
        """Explicit portable recovery export. The old key is inside the authenticated ciphertext."""
        import base64
        salt,nonce=secrets.token_bytes(16),secrets.token_bytes(12)
        header=b'SILOR1'+salt
        clear=json_bytes({'key':base64.b64encode(self._key).decode('ascii'),
                          'backup':strict_json(self.backup())})
        if len(clear)>64*1024*1024:raise AccessDenied('Recovery backup exceeds limit')
        return header+nonce+self._recovery_cipher(password,salt).encrypt(nonce,clear,header)

    def restore_recovery(self,data,password):
        import base64
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        if not isinstance(data,bytes) or not 54 <= len(data) <= 64*1024*1024+54 or data[:6]!=b'SILOR1':
            raise AccessDenied('Invalid recovery archive')
        try:
            value=strict_json(self._recovery_cipher(password,data[6:22]).decrypt(data[22:34],data[34:],data[:22]))
            if set(value)!={'key','backup'}:raise ValueError()
            key=base64.b64decode(value['key'],validate=True)
            if len(key)!=32 or value['backup']['key_id']!=hashlib.sha256(key).hexdigest():raise ValueError()
            old_cipher=AESGCM(key)
            resealed={}
            files=value['backup']['files']
            if not isinstance(files,dict) or len(files)>256:raise ValueError()
            for filename,encoded in files.items():
                if not re.fullmatch(r'(?:project-[a-f0-9]{32}|active-project|schedules)-\d{20}\.seal',filename):raise ValueError()
                original=base64.b64decode(encoded,validate=True)
                if original[:5]!=b'SILO1' or len(original)>MAX_RECORD+64:raise ValueError()
                clear=old_cipher.decrypt(original[5:17],original[17:],filename.encode('ascii'))
                strict_json(clear)
                nonce=secrets.token_bytes(12)
                sealed=b'SILO1'+nonce+self.cipher.encrypt(nonce,clear,filename.encode('ascii'))
                resealed[filename]=base64.b64encode(sealed).decode('ascii')
        except Exception as error:
            raise AccessDenied('Recovery password or archive authentication failed') from error
        self.restore(json_bytes({'format':1,'key_id':self.key_id,'files':resealed}))

    def close(self):
        self.store.close()
        self._key = b''



class ProjectStore:
    def __init__(self, vault, *, clock=time.time):
        self.vault, self.clock = vault, clock

    def create(self, name, *, retention_days=30, data_scope='synthetic'):
        if len(self.vault.names('project-')) >= 64:
            raise AccessDenied('Project limit reached; delete an unused project')
        if type(retention_days) is not int or not 1 <= retention_days <= 365:
            raise AccessDenied('Retention must be 1 to 365 days')
        project = Project(secrets.token_hex(16), name, data_scope)
        record = {'format': 1, 'project': asdict(project), 'updated': self.clock(),
                  'retention_days': retention_days, 'instructions': '', 'grants': [], 'turns': [],
                  'workflows': {}, 'configuration_id': None}
        self.vault.put('project-'+project.id, record)
        return project

    def load(self, identifier, *, allow_expired=False):
        Project(identifier, 'Project')
        value = self.vault.get('project-'+identifier)
        if value is None:
            raise AccessDenied('Unknown project')
        if (not isinstance(value, dict) or value.get('format') != 1
                or set(value) != {'format','project','updated','retention_days','instructions','grants',
                                  'turns','workflows','configuration_id'}):
            raise AccessDenied('Invalid saved project')
        Project(**value['project'])
        if (type(value['retention_days']) is not int or not 1 <= value['retention_days'] <= 365
                or type(value['updated']) not in {int,float} or value['updated'] < 0
                or not isinstance(value['instructions'],str) or len(value['instructions'].encode('utf-8')) > 8192
                or not isinstance(value['grants'],list) or len(value['grants']) > 64
                or not isinstance(value['turns'],list) or len(value['turns']) > 16
                or not isinstance(value['workflows'],dict) or len(value['workflows']) > 32):
            raise AccessDenied('Invalid saved project bounds')
        if value['project']['id'] != identifier:
            raise AccessDenied('Project identity mismatch')
        if not allow_expired and self.expired(value):
            raise AccessDenied('Project retention expired; delete it or explicitly extend retention')
        return value

    def expired(self, record):
        return self.clock() >= record['updated'] + record['retention_days'] * 86400

    def listing(self):
        result = []
        for name in self.vault.names('project-'):
            record = self.load(name[8:], allow_expired=True)
            result.append({**record['project'], 'updated': record['updated'],
                           'retention_days': record['retention_days'], 'expired': self.expired(record),
                           'turns': len(record['turns']), 'grants': len(record['grants'])})
        return result

    def save(self, record, *, touch=True):
        if touch: record['updated'] = self.clock()
        self.vault.put('project-'+record['project']['id'], record)

    def renew(self, identifier, days):
        if type(days) is not int or not 1 <= days <= 365:
            raise AccessDenied('Retention must be 1 to 365 days')
        record=self.load(identifier,allow_expired=True)
        record['retention_days']=days; self.save(record)
        return record

    def delete(self, identifier):
        self.load(identifier, allow_expired=True)
        self.vault.delete('project-'+identifier)

    def prune(self):
        removed = []
        for item in self.listing():
            if item['expired']:
                self.delete(item['id']); removed.append(item['id'])
        return removed


class ProjectSession:
    """Shared backend decorator. Persistence is opt-in per explicitly opened project."""
    def __init__(self, backend, store):
        self.backend, self.store, self.record = backend, store, None
        reserve = getattr(backend.workspace.broker, 'reserve_tree', None)
        if reserve is not None: reserve(store.vault.path)
        owner = getattr(backend, 'service', backend)
        self.base_instructions = getattr(owner, 'instructions',
                                         getattr(getattr(owner, 'harness', None), 'instructions', ''))

    def __getattr__(self, name):
        return getattr(self.backend, name)

    def model_id(self):
        manager = getattr(getattr(self.backend,'service',None),'model_manager',None)
        return manager.selected() if manager is not None else None

    @property
    def conversation(self):
        return getattr(self.backend, 'service', self.backend).conversation

    def _idle(self):
        with self.backend._guard:
            self.backend._require_idle()

    def _instructions(self, text):
        if not isinstance(text, str) or len(text.encode('utf-8')) > 8192 or '\0' in text:
            raise AccessDenied('Task instructions must be UTF-8 and at most 8 KiB')
        combined = self.base_instructions + ('\n\nProject task instructions:\n'+text if text else '')
        if len(combined.encode('utf-8')) > 8192:
            raise AccessDenied('Combined application and project instructions exceed 8 KiB')
        owner = getattr(self.backend, 'service', self.backend)
        if hasattr(owner, 'harness'):
            owner.harness.instructions = combined
        else:
            owner.instructions = combined

    def persist(self, *, touch=False):
        if self.record is None:
            return
        self.conversation.prepare(self.workspace)
        folders = self.workspace.broker.folders()
        grants = self.workspace.broker.saved_grants()
        self.record['grants'] = [dict(grant, id=folder.id) for folder, grant in zip(folders, grants, strict=True)]
        self.record['turns'] = [asdict(turn) for turn in self.conversation.turns]
        self.record['configuration_id'] = self.model_id()
        self.store.save(self.record, touch=touch)

    def ask(self, prompt):
        self._idle()
        manager = getattr(getattr(self.backend,'service',None),'model_manager',None)
        if manager is not None: manager.authorize(manager.selected(),data_scope=self.backend.project.data_scope)
        if self.record is not None and self.store.expired(self.record):
            self.backend.clear_chat(); self.persist()
            raise AccessDenied('Project retention expired; extend it explicitly before continuing')
        try:
            return self.backend.ask(prompt)
        finally:
            self.persist(touch=True)

    def create_project(self, name, *, retention_days=30):
        self._idle(); self.persist()
        project = self.store.create(name, retention_days=retention_days,
                                    data_scope=self.backend.project.data_scope)
        # New project inherits only the explicitly current grants, never another project's chat.
        self.backend.clear_chat()
        self.record = self.store.load(project.id)
        self.backend.project = project
        self._instructions(''); self.persist()
        self.store.vault.put('active-project', {'id':project.id})
        return project

    def open_project(self, identifier):
        self._idle()
        record = self.store.load(identifier)
        self.persist(); self.backend.clear_chat()
        if getattr(getattr(self.backend, 'service', None), 'code', None) is not None:
            self.backend.close_code()
        for folder in self.workspace.broker.folders():
            self.workspace.revoke(folder.id)
        mapping, failed = {}, False
        try:
            for grant in record['grants']:
                try:
                    self._protect_storage(grant['path'])
                    folder = self.workspace.broker.grant(grant['path'], grant['access'],
                        expected_identity=(grant['volume'], grant['index']))
                    mapping[grant['id']] = folder.id
                except (OSError, ValueError, RuntimeError):
                    failed = True
            self.backend.project = Project(**record['project'])
            self._instructions(record['instructions'])
            if not failed:
                for turn in record['turns']:
                    sources = tuple(replace(Source(**source), folder_id=mapping[source['folder_id']])
                                    for source in turn['sources'])
                    self.conversation.append(turn['prompt'], turn['answer'], sources,
                                             self.workspace.broker.revision)
            _, _, changed = self.conversation.prepare(self.workspace)
        except BaseException:
            self.conversation.clear()
            for folder in self.workspace.broker.folders():
                self.workspace.revoke(folder.id)
            self.record = None
            self._instructions('')
            raise
        self.record = record
        self.store.vault.put('active-project', {'id':identifier})
        self.persist()
        return {'project': self.backend.project, 'context_invalidated': failed or changed,
                'restored_grants': len(mapping)}

    def set_instructions(self, text):
        self._idle()
        if self.record is None:
            raise AccessDenied('Open a saved project first')
        self._instructions(text)
        self.record['instructions'] = text
        self.clear_chat(); self.persist(touch=True)

    def set_retention(self, days):
        self._idle()
        if self.record is None or type(days) is not int or not 1 <= days <= 365:
            raise AccessDenied('Open a project and select 1 to 365 days')
        self.record['retention_days'] = days; self.persist(touch=True)

    def _protect_storage(self, path):
        selected = Path(path).absolute()
        protected = self.store.vault.path
        if selected == protected or selected in protected.parents or protected in selected.parents:
            raise AccessDenied('Application private storage cannot be granted to the model')

    def grant(self, path, kind):
        self._protect_storage(path)
        if len(self.workspace.broker.folders()) >= 64: raise AccessDenied('Project folder limit reached')
        result = self.backend.grant(path, kind); self.persist(touch=True); return result

    def revoke(self, identifier):
        self.backend.revoke(identifier); self.persist(touch=True)

    def clear_chat(self):
        self.backend.clear_chat(); self.persist()

    def switch_model(self, identifier):
        self._idle()
        try:
            self.backend.switch_model(identifier)
        finally:
            if not self.backend.service.closed:
                reserve = getattr(self.workspace.broker, 'reserve_tree', None)
                if reserve is not None: reserve(self.store.vault.path)
                self.persist()

    def close_project(self):
        self._idle(); self.persist(); self.backend.clear_chat()
        if getattr(getattr(self.backend, 'service', None), 'code', None) is not None:
            self.backend.close_code()
        for folder in self.workspace.broker.folders():
            self.workspace.revoke(folder.id)
        self.record = None; self._instructions('')
        self.store.vault.delete('active-project')
        self.backend.project = Project('unsaved', 'Unsaved session')

    def delete_project(self, identifier):
        self._idle()
        if self.record and self.record['project']['id'] == identifier:
            self.close_project()
        self.store.delete(identifier)

    def close(self):
        self._idle()
        try:
            self.persist()
        finally:
            self.backend.close(); self.store.vault.close()


def project_data_directory(state, *, name='projects'):
    """Create an isolated private child; never broaden an existing directory ACL."""
    from .asset_integrity import ordinary
    if name not in {'projects','models','ocr'}:raise AccessDenied('Unknown application storage category')
    parent=Path(state).absolute(); ordinary(parent,directory=True)
    path=parent/name
    if path.exists():
        ordinary(path,directory=True)
        return path
    if os.name!='nt':
        path.mkdir(mode=0o700); return path
    kernel=C.WinDLL('kernel32',use_last_error=True); adv=C.WinDLL('advapi32',use_last_error=True)
    pointer=C.c_void_p; uint=C.c_uint32
    class Security(C.Structure):
        _fields_=[('length',uint),('descriptor',pointer),('inherit',C.c_int)]
    kernel.GetCurrentProcess.argtypes=[];kernel.GetCurrentProcess.restype=pointer
    kernel.CreateDirectoryW.argtypes=[C.c_wchar_p,C.POINTER(Security)];kernel.CreateDirectoryW.restype=C.c_int
    kernel.CloseHandle.argtypes=[pointer];kernel.CloseHandle.restype=C.c_int
    kernel.LocalFree.argtypes=[pointer];kernel.LocalFree.restype=pointer
    adv.OpenProcessToken.argtypes=[pointer,uint,C.POINTER(pointer)];adv.OpenProcessToken.restype=C.c_int
    adv.GetTokenInformation.argtypes=[pointer,uint,pointer,uint,C.POINTER(uint)];adv.GetTokenInformation.restype=C.c_int
    adv.ConvertSidToStringSidW.argtypes=[pointer,C.POINTER(pointer)];adv.ConvertSidToStringSidW.restype=C.c_int
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes=[C.c_wchar_p,uint,C.POINTER(pointer),pointer]
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype=C.c_int
    token,descriptor,sid_text=pointer(),pointer(),pointer()
    def check(success):
        if not success:raise AccessDenied('Private project storage creation failed')
    try:
        check(adv.OpenProcessToken(kernel.GetCurrentProcess(),8,C.byref(token)))
        needed=uint();adv.GetTokenInformation(token,1,None,0,C.byref(needed))
        if not 0<needed.value<65536:raise AccessDenied('Current account metadata is unavailable')
        buffer=C.create_string_buffer(needed.value)
        check(adv.GetTokenInformation(token,1,buffer,len(buffer),C.byref(needed)))
        check(adv.ConvertSidToStringSidW(pointer.from_buffer(buffer).value,C.byref(sid_text)))
        sid=C.wstring_at(sid_text)
        sddl=f'O:{sid}D:P(A;OICI;FA;;;{sid})(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)'
        check(adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl,1,C.byref(descriptor),None))
        security=Security(C.sizeof(Security),descriptor,0)
        check(kernel.CreateDirectoryW(str(path),C.byref(security)))
    finally:
        if descriptor.value:kernel.LocalFree(descriptor)
        if sid_text.value:kernel.LocalFree(sid_text)
        if token.value:kernel.CloseHandle(token)
    return path
