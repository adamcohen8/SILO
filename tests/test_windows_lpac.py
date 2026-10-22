"""Portable API contracts and explicit native suspended-token controls for #34."""
import ctypes as C
import itertools
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from local_ai_appliance import windows_container as wc
from local_ai_appliance.windows_lpac import TokenAccessProbe, verify_lpac


def put(pointer, kind, value):
    C.cast(pointer, C.POINTER(kind))[0] = value


class Function:
    def __init__(self, call):
        self.call = call
    def __call__(self, *args):
        return self.call(*args)


class ProbeFixture:
    def __init__(self, *, outcomes=(False, False, True), api_failure=None):
        self.closed, self.freed, self.descriptors, self.calls = [], [], {}, []
        self.error, self.api_failure, self.outcomes = 0, api_failure, iter(outcomes)
        self.owner = SimpleNamespace(sid_text='S-1-15-2-123-456',
            kernel=SimpleNamespace(CloseHandle=lambda p: self.closed.append(p.value) or 1,
                                   LocalFree=lambda p: self.freed.append(p.value)),
            adv=SimpleNamespace(DuplicateTokenEx=Function(self.duplicate),
                ConvertStringSecurityDescriptorToSecurityDescriptorW=Function(self.descriptor),
                AccessCheck=Function(self.access)),
            _token_value=lambda token, kind: C.create_string_buffer((1).to_bytes(4, 'little'), 4))
    def duplicate(self, token, access, attrs, level, kind, output):
        if (access, attrs, level, kind) != (8, None, 2, 2):
            raise AssertionError('Token duplication must request only query access and impersonation')
        put(output, wc.PTR, 900)
        return 1
    def descriptor(self, sddl, revision, output, size):
        self.descriptors[len(self.descriptors)+1] = sddl
        put(output, wc.PTR, len(self.descriptors))
        return 1
    def access(self, descriptor, token, desired, mapping, privileges, length, granted, allowed):
        self.calls.append(self.descriptors[descriptor.value])
        if token.value != 900 or desired != 1:
            raise AssertionError('AccessCheck must use the duplicated token and specific read access')
        if self.api_failure is not None:
            self.error = self.api_failure
            return 0
        value = next(self.outcomes)
        put(length, wc.U32, 8)
        put(granted, wc.U32, 1 if value else 0)
        put(allowed, wc.BOOL, int(value))
        return 1


class LPACContracts(unittest.TestCase):
    def test_only_lpac_control_pattern_is_accepted_and_resources_are_freed(self):
        for outcomes in itertools.product((False, True), repeat=3):
            with self.subTest(outcomes=outcomes):
                fixture = ProbeFixture(outcomes=outcomes)
                if outcomes == (False, False, True):
                    evidence = verify_lpac(fixture.owner, 123)
                    self.assertTrue(evidence['lpac'])
                    self.assertEqual(evidence['lpac_verification'], 'accesscheck-aap-profile-v1')
                else:
                    with self.assertRaisesRegex(OSError, 'stays suspended'):
                        verify_lpac(fixture.owner, 123)
                self.assertEqual(fixture.closed, [900])
                self.assertEqual(fixture.freed, [1, 2, 3])
                self.assertEqual(fixture.calls, ['O:SYG:SYD:P(A;;0x1;;;WD)',
                    'O:SYG:SYD:P(A;;0x1;;;WD)(A;;0x1;;;S-1-15-2-1)',
                    'O:SYG:SYD:P(A;;0x1;;;WD)(A;;0x1;;;S-1-15-2-123-456)'])

    def test_accesscheck_api_failure_is_not_treated_as_denied_access(self):
        for error in (5, 87, 122):
            with self.subTest(error=error):
                fixture = ProbeFixture(api_failure=error)
                with patch.object(C, 'get_last_error', lambda: fixture.error, create=True):
                    with self.assertRaises(OSError) as caught:
                        verify_lpac(fixture.owner, 123)
                self.assertEqual(caught.exception.winerror, error)
                self.assertEqual(fixture.closed, [900])
                self.assertEqual(fixture.freed, [1])

    def test_short_or_non_appcontainer_token_is_rejected_before_access_probe(self):
        for data in (b'', b'\x01', b'\0'*4, b'\x02\0\0\0', b'\x01\0\0\0extra'):
            with self.subTest(data=data):
                fixture = ProbeFixture()
                fixture.owner._token_value = lambda token, kind: C.create_string_buffer(data, len(data))
                with self.assertRaisesRegex(OSError, 'requires an AppContainer'):
                    verify_lpac(fixture.owner, 123)
                self.assertEqual(fixture.calls, [])

    def test_cleanup_failure_prevents_verified_evidence_from_being_returned(self):
        for operation in ('LocalFree', 'CloseHandle'):
            with self.subTest(operation=operation):
                fixture = ProbeFixture()
                setattr(fixture.owner.kernel, operation, Mock(return_value=1 if operation == 'LocalFree' else 0))
                with patch.object(C, 'get_last_error', return_value=6, create=True):
                    with self.assertRaisesRegex(OSError, 'cleanup failed') as caught:
                        verify_lpac(fixture.owner, 123)
                self.assertEqual(caught.exception.winerror, 6)
                if operation == 'LocalFree':
                    self.assertEqual(fixture.closed, [900])
                else:
                    self.assertEqual(fixture.freed, [1, 2, 3])

    def test_accesscheck_retries_only_a_bounded_privilege_buffer_request(self):
        fixture = ProbeFixture()
        native = fixture.owner.adv.AccessCheck.call
        capacities = []
        def access(*args):
            length = args[5]
            capacities.append(C.cast(length, C.POINTER(wc.U32)).contents.value)
            if len(capacities) == 1:
                put(length, wc.U32, 2048)
                fixture.error = 122
                return 0
            return native(*args)
        fixture.owner.adv.AccessCheck.call = access
        with patch.object(C, 'get_last_error', lambda: fixture.error, create=True):
            self.assertTrue(verify_lpac(fixture.owner, 123)['lpac'])
        self.assertEqual(capacities, [1024, 2048, 1024, 1024])
        self.assertEqual(fixture.closed, [900])
        self.assertEqual(fixture.freed, [1, 2, 3])

    def test_oversized_or_inconsistent_access_data_is_never_accepted(self):
        for oversized in (False, True):
            with self.subTest(oversized=oversized):
                fixture = ProbeFixture()
                def access(descriptor, token, desired, mapping, privileges, length, granted, allowed):
                    if oversized:
                        put(length, wc.U32, 65537)
                        fixture.error = 122
                        return 0
                    put(length, wc.U32, 8)
                    put(allowed, wc.BOOL, 0)
                    put(granted, wc.U32, 1)  # Denied access cannot grant a right.
                    return 1
                fixture.owner.adv.AccessCheck.call = access
                with patch.object(C, 'get_last_error', lambda: fixture.error, create=True):
                    with self.assertRaises(OSError):
                        verify_lpac(fixture.owner, 123)
                self.assertEqual(fixture.closed, [900])
                self.assertEqual(fixture.freed, [1])

    def test_runner_refuses_before_impersonation_or_registry_changes_on_probe_error(self):
        from local_ai_appliance.windows_code_runner import RunnerContainer
        runner = RunnerContainer.__new__(RunnerContainer)
        def opened(process, access, output):
            self.assertEqual(access, 14)  # QUERY | DUPLICATE | IMPERSONATE
            put(output, wc.PTR, 123)
            return 1
        functions = {name: Function(Mock()) for name in ('ImpersonateLoggedOnUser', 'RevertToSelf',
            'RegCloseKey', 'RegEnumKeyExW', 'RegOpenKeyExW')}
        runner.adv = SimpleNamespace(OpenProcessToken=opened, **functions)
        runner.userenv = SimpleNamespace(GetAppContainerRegistryLocation=Function(Mock()))
        runner.kernel = SimpleNamespace(CloseHandle=Mock())
        process = SimpleNamespace(info=SimpleNamespace(process=456), token_evidence={})
        with patch('local_ai_appliance.windows_lpac.verify_lpac', side_effect=OSError('probe failed')):
            with self.assertRaisesRegex(OSError, 'probe failed'):
                runner.prepare_process(process)
        functions['ImpersonateLoggedOnUser'].call.assert_not_called()
        runner.userenv.GetAppContainerRegistryLocation.call.assert_not_called()
        self.assertEqual(process.token_evidence, {})
        self.assertEqual(runner.kernel.CloseHandle.call_args.args[0].value, 123)

    def test_token_query_failure_keeps_real_error_and_class_in_diagnostics(self):
        owner = wc.AppContainer.__new__(wc.AppContainer)
        owner.adv = SimpleNamespace(GetTokenInformation=lambda *args: 0)
        with patch.object(C, 'get_last_error', return_value=87, create=True):
            with self.assertRaises(OSError) as caught:
                owner._token_value(123, 46)
        self.assertEqual(caught.exception.winerror, 87)
        self.assertIn('class 46 size query; required=0', str(caught.exception))

    def test_token_query_bounds_errors_and_truncated_results_fail_closed(self):
        for required, read_success, returned in ((65537, 1, 65537), (4, 0, 4), (4, 1, 5), (4, 1, 0)):
            with self.subTest(required=required, read_success=read_success, returned=returned):
                owner = wc.AppContainer.__new__(wc.AppContainer)
                def query(token, kind, buffer, length, size):
                    put(size, wc.U32, required if buffer is None else returned)
                    return 0 if buffer is None else read_success
                owner.adv = SimpleNamespace(GetTokenInformation=query)
                with patch.object(C, 'get_last_error', return_value=122, create=True):
                    with self.assertRaises(OSError):
                        owner._token_value(123, 29)

    def test_token_query_returns_only_actual_bytes_and_reports_data_failure(self):
        owner = wc.AppContainer.__new__(wc.AppContainer)
        def query(token, kind, buffer, length, size):
            put(size, wc.U32, 8 if buffer is None else 4)
            if buffer is not None:
                C.memmove(buffer, b'\x01\0\0\0', 4)
                return 1
            return 0
        owner.adv = SimpleNamespace(GetTokenInformation=query)
        with patch.object(C, 'get_last_error', return_value=122, create=True):
            data = owner._token_value(123, 29)
        self.assertEqual(bytes(data), b'\x01\0\0\0')
        self.assertEqual(len(data), 4)
        def fail_read(token, kind, buffer, length, size):
            put(size, wc.U32, 4)
            return 0
        owner.adv.GetTokenInformation = fail_read
        with patch.object(C, 'get_last_error', side_effect=[122, 5], create=True):
            with self.assertRaises(OSError) as caught:
                owner._token_value(123, 29)
        self.assertEqual(caught.exception.winerror, 5)
        self.assertIn('class 29 data query', str(caught.exception))


@unittest.skipUnless(os.name == 'nt' and os.environ.get('SILO_RUN_NATIVE_LPAC_PROBES') == '1',
                     'Explicit Windows suspended-token probes required; no model or worker is resumed')
class NativeLPACTokenTests(unittest.TestCase):
    def test_ordinary_host_token_is_not_lpac(self):
        # No profile, certificate, enrollment, policy or ACL change.
        owner = wc.AppContainer.__new__(wc.AppContainer)
        owner.adv = C.WinDLL('advapi32', use_last_error=True)
        owner.kernel = C.WinDLL('kernel32', use_last_error=True)
        wc.bind(owner.adv, 'OpenProcessToken', wc.BOOL, [wc.PTR, wc.U32, C.POINTER(wc.PTR)])
        wc.bind(owner.adv, 'GetTokenInformation', wc.BOOL,
                [wc.PTR, wc.U32, wc.PTR, wc.U32, C.POINTER(wc.U32)])
        wc.bind(owner.kernel, 'CloseHandle', wc.BOOL, [wc.PTR])
        token = wc.PTR()
        wc.ok(owner.adv.OpenProcessToken(wc.PTR(-1), 10, C.byref(token)))
        try:
            with self.assertRaisesRegex(OSError, 'requires an AppContainer'):
                verify_lpac(owner, token)
        finally:
            owner.kernel.CloseHandle(token)

    def test_plain_appcontainer_and_lpac_are_distinguished_before_resume(self):
        class Captured(Exception):
            pass
        for use_lpac in (False, True):
            with self.subTest(lpac=use_lpac):
                class ProbeContainer(wc.AppContainer):
                    lpac = use_lpac
                    def verify_token(self, process):
                        self.observed = super().verify_token(process)
                        token = wc.PTR()
                        wc.ok(self.adv.OpenProcessToken(process, 10, C.byref(token)))
                        try:
                            self.checks = TokenAccessProbe(self, token).run()
                            if use_lpac:
                                self.observed.update(verify_lpac(self, token))
                            else:
                                with self_test.assertRaisesRegex(OSError, 'stays suspended'):
                                    verify_lpac(self, token)
                        finally:
                            self.kernel.CloseHandle(token)
                        raise Captured()  # Deliberately never ResumeThread.
                self_test = self
                with ProbeContainer(evaluation=True, private_desktop=False) as owner:
                    owner.kernel.ResumeThread = Mock(side_effect=AssertionError('Must not resume inert token probe'))
                    with self.assertRaises(Captured):
                        owner.launch([str(Path(sys.executable).resolve()), '-I', '-B', '-c', 'pass'],
                                     cwd=Path(sys.executable).resolve().parent)
                    owner.kernel.ResumeThread.assert_not_called()
                    self.assertEqual(owner.checks, {'everyone': False,
                        'all_application_packages': not use_lpac, 'profile': True})
                    self.assertEqual(owner.observed.get('lpac', False), use_lpac)
                    self.assertEqual(owner.processes, [])
                self.assertTrue(owner.closed)
