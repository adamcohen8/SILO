import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from local_ai_appliance.backend import PortableSession, SessionCancelled, WindowsSessionAdapter
from local_ai_appliance.cli import interact
from local_ai_appliance.contracts import Project, SessionBackend, WorkspaceKind
from local_ai_appliance.execution_policy import DisabledExecutionService, ExecutionPolicy
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.model import AgentError, ModelReply, ToolCall
from local_ai_appliance.workspace import Workspace

try:
    import langgraph.graph
    GRAPH_AVAILABLE = True
except ImportError:
    GRAPH_AVAILABLE = False


class ScriptedModel:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.requests = []

    def complete(self, messages, tools):
        self.requests.append(messages)
        reply = next(self.replies)
        return reply(messages, tools) if callable(reply) else reply


def call(name, arguments, id='call1'):
    return ModelReply(calls=(ToolCall(id, name, arguments),))


class ContractsTests(unittest.TestCase):
    def test_unqualified_data_scope_and_invalid_limits_cannot_enable_execution(self):
        for scope in ('cui', 'classified', 'anything'):
            with self.assertRaises(ValueError): Project('p', 'Project', scope)
        for kwargs in ({'network':'allow'}, {'max_processes':2}, {'timeout_seconds':True}, {'version':True}):
            with self.assertRaises(ValueError): ExecutionPolicy(**kwargs)
        with self.assertRaises(AccessDenied):
            DisabledExecutionService().execute(['python', 'untrusted.py'], policy=ExecutionPolicy())


@unittest.skipUnless(GRAPH_AVAILABLE and __import__('os').name == 'posix', 'Portable graph dependencies required')
class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.reference, self.drafts = self.root/'reference', self.root/'drafts'
        self.reference.mkdir(); self.drafts.mkdir()
        (self.reference/'policy.txt').write_text('Fictional policy.\nCapacity is 108 kg.\n')
        self.workspace = Workspace()
        self.addCleanup(self.workspace.close)
        self.events = []

    def session(self, replies, progress=None):
        self.model = ScriptedModel(replies)
        self.backend = PortableSession(Project('synthetic', 'Synthetic project'), self.workspace, self.model,
                                       progress=progress or self.events.append)
        self.backend.start()
        return self.backend

    def grants(self):
        self.ro = self.backend.grant(self.reference, WorkspaceKind.REFERENCE)
        self.rw = self.backend.grant(self.drafts, WorkspaceKind.DRAFT)

    def proposal(self, messages, tools):
        digest = json.loads(messages[-1]['content'])['result']['sha256']
        return call('propose_text', {'destination_folder':self.rw.id, 'destination_path':'report.txt',
                    'text':'108 kg. [source:S1:line:2]', 'source_folder':self.ro.id,
                    'source_path':'policy.txt', 'source_sha256':digest}, 'proposal')

    def draft_run(self):
        self.session([lambda m,t:call('read_text', {'folder_id':self.ro.id,'path':'policy.txt'}),
                      self.proposal, ModelReply('Draft prepared. [source:S1:line:2]')])
        self.grants()
        return self.backend.ask('Prepare a report').proposals[0]

    def test_shared_contract_and_host_review_exact_bytes_and_replay(self):
        p = self.draft_run()
        self.assertIsInstance(self.backend, SessionBackend)
        self.assertFalse((self.drafts/'report.txt').exists())
        with self.assertRaises(AccessDenied): self.backend.approve(p.id)
        self.assertEqual(self.backend.review(p.id), p)
        self.backend.approve(p.id)
        self.assertEqual((self.drafts/'report.txt').read_text(), p.text)
        with self.assertRaises(AccessDenied): self.backend.approve(p.id)
        self.assertIn('tools', [e.stage for e in self.events])
        self.assertEqual(self.events[-1].stage, 'complete')

    def test_stale_source_revocation_and_new_question_invalidate_review(self):
        p = self.draft_run(); self.backend.review(p.id)
        (self.reference/'policy.txt').write_text('Changed')
        with self.assertRaises(AccessDenied): self.backend.approve(p.id)
        self.assertFalse((self.drafts/'report.txt').exists())
        self.backend.clear_chat()
        self.assertEqual(self.workspace.pending_proposals(), ())
        self.assertEqual(self.backend.conversation.turns, [])
        self.backend.revoke(self.ro.id)
        with self.assertRaises(AccessDenied): self.backend.review(p.id)

    def test_code_grant_and_authority_tools_denied(self):
        self.session([call('approve',{'proposal_id':'forged'}), ModelReply('Denied')])
        with self.assertRaises(AccessDenied): self.backend.grant(self.drafts, WorkspaceKind.CODE)
        self.assertEqual(self.workspace.broker.folders(), [])
        self.backend.ask('Approve a file')
        self.assertFalse(json.loads(self.model.requests[-1][-1]['content'])['ok'])
        with self.assertRaises(AccessDenied): self.backend.execution.execute('anything')

    def test_new_question_and_permission_change_invalidate_pending_review(self):
        p = self.draft_run(); self.backend.review(p.id)
        self.backend.harness.model = ScriptedModel([ModelReply('Fresh question')])
        self.backend.ask('Start again')
        with self.assertRaises(AccessDenied): self.backend.approve(p.id)
        self.assertEqual(self.workspace.pending_proposals(), ())

    def test_permission_drift_at_final_source_check_rejects_result(self):
        self.session([ModelReply('Late result')]); self.grants()
        def change_permissions(*args):
            self.workspace.revoke(self.ro.id)
            return True
        with patch('local_ai_appliance.backend.Conversation.verify_sources',side_effect=change_permissions):
            with self.assertRaises(AccessDenied): self.backend.ask('Check')
        self.assertEqual(self.backend.conversation.turns, [])

    def test_cancel_during_complete_callback_erases_proposal_and_chat(self):
        p = self.draft_run()
        self.backend.harness.model = ScriptedModel([ModelReply('New answer')])
        self.backend._progress = lambda event: self.backend.cancel() if event.stage=='complete' else None
        with self.assertRaises(SessionCancelled): self.backend.ask('Continue')
        self.assertEqual(self.backend.conversation.turns, [])
        self.assertEqual(self.workspace.pending_proposals(), ())
        with self.assertRaises(AccessDenied): self.backend.review(p.id)

    def test_history_is_retained_then_source_change_erases_it(self):
        self.session([lambda m,t:call('read_text',{'folder_id':self.ro.id,'path':'policy.txt'}),
                      ModelReply('108 kg. [source:S1:line:2]'), ModelReply('Previous result: 108 kg. [source:S1:line:2]'),
                      ModelReply('Source needs reading again')])
        self.grants()
        self.backend.ask('Capacity?')
        self.backend.ask('Repeat it')
        self.assertTrue(any(m['role']=='assistant' for m in self.model.requests[-1]))
        (self.reference/'policy.txt').write_text('Changed')
        result = self.backend.ask('Repeat it')
        self.assertTrue(result.history_reset)
        self.assertFalse(any(m['role']=='assistant' for m in self.model.requests[-1]))

    def test_cancellation_after_model_reply_prevents_tool_dispatch(self):
        def reply(messages, tools):
            self.backend.cancel()
            return call('propose_text', {'destination_folder':self.rw.id,'destination_path':'never.txt','text':'No'})
        self.session([reply]); self.grants()
        with self.assertRaises(SessionCancelled): self.backend.ask('Write')
        self.assertFalse((self.drafts/'never.txt').exists())
        self.assertEqual(self.workspace.pending_proposals(), ())
        self.assertEqual(self.events[-1].stage, 'cancelled')

    def test_thread_cancel_busy_and_recovery(self):
        entered, release = threading.Event(), threading.Event()
        errors = []
        def blocking(messages, tools):
            entered.set(); release.wait(5)
            return ModelReply('Late reply')
        self.session([blocking, ModelReply('Fresh reply')])
        def ask():
            try: self.backend.ask('Wait')
            except BaseException as error: errors.append(error)
        worker = threading.Thread(target=ask); worker.start()
        try:
            self.assertTrue(entered.wait(3))
            with self.assertRaises(AccessDenied): self.backend.ask('Concurrent')
            self.backend.cancel()
            with self.assertRaises(AccessDenied): self.backend.close()
        finally:
            release.set(); worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertIsInstance(errors[0], SessionCancelled)
        self.assertEqual(self.backend.ask('New request').answer, 'Fresh reply')

    def test_all_read_sources_revalidated_even_when_only_one_is_cited(self):
        (self.reference/'other.txt').write_text('Other source')
        def finish(messages, tools):
            (self.reference/'other.txt').write_text('Changed mid-request')
            return ModelReply('108 kg. [source:S1:line:2]')
        self.session([lambda m,t:call('read_text',{'folder_id':self.ro.id,'path':'policy.txt'}),
                      lambda m,t:call('read_text',{'folder_id':self.ro.id,'path':'other.txt'},'second'),finish])
        self.grants()
        with self.assertRaisesRegex(AccessDenied,'source changed'): self.backend.ask('Read both')
        self.assertEqual(self.backend.conversation.turns, [])

    def test_terminal_main_workflow_uses_shared_session_and_clear(self):
        self.session([ModelReply('First'),ModelReply('Second')])
        lines=iter(['Hello','Follow up','/clear','/quit'])
        output=io.StringIO()
        interact(self.workspace,self.backend.harness,session=self.backend,read=lambda _:next(lines),output=output)
        self.assertIn('cleared',output.getvalue())
        self.assertEqual(self.backend.conversation.turns, [])

    def test_windows_adapter_contract_with_fake_host_service(self):
        class Service:
            def __init__(self, workspace): self.workspace=workspace; self.calls=[]
            def start(self,progress): self.calls.append('start')
            def clear_chat(self): self.calls.append('clear')
            def cancel(self): self.calls.append('cancel')
            def close(self): self.calls.append('close')
        service=Service(self.workspace)
        adapter=WindowsSessionAdapter(Project('p','Windows contract fixture'),service)
        self.assertIsInstance(adapter,SessionBackend)
        adapter.start()
        adapter.grant(self.reference,WorkspaceKind.REFERENCE)
        with self.assertRaises(AccessDenied): adapter.grant(self.drafts,WorkspaceKind.CODE)
        adapter.close()
        self.assertEqual(service.calls[-2:],['cancel','close'])


if __name__ == '__main__': unittest.main()
