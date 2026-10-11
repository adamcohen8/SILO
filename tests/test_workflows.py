import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from local_ai_appliance.backend import PortableSession
from local_ai_appliance.contracts import Project,WorkspaceKind
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.model import ModelReply
from local_ai_appliance.project_store import LocalVault,ProjectStore,ProjectSession
from local_ai_appliance.workspace import Workspace
from local_ai_appliance.workflows import ScheduleEngine,Workflows

class Model:
    def __init__(self):self.calls=0
    def complete(self,messages,tools):self.calls+=1;return ModelReply('Fixture result')

@unittest.skipUnless(os.name=='posix','Portable schedule fixture')
class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();state=self.root/'state';state.mkdir(mode=0o700)
        self.folder=self.root/'folder';self.folder.mkdir()
        self.vault=LocalVault(state);self.addCleanup(self.vault.close)
        self.model=Model();self.backend=PortableSession(Project('unsaved','Unsaved'),Workspace(),self.model)
        self.addCleanup(self.backend.close)
        self.now=[1000];self.session=ProjectSession(self.backend,ProjectStore(self.vault,clock=lambda:self.now[0]))
        self.folder_id=self.session.grant(self.folder,WorkspaceKind.REFERENCE).id
        self.project=self.session.create_project('Tasks')
        self.workflows=Workflows(self.session);self.workflows.save('summarize','Summarize fictional inputs')
        self.scheduler=ScheduleEngine(self.session,clock=lambda:self.now[0])

    def test_workflow_retains_scope_and_prompt_but_cannot_expand_grants(self):
        self.assertEqual(self.workflows.prompt('summarize'),'Summarize fictional inputs')
        self.session.revoke(self.folder_id)
        with self.assertRaisesRegex(AccessDenied,'scope changed'):self.workflows.prompt('summarize')
        self.workflows.save('summarize','Reviewed without references')
        self.assertEqual(self.workflows.prompt('summarize'),'Reviewed without references')

    def test_due_task_runs_once_coalesces_missed_slots_and_retains_evidence(self):
        name=self.scheduler.create('summarize',interval_seconds=60)
        self.assertEqual(self.scheduler.tick(),[])
        self.now[0]=1240;events=self.scheduler.tick()
        self.assertEqual(self.model.calls,1);self.assertEqual(events[0]['skipped_slots'],3)
        self.assertEqual(events[0]['state'],'complete');self.assertEqual(events[0]['due'],1240)
        self.assertEqual(self.scheduler.tick(),[]);self.assertEqual(self.model.calls,1)
        self.assertEqual(len(self.session.conversation.turns),1)
        self.assertEqual(self.scheduler.listing()[name]['last']['pending_reviews'],0)

    def test_second_runner_cannot_duplicate_or_reconcile_active_attempt(self):
        name=self.scheduler.create('summarize',interval_seconds=60);self.now[0]=1060
        second=ScheduleEngine(self.session,clock=lambda:self.now[0])
        original=self.session.ask
        def ask(prompt):
            self.assertEqual(second.tick(),[])
            with self.assertRaises(AccessDenied):second.reconcile(name)
            self.assertEqual(second.listing()[name]['state'],'running')
            return original(prompt)
        with patch.object(self.session,'ask',side_effect=ask):events=self.scheduler.tick()
        self.assertEqual(events[0]['state'],'complete');self.assertEqual(self.model.calls,1)
        self.assertNotIn('.schedule-runner-lock',self.vault.store.names())

    def test_crash_lock_blocks_replay_until_explicit_operator_recovery(self):
        self.scheduler.create('summarize',interval_seconds=60);self.now[0]=1060
        self.vault.store.write('.schedule-runner-lock',lambda write:write(b''))
        self.assertEqual(self.scheduler.tick(),[]);self.assertEqual(self.model.calls,0)
        self.vault.store.remove('.schedule-runner-lock')
        self.scheduler.tick();self.assertEqual(self.model.calls,1)

    def test_closed_wrong_project_and_changed_scope_do_not_run(self):
        name=self.scheduler.create('summarize',interval_seconds=60);self.now[0]=1060
        self.session.close_project();self.assertEqual(self.scheduler.tick(),[])
        self.session.create_project('Other');self.assertEqual(self.scheduler.tick(),[])
        self.session.open_project(self.project.id);self.session.set_instructions('Changed')
        events=self.scheduler.tick();self.assertEqual(events[0]['state'],'scope_changed');self.assertEqual(self.model.calls,0)
        self.assertFalse(self.scheduler.listing()[name]['enabled'])

    def test_crash_running_becomes_unknown_and_requires_reconciliation_no_replay(self):
        name=self.scheduler.create('summarize',interval_seconds=60)
        items=self.scheduler.listing();items[name]['state']='running';items[name]['last']={'state':'running'}
        self.scheduler._save(items);self.now[0]=1060
        self.assertEqual(self.scheduler.tick()[0]['state'],'unknown');self.assertEqual(self.model.calls,0)
        self.scheduler.reconcile(name);self.assertEqual(self.scheduler.tick(),[])
        self.now[0]=1120;self.scheduler.tick();self.assertEqual(self.model.calls,1)

    def test_failure_advances_slot_without_retrying_same_action(self):
        name=self.scheduler.create('summarize',interval_seconds=60);self.now[0]=1060
        with patch.object(self.session,'ask',side_effect=RuntimeError('fixture failure')):
            events=self.scheduler.tick();self.assertEqual(events[0]['state'],'failed')
        self.assertEqual(self.scheduler.tick(),[])
        self.assertEqual(self.scheduler.listing()[name]['next_due'],1120)

    def test_changed_workflow_disables_schedule_before_model_call(self):
        name=self.scheduler.create('summarize',interval_seconds=60)
        self.workflows.save('summarize','A changed task');self.now[0]=1060
        self.assertEqual(self.scheduler.tick()[0]['state'],'workflow_changed')
        self.assertFalse(self.scheduler.listing()[name]['enabled']);self.assertEqual(self.model.calls,0)

    def test_cancel_pending_never_runs_and_invalid_intervals_denied(self):
        name=self.scheduler.create('summarize',interval_seconds=60);self.scheduler.cancel(name)
        self.now[0]=1060;self.assertEqual(self.scheduler.tick(),[]);self.assertEqual(self.model.calls,0)
        for seconds in (True,0,59,365*86400+1):
            with self.assertRaises(AccessDenied):self.scheduler.create('summarize',interval_seconds=seconds)

    def test_scheduled_result_stays_unsaved_pending_review(self):
        folder=self.root/'dest';folder.mkdir();grant=self.session.grant(folder,WorkspaceKind.DRAFT)
        self.workflows.save('draft','Prepare a report');name=self.scheduler.create('draft',interval_seconds=60)
        original=self.session.ask
        from dataclasses import replace
        def ask(prompt):
            result=original(prompt);proposal=self.session.workspace.propose(grant.id,'pending.txt','Pending')
            return replace(result,proposals=(proposal,))
        self.now[0]=1060
        with patch.object(self.session,'ask',side_effect=ask):events=self.scheduler.tick()
        self.assertFalse((folder/'pending.txt').exists());self.assertEqual(events[0]['pending_reviews'],1)
        self.assertEqual(len(self.session.workspace.pending_proposals()),1)
