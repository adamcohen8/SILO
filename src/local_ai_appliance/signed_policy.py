"""Detached Ed25519 policy and release signatures with explicit trust enrollment."""
import base64
import hashlib
import re
import time

from .folders import AccessDenied
from .model import strict_json


def canonical(value):
    import json
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def sign_document(value, private_key):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    return canonical({'payload':value,'signature':base64.b64encode(
        Ed25519PrivateKey.from_private_bytes(private_key).sign(canonical(value))).decode('ascii')})


def verify_document(data, public_key, expected_key_sha256, *, limit=1024*1024):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    if (not isinstance(public_key,bytes) or len(public_key) != 32
            or not isinstance(expected_key_sha256,str) or not re.fullmatch(r'[a-f0-9]{64}',expected_key_sha256)
            or hashlib.sha256(public_key).hexdigest() != expected_key_sha256 or len(data) > limit):
        raise AccessDenied('Signature trust anchor or size does not match independent host policy')
    try:
        envelope = strict_json(data)
        if set(envelope) != {'payload','signature'}:
            raise ValueError()
        signature = base64.b64decode(envelope['signature'],validate=True)
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature,canonical(envelope['payload']))
        return envelope['payload']
    except Exception as error:
        raise AccessDenied('Detached signature verification failed') from error


def administrative_access(*, development=False):
    import os
    if development and os.name != 'nt': return
    if os.name != 'nt': raise AccessDenied('Administrative enrollment requires native Windows')
    import ctypes
    if not ctypes.windll.shell32.IsUserAnAdmin():
        raise AccessDenied('Run the explicit policy enrollment/update command as administrator')


class SignedPolicyStore:
    def __init__(self,vault,*,clock=time.time):
        import os
        if os.name == 'nt' and not getattr(vault, 'administrator_owned', False):
            raise AccessDenied('Native administrative policy requires the protected machine store, not a user project vault')
        self.vault,self.clock = vault,clock

    def enroll(self,public_key,expected_sha256,*,development=False):
        administrative_access(development=development)
        if len(public_key) != 32 or hashlib.sha256(public_key).hexdigest() != expected_sha256:
            raise AccessDenied('Supply the independently verified public-key SHA-256')
        with self.vault.transaction():
            existing = self.vault.get('trust-anchor')
            if existing is not None:
                raise AccessDenied('Trust anchor already enrolled; key rotation requires a separate reviewed migration')
            self.vault.put('trust-anchor',{'key':base64.b64encode(public_key).decode('ascii'),
                                         'sha256':expected_sha256})

    def verify(self,data):
        anchor = self.vault.get('trust-anchor')
        if anchor is None: raise AccessDenied('Enroll an independent organization public key first')
        return verify_document(data,base64.b64decode(anchor['key'],validate=True),anchor['sha256'])

    def update(self,data,validate,*,development=False):
        administrative_access(development=development)
        value = self.verify(data); validate(value)
        if (type(value.get('sequence')) is not int or value['sequence'] < 1
                or type(value.get('expires')) not in {int,float} or value['expires'] <= self.clock()):
            raise AccessDenied('Policy is expired or has an invalid sequence')
        with self.vault.transaction():
            previous = self.vault.get('active-policy')
            if previous and value['sequence'] <= previous['sequence']:
                raise AccessDenied('Policy rollback or replay denied')
            self.vault.put('active-policy',{'sequence':value['sequence'],
                'envelope':base64.b64encode(data).decode('ascii')})
        return value

    def current(self,validate):
        saved = self.vault.get('active-policy')
        if saved is None: return None
        value = self.verify(base64.b64decode(saved['envelope'],validate=True)); validate(value)
        if value['sequence'] != saved['sequence'] or value['expires'] <= self.clock():
            raise AccessDenied('Active policy is expired or inconsistent')
        return value
