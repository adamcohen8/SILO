"""Native attacks on the evaluation worker's actual private pipe protocol."""
import os
from pathlib import Path
import unittest

from local_ai_appliance.windows_container import AppContainer
from local_ai_appliance.windows_model import WindowsSocketChatModel
from local_ai_appliance.model import AgentError

ROOT = Path(__file__).resolve().parents[1]
from native_test_support import native_worker_path, verified_native_worker
SOFTWARE = native_worker_path()
PREAMBLE = "import sys,json;f=json.loads(sys.stdin.buffer.readline());"


@unittest.skipUnless(os.name == 'nt' and (SOFTWARE/'python.exe').exists(), 'Staged native evaluation interpreter required')
class WindowsContainerTests(unittest.TestCase):
    def setUp(self):
        verified_native_worker()
        self.container = AppContainer(evaluation=True)
        self.container.allow_read(SOFTWARE, directory=True)

    def tearDown(self):
        self.container.close()

    def launch(self, script):
        return self.container.launch([str(SOFTWARE/'python.exe'), '-I', '-B', '-c', script], cwd=SOFTWARE)

    def test_private_pipe_round_trip_is_session_bound(self):
        script = PREAMBLE + "f.update(sequence=1,kind='request',payload={'op':'ping'});print(json.dumps(f),flush=True);r=json.loads(sys.stdin.buffer.readline());f.update(sequence=2,kind='result',payload=r['payload']);print(json.dumps(f),flush=True)"
        process = self.launch(script)
        seen = []
        result, _ = process.exchange({'synthetic': True}, lambda request: seen.append(request) or {'ack': True})
        self.assertEqual(result, {'ack': True})
        self.assertEqual(seen, [{'op': 'ping'}])
        self.assertTrue(process.token_evidence['appcontainer'])
        self.assertEqual(process.token_evidence['capability_count'], 0)
        self.assertFalse(process.token_evidence['profile_loopback_exempt'])

    def test_wrong_session_rejected_before_host_dispatch(self):
        process = self.launch(PREAMBLE + "f.update(session='wrong',sequence=1,kind='request',payload={});print(json.dumps(f),flush=True)")
        seen = []
        with self.assertRaisesRegex(OSError, 'Malformed or replayed'):
            process.exchange({}, lambda value: seen.append(value))
        self.assertEqual(seen, [])

    def test_replayed_frame_rejected_without_second_dispatch(self):
        script = PREAMBLE + "f.update(sequence=1,kind='request',payload={'op':'ping'});print(json.dumps(f),flush=True);sys.stdin.buffer.readline();print(json.dumps(f),flush=True)"
        seen = []
        with self.assertRaisesRegex(OSError, 'Malformed or replayed'):
            self.launch(script).exchange({}, lambda value: seen.append(value) or {})
        self.assertEqual(seen, [{'op': 'ping'}])

    def test_oversized_or_unknown_frames_do_not_dispatch(self):
        for script in ("import sys;sys.stdout.write('x'*(256*1024+1));sys.stdout.flush()",
                       PREAMBLE + "f.update(sequence=1,kind='approve',payload={});print(json.dumps(f),flush=True)"):
            seen = []
            with self.assertRaises(OSError):
                self.launch(script).exchange({}, lambda value: seen.append(value))
            self.assertEqual(seen, [])

    def test_timeout_kills_owned_worker_and_next_worker_runs(self):
        with self.assertRaises(TimeoutError):
            self.launch("import time;time.sleep(60)").communicate(timeout=0.2)
        code, output, _ = self.launch("print('synthetic recovery')").communicate(timeout=5)
        self.assertEqual(code, 0)
        self.assertIn(b'synthetic recovery', output)

    def test_socket_transport_requires_explicit_evaluation_and_token(self):
        for args in ({'evaluation': False, 'api_token': 'synthetic_explicit_session_token'},
                     {'evaluation': True, 'api_token': None}):
            with self.assertRaises(AgentError):
                WindowsSocketChatModel(str(SOFTWARE/'s.sock'), 'test', **args)
