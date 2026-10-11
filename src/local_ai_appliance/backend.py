"""Interface-independent sessions using existing host-owned document authority.

Portable sessions are development orchestration, not OS containment. The Windows
adapter delegates launch/cancellation/cleanup to the existing contained service.
No adapter grants Code access or introduces a process-execution tool.
"""
from dataclasses import replace
import threading

from .agent import DocumentAgent
from .contracts import Progress, Project, WorkspaceKind
from .conversation import Conversation
from .folders import AccessDenied
from .model import AgentError
from .execution_policy import DisabledExecutionService


class SessionCancelled(AgentError):
    pass


class _Authority:
    def _require_idle(self):
        if self.closed or self._busy:
            raise AccessDenied('Session is closed or busy')

    def _emit(self, stage, model_calls=0, tool_calls=0):
        self._progress(Progress(stage, model_calls, tool_calls))

    def _clear_authority(self):
        self._reviewed.clear()
        for proposal in self.workspace.pending_proposals():
            self.workspace.discard(proposal.id)

    def grant(self, path, kind):
        with self._guard:
            self._require_idle()
            if not isinstance(kind, WorkspaceKind):
                raise AccessDenied('Select an explicit Reference, Draft, or Code permission')
            if kind is WorkspaceKind.CODE:
                raise AccessDenied('Code workspace grants are unavailable in Phase 1')
            folder = self.workspace.grant(path, 'read-only' if kind is WorkspaceKind.REFERENCE else 'editable')
            self.clear_chat()
            return folder

    def revoke(self, folder_id):
        with self._guard:
            self._require_idle()
            self.workspace.revoke(folder_id)
            self.clear_chat()

    def review(self, proposal_id):
        with self._guard:
            self._require_idle()
            proposal = next((p for p in self.workspace.pending_proposals() if p.id == proposal_id), None)
            if proposal is None or proposal.permission_revision != self.workspace.broker.revision:
                raise AccessDenied('Proposal is unavailable or permissions changed')
            self.workspace.validate_proposal(proposal)
            self.workspace.broker.validate_create(proposal.destination_folder, proposal.destination_path)
            if proposal.source:
                source = self.workspace.open_source(proposal.source.folder_id, proposal.source.path)
                if source.sha256 != proposal.source.sha256:
                    raise AccessDenied('Source changed; review a new proposal')
            # Keep the exact immutable object; review cannot transfer between sessions.
            self._reviewed[proposal_id] = proposal
            return proposal

    def approve(self, proposal_id):
        with self._guard:
            self._require_idle()
            proposal = self._reviewed.pop(proposal_id, None)
            current = next((p for p in self.workspace.pending_proposals() if p.id == proposal_id), None)
            if proposal is None or proposal != current:
                raise AccessDenied('Review the exact current proposal before approving it')
            return self.workspace.approve(proposal_id)

    def discard(self, proposal_id):
        with self._guard:
            self._require_idle()
            self._reviewed.pop(proposal_id, None)
            self.workspace.discard(proposal_id)


class PortableSession(_Authority):
    def __init__(self, project, workspace, model, *, progress=lambda event: None, instructions=''):
        if not isinstance(project, Project):
            raise ValueError('A validated project descriptor is required')
        self.project, self.workspace = project, workspace
        self._progress = progress
        self._guard = threading.RLock()
        self._cancelled = threading.Event()
        self._busy, self.closed = False, False
        self._reviewed = {}
        self.conversation = Conversation()
        self.execution = DisabledExecutionService()
        self.workspace.checkpoint = self._checkpoint
        self.harness = DocumentAgent(workspace, model, instructions=instructions,
                                     checkpoint=self._checkpoint, progress=self._agent_progress)

    def _checkpoint(self):
        if self._cancelled.is_set():
            raise SessionCancelled('Session cancelled')

    def _agent_progress(self, stage, model_calls, tool_calls):
        self._emit(stage, model_calls, tool_calls)
        self._checkpoint()

    def start(self):
        with self._guard:
            self._require_idle()
            self._emit('starting')

    def ask(self, prompt):
        with self._guard:
            self._require_idle()
            self._busy = True
            self._cancelled.clear()
            self._clear_authority()
            revision = self.workspace.broker.revision
        try:
            history, sources, reset = self.conversation.prepare(self.workspace)
            result = self.harness.run(prompt, history=history, sources=sources)
            self._checkpoint()
            # Recheck every source consumed in the request, including uncited reads.
            retained = self.harness.read_sources
            if not Conversation.verify_sources(self.workspace, (*sources, *retained)):
                self.conversation.clear()
                raise AccessDenied('A source changed during the request; chat cleared')
            with self._guard:
                self._checkpoint()
                if revision != self.workspace.broker.revision:
                    raise AccessDenied('Permissions changed during the request; chat cleared')
                self.conversation.drop(result.history_dropped)
                answer = result.answer
                if result.proposals:
                    answer += '\n\n'+'\n\n'.join('Unsaved draft: '+p.text for p in result.proposals)
                trimmed = self.conversation.append(prompt, answer, retained, self.workspace.broker.revision)
                self._emit('complete', result.model_calls, result.tool_calls)
                self._checkpoint()
                return replace(result, conversation=self.conversation.display(), history_reset=reset,
                               history_trimmed=trimmed or result.history_dropped > 0)
        except BaseException:
            with self._guard:
                self._clear_authority()
                self.conversation.clear()
            self._emit('cancelled' if self._cancelled.is_set() else 'failed')
            raise
        finally:
            with self._guard:
                self._busy = False

    def clear_chat(self):
        with self._guard:
            self._require_idle()
            self._clear_authority()
            self.conversation.clear()

    def cancel(self):
        # Cooperative on POSIX: no interrupt of a blocked model/HTTP call.
        self._cancelled.set()
        with self._guard:
            self._clear_authority()
            self.conversation.clear()

    def close(self):
        self.cancel()
        with self._guard:
            if self._busy:
                raise AccessDenied('Wait for the cancelled request before closing its broker')
            if not self.closed:
                self.workspace.close()
                self.closed = True
                self._emit('closed')


class WindowsSessionAdapter(_Authority):
    """Host adapter; Windows remains the owner of hard process cancellation."""
    def __init__(self, project, service, *, progress=lambda event: None):
        if not isinstance(project, Project):
            raise ValueError('A validated project descriptor is required')
        self.project, self.service, self._progress = project, service, progress
        self._guard = threading.RLock()
        self._busy, self.closed = False, False
        self._reviewed = {}
        self._cancelled = threading.Event()
        self.execution = DisabledExecutionService()

    @property
    def workspace(self):
        if self.service.workspace is None:
            raise AccessDenied('Start the Windows session before granting folders')
        return self.service.workspace

    def start(self):
        with self._guard:
            self._require_idle()
            self._busy = True
        try:
            self._emit('starting')
            self.service.start(progress=lambda _: None)
        finally:
            with self._guard:
                self._busy = False

    def ask(self, prompt):
        with self._guard:
            self._require_idle()
            self._busy = True
            self._cancelled.clear()
            self._clear_authority()
        try:
            self._emit('model')
            result = self.service.ask(prompt)
            if self._cancelled.is_set():
                raise SessionCancelled('Session cancelled')
            self._emit('complete', result.model_calls, result.tool_calls)
            if self._cancelled.is_set():
                raise SessionCancelled('Session cancelled')
            return result
        except BaseException:
            self.service.clear_chat()
            self._reviewed.clear()
            self._emit('cancelled' if self._cancelled.is_set() else 'failed')
            raise
        finally:
            with self._guard:
                self._busy = False

    def clear_chat(self):
        with self._guard:
            self._require_idle()
            self._clear_authority()
            self.service.clear_chat()

    def cancel(self):
        self._cancelled.set()
        self.service.cancel()
        self._reviewed.clear()

    def create_code(self,policy,**qualification):
        with self._guard:
            self._require_idle()
            if self.project.data_scope != 'synthetic':
                raise AccessDenied('Code evaluation requires a synthetic project')
            return self.service.create_code(policy,**qualification)

    def grant(self,path,kind):
        with self._guard:
            result=super().grant(path,kind)
            if getattr(self.service,'code',None) is not None: self.service.close_code()
            return result

    def revoke(self,folder_id):
        with self._guard:
            super().revoke(folder_id)
            if getattr(self.service,'code',None) is not None: self.service.close_code()

    def close_code(self):
        with self._guard:
            self._require_idle(); self.service.close_code()

    def review(self,identifier):
        with self._guard:
            self._require_idle()
            code=getattr(self.service,'code',None)
            if code is not None and identifier in code.exports: return code.review(identifier)
            return super().review(identifier)

    def approve(self,identifier):
        with self._guard:
            self._require_idle()
            code=getattr(self.service,'code',None)
            if code is not None and identifier in code.exports: return code.approve(identifier)
            return super().approve(identifier)

    def discard(self,identifier):
        with self._guard:
            self._require_idle()
            code=getattr(self.service,'code',None)
            if code is not None and identifier in code.exports: return code.discard(identifier)
            return super().discard(identifier)

    def close(self):
        self.cancel()
        with self._guard:
            if self._busy:
                raise AccessDenied('Wait for the cancelled Windows operation before closing its broker')
            if not self.closed:
                self.service.close()
                self.closed = True
                self._emit('closed')
