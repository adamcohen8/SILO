"""Native-only staging/ACL fixtures. All files are synthetic and temporary."""
import ctypes as C
import os
from pathlib import Path
import tempfile
import unittest

from local_ai_appliance.windows_native import NativeFiles, HANDLE, U32, I32
from local_ai_appliance.managed_code_storage import current_user_sid
import test_installation as portable


def private_acl(path):
    native = NativeFiles(); adv = C.WinDLL('advapi32', use_last_error=True)
    NativeFiles._bind(adv, 'GetSecurityInfo', U32, [HANDLE, U32, U32] + [C.POINTER(HANDLE)] * 5)
    NativeFiles._bind(adv, 'ConvertSidToStringSidW', I32, [HANDLE, C.POINTER(HANDLE)])
    NativeFiles._bind(adv, 'ConvertStringSecurityDescriptorToSecurityDescriptorW', I32,
                     [C.c_wchar_p, U32, C.POINTER(HANDLE), C.POINTER(U32)])
    NativeFiles._bind(adv, 'SetFileSecurityW', I32, [C.c_wchar_p, U32, HANDLE])
    NativeFiles._bind(native.kernel, 'LocalFree', HANDLE, [HANDLE])
    handle = native.kernel.CreateFileW(str(path), 0x20000, 7, None, 3, 0x02200000, None)
    if handle in {None, C.c_void_p(-1).value}: raise OSError('Synthetic ACL fixture open failed')
    owner, group, dacl, sacl, descriptor, sid_text, private = (HANDLE() for _ in range(7))
    try:
        if adv.GetSecurityInfo(handle, 1, 1, C.byref(owner), C.byref(group), C.byref(dacl),
                               C.byref(sacl), C.byref(descriptor)) != 0: raise OSError('Fixture owner unavailable')
        native._ok(adv.ConvertSidToStringSidW(owner, C.byref(sid_text)))
        # Elevated-created temporary folders can initially belong to Administrators.
        sid = current_user_sid()
        sddl = f'O:{sid}D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;{sid})'
        native._ok(adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, C.byref(private), None))
        native._ok(adv.SetFileSecurityW(str(path), 0x80000005, private))
    finally:
        native.close(handle)
        for pointer in (private, sid_text, descriptor):
            if pointer.value: native.kernel.LocalFree(pointer)


@unittest.skipUnless(os.name == 'nt', 'Native Windows ACL/staging candidate fixtures')
class WindowsInstallationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.bundle = self.root / 'bundle'; self.bundle.mkdir()
        self.store = self.root / 'private'; self.store.mkdir(); private_acl(self.store)
        self.digest = portable.synthetic_bundle(self.bundle)
        self.payload = self.store / ('tx-' + self.digest) / 'payload'

    def run_action(self, action, **kwargs):
        from local_ai_appliance.installation import operate
        return operate(action, self.bundle, self.digest, state_root=self.store, development=True,
                       windows_validation=True, **kwargs)

    test_stage_idempotence_and_no_payload_execution = portable.InstallationTests.test_stage_idempotence_and_no_payload_execution
    test_reboot_requires_changed_boot_then_validation = portable.InstallationTests.test_reboot_requires_changed_boot_then_validation
    test_rollback_owned_payload_only_and_journal_retained = portable.InstallationTests.test_rollback_owned_payload_only_and_journal_retained
    test_modified_or_unowned_content_preserved = portable.InstallationTests.test_modified_or_unowned_content_preserved
    test_source_corruption_and_staging_failure_never_ready = portable.InstallationTests.test_source_corruption_and_staging_failure_never_ready

    def test_public_acl_denied(self):
        from local_ai_appliance.install_store import Store
        from local_ai_appliance.bundle import BundleError
        unsafe = self.root / 'inherited'; unsafe.mkdir()
        with self.assertRaises(BundleError):
            with Store(unsafe, windows_validation=True): pass
