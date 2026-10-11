"""Interface-independent sessions using existing host-owned document authority.

Portable sessions are development orchestration, not OS containment. The Windows
adapter delegates launch/cancellation/cleanup to the existing contained service.
No adapter grants Code access or introduces a process-execution tool.
"""
from dataclasses import replace
import os
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
        self._text = None
        self._recovering = False
        self._recovery_stop = threading.Event()

    def set_display_sinks(self, progress, text):
        """Host presentation callbacks, absent from the worker tool registry."""
        with self._guard:
            self._require_idle()
            self._progress, self._text = progress, text

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
            if self._text is None:
                result = self.service.ask(prompt)
            else:
                result = self.service.ask(prompt, on_progress=self._progress, on_text=self._text)
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

    def switch_model(self, identifier):
        """Replace owned processes, then restore only identity-verified host grants."""
        manager = getattr(self.service, 'model_manager', None)
        if manager is None: raise AccessDenied('Managed models are unavailable')
        with self._guard:
            self._require_idle()
            previous = manager.selected()
            self._busy = True
            self._cancelled.clear()
            self._switch_starting = False
            self._model_grants_omitted = 0
        def checkpoint():
            if self._cancelled.is_set(): raise SessionCancelled('Model switch cancelled')
        service_type, root = type(self.service), self.service.root
        grants, instructions = [], ''
        def restart(selected, *, cancellable=False):
            self._model_grants_omitted = 0
            manager.vault.put('selected-model', {'id': selected})
            previous_service = self.service
            self.service = (previous_service.recreate() if hasattr(previous_service, 'recreate')
                            else service_type(root, model_manager=manager))
            if cancellable:
                self._switch_starting = True
                checkpoint()
            self.service.start(progress=lambda _: None)
            if cancellable: checkpoint()
            self._switch_starting = False
            self.service.instructions = instructions
            for grant in grants:
                try:
                    self.workspace.broker.grant(grant['path'], grant['access'],
                        expected_identity=(grant['volume'], grant['index']))
                except (OSError, AccessDenied):
                    self._model_grants_omitted += 1
        try:
            grants = self.workspace.broker.saved_grants()
            instructions = self.service.instructions
            if identifier is not None:
                profile = manager.authorize(identifier, data_scope=self.project.data_scope)
                manager.verify_model(profile, checkpoint)
                if os.name == 'nt':
                    from .model_management import scan_hardware
                    if not manager.hardware_fit(profile, scan_hardware()):
                        raise AccessDenied('Selected model needs more RAM or CUDA0 VRAM')
            checkpoint()
            self._clear_authority()
            self.service.close()
            try:
                restart(identifier, cancellable=True)
            except BaseException as error:
                self._switch_starting = False
                self.service.close()
                restart(previous)
                raise AccessDenied('Model switch failed; the previous model was restored: '+str(error)) from error
        finally:
            with self._guard:
                self._switch_starting = False
                self._busy = False

    def cancel_model_change(self):
        self._cancelled.set()
        if getattr(self, '_switch_starting', False): self.service.cancel()

    def cancel(self):
        self._cancelled.set()
        if self._recovering:
            self._recovery_stop.set()
        self.service.cancel()
        self._reviewed.clear()

    def recover(self, *, reserved_paths=()):
        """After hard cancellation, rebuild owned processes and recheck grants.

        The caller must first drain the cancelled ask. Old chat, reviews and
        code authority do not survive; a failed cleanup cannot create a new host.
        """
        with self._guard:
            self._require_idle()
            if not self._cancelled.is_set():
                return
            self._busy = True
            self._recovering = True
            self._recovery_stop.clear()
        try:
            old = self.service
            manager = getattr(old, 'model_manager', None)
            grants = self.workspace.broker.saved_grants()
            instructions = old.instructions
            self._clear_authority()
            old.clear_chat()
            old.close()  # Includes verified owned-process/IPC cleanup.
            replacement = (old.recreate() if hasattr(old, 'recreate')
                           else type(old)(old.root, model_manager=manager))
            self.service = replacement
            try:
                if self._recovery_stop.is_set():
                    raise SessionCancelled('Recovery cancelled')
                replacement.start(progress=lambda _: self._emit('starting'))
                replacement.instructions = instructions
                reserve = getattr(replacement.workspace.broker, 'reserve_tree', None)
                if reserve is not None:
                    for path in reserved_paths: reserve(path)
                self._recovery_grants_omitted = 0
                for grant in grants:
                    try:
                        replacement.workspace.broker.grant(grant['path'], grant['access'],
                            expected_identity=(grant['volume'], grant['index']))
                    except (OSError, AccessDenied):
                        self._recovery_grants_omitted += 1
                if self._recovery_stop.is_set():
                    raise SessionCancelled('Recovery cancelled')
                self._cancelled.clear()
            except BaseException:
                replacement.close()
                raise
        finally:
            with self._guard:
                self._recovering = False
                self._busy = False

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
