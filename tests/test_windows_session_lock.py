"""Real Windows constructor cleanup under an existing native byte-range lock."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from local_ai_appliance.windows_session import WindowsSession


@unittest.skipUnless(os.name == 'nt', 'Native Windows byte-range lock required')
class WindowsSessionLockTests(unittest.TestCase):
    def test_peer_refusal_closes_failed_handle_and_preserves_owner_and_recovery(self):
        with tempfile.TemporaryDirectory(prefix='silo-lock-test-') as temp:
            root=Path(temp);opened=[];original_open=Path.open
            def tracked(path,*args,**kwargs):
                stream=original_open(path,*args,**kwargs)
                if path.name=='session.lock':opened.append(stream)
                return stream
            with patch.object(Path,'open',tracked), patch('local_ai_appliance.machine_security.machine_directory',return_value=root/'unprovisioned-machine-fixture'):
                owner=WindowsSession(root,evaluation=True)
                try:
                    with self.assertRaisesRegex(RuntimeError,'already running'):
                        WindowsSession(root,evaluation=True)
                    self.assertTrue(opened[-1].closed)
                    self.assertFalse(opened[0].closed)
                finally:owner.close()
                recovered=WindowsSession(root,evaluation=True)
                recovered.close()
                self.assertTrue(all(stream.closed for stream in opened))


if __name__=='__main__':unittest.main()
