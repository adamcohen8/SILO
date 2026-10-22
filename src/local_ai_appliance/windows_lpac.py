"""Verify LPAC's documented access semantics before resuming a worker.

TokenIsLessPrivilegedAppContainer (46) is rejected by GetTokenInformation on
the reported Windows build. Do not guess private attributes or accept a query
failure. Instead require Windows AccessCheck to deny an ALL_APPLICATION_PACKAGES
grant while granting the exact profile SID. An Everyone-only denial is a
negative control. API failures are never interpreted as access denials.

The caller first verifies AppContainer identity, zero capabilities, low integrity
and the expected profile on this same suspended process. This is an engineering
verification method, still requiring independent native review/acceptance.
"""
import ctypes as C

from .windows_container import BOOL, PTR, U32, WSTR, bind, native_error


class GenericMapping(C.Structure):
    _fields_ = [("read", U32), ("write", U32), ("execute", U32), ("all", U32)]


class TokenAccessProbe:
    def __init__(self, owner, token):
        self.owner, self.token = owner, token
        bind(owner.adv, 'DuplicateTokenEx', BOOL,
             [PTR, U32, PTR, U32, U32, C.POINTER(PTR)])
        bind(owner.adv, 'ConvertStringSecurityDescriptorToSecurityDescriptorW', BOOL,
             [WSTR, U32, C.POINTER(PTR), C.POINTER(U32)])
        bind(owner.adv, 'AccessCheck', BOOL,
             [PTR, PTR, U32, C.POINTER(GenericMapping), PTR, C.POINTER(U32),
              C.POINTER(U32), C.POINTER(BOOL)])

    def check(self, token, sid=None):
        # Specific read bit 1, not GENERIC_READ: no privilege or owner rights.
        # Owner/group are required by AccessCheck. These are in-memory test
        # descriptors; no object, ACL, token, privilege or host policy is edited.
        sddl = 'O:SYG:SYD:P(A;;0x1;;;WD)'
        if sid is not None:
            sddl += f'(A;;0x1;;;{sid})'
        descriptor = PTR()
        if not self.owner.adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                sddl, 1, C.byref(descriptor), None):
            raise native_error('LPAC probe security descriptor creation failed')
        try:
            mapping = GenericMapping(1, 2, 4, 7)
            # Bounded retry only for the documented insufficient-buffer result.
            capacity = 1024
            for attempt in range(2):
                privileges = C.create_string_buffer(capacity)
                length, granted, allowed = U32(capacity), U32(), BOOL()
                success = self.owner.adv.AccessCheck(descriptor, token, 1,
                    C.byref(mapping), privileges, C.byref(length), C.byref(granted), C.byref(allowed))
                if success:
                    if (not 0 < length.value <= capacity or allowed.value not in (0, 1)
                            or granted.value != (1 if allowed.value else 0)):
                        raise native_error('LPAC probe returned inconsistent access data', 13)
                    return bool(allowed.value)
                error = C.get_last_error()
                if attempt == 0 and error == 122 and capacity < length.value <= 65536:
                    capacity = length.value
                    continue
                raise native_error('LPAC AccessCheck failed', error)
        finally:
            if self.owner.kernel.LocalFree(descriptor):
                raise native_error('LPAC probe security descriptor cleanup failed')

    def run(self):
        duplicate = PTR()
        # TOKEN_QUERY; SecurityImpersonation; TokenImpersonation. The source
        # handle must include TOKEN_DUPLICATE; no thread impersonation needed.
        if not self.owner.adv.DuplicateTokenEx(self.token, 8, None, 2, 2, C.byref(duplicate)):
            raise native_error('LPAC probe token duplication failed')
        try:
            return {
                'everyone': self.check(duplicate),
                'all_application_packages': self.check(duplicate, 'S-1-15-2-1'),
                'profile': self.check(duplicate, self.owner.sid_text),
            }
        finally:
            if not self.owner.kernel.CloseHandle(duplicate):
                raise native_error('LPAC probe duplicated token cleanup failed')


def verify_lpac(owner, token):
    contained = owner._token_value(token, 29)  # Documented DWORD query.
    if len(contained) != C.sizeof(U32) or U32.from_buffer(contained).value != 1:
        raise OSError('LPAC verification requires an AppContainer token')
    checks = TokenAccessProbe(owner, token).run()
    if checks != {'everyone': False, 'all_application_packages': False, 'profile': True}:
        raise OSError('Runner token failed LPAC access verification; process stays suspended')
    return {'lpac': True, 'lpac_verification': 'accesscheck-aap-profile-v1',
            'lpac_access_checks': checks}
