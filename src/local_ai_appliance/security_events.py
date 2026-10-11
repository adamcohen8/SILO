"""Metadata-only security events. Native records are owned by Windows Event Log.

The SILO source must be registered by the deployment administrator. No event
source, ACL, retention setting or remote destination is created at runtime.
"""
import ctypes as C
import hashlib
import os
import re
import secrets
import threading
import time

from .folders import AccessDenied
from .model import json_bytes

EVENTS = frozenset({'session', 'grant', 'revoke', 'read', 'list', 'review', 'save',
                   'export', 'policy', 'denial', 'execution', 'cleanup', 'backup',
                   'restore', 'retention', 'integrity', 'schedule'})


def identifier(value):
    return hashlib.sha256(str(value).encode('utf-8')).hexdigest()


class SecurityAudit:
    def __init__(self, sink, *, clock=time.time):
        self.sink, self.clock = sink, clock
        self.session = secrets.token_hex(16)
        self._guard = threading.RLock()
        self.sequence = 0
        self.failed = False

    def emit(self, event, outcome, **metadata):
        # Deliberately no arbitrary strings, paths, exception text or prompts.
        if event not in EVENTS or outcome not in {'attempt', 'success', 'denied', 'failed'}:
            raise AccessDenied('Unknown security audit event')
        if set(metadata) - {'object_sha256', 'policy_sha256', 'release_sha256', 'operation_id', 'bytes', 'revision', 'code'}:
            raise AccessDenied('Security audit metadata field is not registered')
        for key, value in metadata.items():
            if key.endswith('sha256') and (not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value)):
                raise AccessDenied('Invalid audit object digest')
            if key == 'operation_id' and (not isinstance(value, str) or not re.fullmatch('[a-f0-9]{32}', value)):
                raise AccessDenied('Invalid audit operation identity')
            if key in {'bytes', 'revision', 'code'} and (type(value) is not int or not 0 <= value < 2**63):
                raise AccessDenied('Invalid audit numeric metadata')
        with self._guard:
            if self.failed:
                raise AccessDenied('Security audit unavailable; protected operations are disabled')
            self.sequence += 1
            record = {'format': 1, 'session': self.session, 'sequence': self.sequence,
                      'time_ns': int(self.clock() * 1_000_000_000), 'event': event,
                      'outcome': outcome, **metadata}
            try:
                self.sink(json_bytes(record))
            except Exception:
                self.failed = True
                raise AccessDenied('Security audit write failed; operation outcome may need reconciliation') from None


class WindowsEventSink:
    """Use the registered source only; Application log ACL/retention is host-owned."""
    def __init__(self):
        if os.name != 'nt':
            raise AccessDenied('Protected auditing requires native Windows Event Log')
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                    r'SYSTEM\CurrentControlSet\Services\EventLog\Application\SILO',
                    0, winreg.KEY_READ):
                pass
        except OSError:
            raise AccessDenied('Administrator must register the SILO Event Log source') from None
        self.adv = C.WinDLL('advapi32', use_last_error=True)
        self.adv.RegisterEventSourceW.argtypes = [C.c_wchar_p, C.c_wchar_p]
        self.adv.RegisterEventSourceW.restype = C.c_void_p
        self.adv.ReportEventW.argtypes = [C.c_void_p, C.c_ushort, C.c_ushort, C.c_uint32,
                                        C.c_void_p, C.c_ushort, C.c_uint32,
                                        C.POINTER(C.c_wchar_p), C.c_void_p]
        self.adv.ReportEventW.restype = C.c_int
        self.adv.DeregisterEventSource.argtypes = [C.c_void_p]
        self.adv.DeregisterEventSource.restype = C.c_int
        self.handle = self.adv.RegisterEventSourceW(None, 'SILO')
        if not self.handle:
            raise AccessDenied('Windows security event source is unavailable')
        kernel=C.WinDLL('kernel32',use_last_error=True)
        kernel.GetCurrentProcess.argtypes=[]; kernel.GetCurrentProcess.restype=C.c_void_p
        kernel.CloseHandle.argtypes=[C.c_void_p]
        self.adv.OpenProcessToken.argtypes=[C.c_void_p,C.c_uint32,C.POINTER(C.c_void_p)]
        self.adv.OpenProcessToken.restype=C.c_int
        self.adv.GetTokenInformation.argtypes=[C.c_void_p,C.c_uint32,C.c_void_p,C.c_uint32,C.POINTER(C.c_uint32)]
        self.adv.GetTokenInformation.restype=C.c_int
        token,size=C.c_void_p(),C.c_uint32()
        try:
            if not self.adv.OpenProcessToken(kernel.GetCurrentProcess(),8,C.byref(token)):
                raise AccessDenied('Security event actor unavailable')
            self.adv.GetTokenInformation(token,1,None,0,C.byref(size))
            if not 0 < size.value <= 65536: raise AccessDenied('Security event actor exceeds bounds')
            self.actor=C.create_string_buffer(size.value)
            if not self.adv.GetTokenInformation(token,1,self.actor,len(self.actor),C.byref(size)):
                raise AccessDenied('Security event actor inspection failed')
            self.actor_sid=C.c_void_p.from_buffer(self.actor).value
        except BaseException:
            self.close(); raise
        finally:
            if token.value: kernel.CloseHandle(token)

    def __call__(self, data):
        if len(data) > 4096 or not self.handle:
            raise AccessDenied('Invalid security event size or source')
        strings = (C.c_wchar_p * 1)(data.decode('utf-8'))
        if not self.adv.ReportEventW(self.handle, 4, 0, 1000, self.actor_sid, 1, 0, strings, None):
            raise AccessDenied('Windows refused the security event')

    def close(self):
        if self.handle:
            handle, self.handle = self.handle, None
            if not self.adv.DeregisterEventSource(handle):
                raise AccessDenied('Security event source cleanup failed')
