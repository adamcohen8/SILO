"""Native checks only. Missing provisioning/skips cannot authorize a release."""
import os
import unittest
from local_ai_appliance.folders import AccessDenied


@unittest.skipUnless(os.name=='nt','Requires native Windows and administrator-provisioned security state')
class WindowsAuthorityTests(unittest.TestCase):
    def test_ordinary_process_cannot_update_fixed_machine_state(self):
        import ctypes
        from local_ai_appliance.machine_security import MachineStore,machine_directory
        if ctypes.windll.shell32.IsUserAnAdmin():self.skipTest('Run this authority test as an ordinary user')
        if not machine_directory().exists():self.skipTest('Independent administrator provisioning is required')
        store=MachineStore()
        try:
            original=store.get('trust-anchor')
            with self.assertRaises(AccessDenied):store.put('trust-anchor',{'key':'synthetic forged fixture'})
            self.assertEqual(store.get('trust-anchor'),original)
            with self.assertRaises(AccessDenied):MachineStore(machine_directory().parent/'user-override')
        finally:store.close()

    def test_notification_registration_and_sticky_failure(self):
        from local_ai_appliance.lifecycle_security import WindowsLifecycle
        lifecycle=WindowsLifecycle()
        try:
            lifecycle.check()
            # Contract check, not evidence of actual adapter/sleep events.
            lifecycle.changed.set()
            with self.assertRaises(AccessDenied):lifecycle.check()
        finally:lifecycle.close()
