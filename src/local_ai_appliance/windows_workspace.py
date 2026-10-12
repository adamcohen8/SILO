"""Trusted document RPC and contained parsing shared by evaluations and UI."""
from dataclasses import asdict
import base64
import hashlib
from pathlib import Path
from .agent import DocumentAgent
from .documents import Document
from .folders import AccessDenied
from .model import json_bytes, strict_json
from .windows_folders import WindowsFolderBroker
from .workspace import DraftTools, Workspace
from .task_completion import TaskRequirements

class ContainedWorkspace(Workspace):
    def __init__(self, container, executable, report):
        super().__init__(WindowsFolderBroker(validation_mode=True, max_file_bytes=1024*1024))
        self.container, self.executable, self.report = container, executable, report

    def open_document(self, folder_id, relative_path):
        with self._lock:
            self.checkpoint()
            data = self.broker.read_file(folder_id, relative_path)
            kind = Path(relative_path).suffix.lower().lstrip('.')
            if kind not in {'pdf', 'docx', 'csv', 'xlsx', 'pptx'}:
                raise AccessDenied('Select a PDF, DOCX, CSV, XLSX or PPTX document')
            request = json_bytes({'format': kind, 'data': base64.b64encode(data).decode('ascii')})
            parser = self.executable.parent / 'Lib' / 'site-packages' / 'local_ai_appliance' / 'parser_worker.py'
            process = self.container.launch([str(self.executable), '-I', '-B', str(parser)], cwd=self.executable.parent)
            try:
                self.checkpoint()
                code, out, _ = process.communicate(request, timeout=10, limit=1024*1024)
                if code != 0:
                    raise AccessDenied('Contained document parser rejected the input')
                value = strict_json(out)
                expected = {'pdf':'page', 'docx':'paragraph', 'csv':'row', 'xlsx':'row', 'pptx':'slide'}[kind]
                units = value['units']
                if (set(value) != {'ok', 'unit_kind', 'units'} or value['ok'] is not True
                        or value['unit_kind'] != expected or not isinstance(units, list)
                        or not 1 <= len(units) <= (100 if kind == 'pdf' else 2000)
                        or not all(isinstance(unit, str) for unit in units)
                        or sum(len(unit.encode()) for unit in units) > 512*1024):
                    raise AccessDenied('Contained document parser returned invalid data')
                self.report['parser_tokens'].append(process.token_evidence)
                return Document(folder_id, relative_path, hashlib.sha256(data).hexdigest(), kind, expected, tuple(units))
            finally:
                process.close()


class BrokerSession:
    def __init__(self, workspace, *, sources=(), code=None, prompt=''):
        self.workspace, self.revision = workspace, workspace.broker.revision
        self.sources, self.created, self.calls = list(sources), set(), 0
        self.initial_source_count = len(sources)
        self.requirements = TaskRequirements.from_prompt(prompt)
        # Only fixed host tool validation/dispatch is used. No graph or third-
        # party AI imports execute in this trusted broker process.
        self.dispatcher = DocumentAgent.__new__(DocumentAgent)
        self.dispatcher.workspace, self.dispatcher.tools = workspace, DraftTools(workspace)
        if code is not None:
            from .code_agent import CodeAgent
            self.dispatcher=CodeAgent.__new__(CodeAgent)
            self.dispatcher.workspace,self.dispatcher.tools,self.dispatcher.code=workspace,DraftTools(workspace),code
        self.max_calls=None  # Host authority is checked on each call, without a lifetime quota.

    def inventory(self, *, max_bytes=8192):
        """Bounded name previews, following at most three single-folder wrappers."""
        previews = []
        for folder in self.workspace.broker.folders():
            path = ''
            for _ in range(4):
                if self.workspace.broker.revision != self.revision:
                    raise AccessDenied('Folder permissions changed')
                try:
                    listing = self.workspace.broker.list_directory(folder.id, path, limit=24)
                    preview = {'folder_id': folder.id, 'path': path, 'ok': True, **listing}
                except AccessDenied as error:
                    preview = {'folder_id': folder.id, 'path': path, 'ok': False, 'error': str(error)}
                if self.workspace.broker.revision != self.revision:
                    raise AccessDenied('Folder permissions changed')
                while len(json_bytes(previews+[preview])) > max_bytes:
                    if not preview.get('entries'):
                        return previews
                    preview['entries'].pop()
                    preview['truncated'] = True
                previews.append(preview)
                entries = preview.get('entries', [])
                if (not preview['ok'] or preview.get('truncated') or len(entries) != 1
                        or entries[0]['kind'] != 'directory'):
                    break
                path = '/'.join(filter(None, (path, entries[0]['name'])))
        return previews

    def handle(self, request):
        intent = False
        sink = getattr(self.workspace, "task_sink", None)
        try:
            if self.workspace.broker.revision != self.revision:
                raise AccessDenied('Folder permissions changed')
            if not isinstance(request, dict):
                raise AccessDenied('Invalid document IPC request')
            operation = request.get('op')
            if operation == 'continuation' and set(request) == {'op', 'data'}:
                data = request['data']
                if (not isinstance(data, dict) or set(data) != {'text', 'status'}
                        or not isinstance(data['text'], str) or not data['text'].strip()
                        or len(json_bytes(data['text'])) > 48*1024
                        or data['status'] != 'partial; not a completed answer'):
                    raise AccessDenied('Invalid partial answer checkpoint')
                if sink: sink('continuation', data)
                value = None
            elif operation == 'pending' and set(request) == {'op'}:
                value = [p.id for p in self.workspace.pending_proposals() if p.id in self.created]
            elif operation == 'discard' and set(request) == {'op', 'id'}:
                if not isinstance(request['id'], str) or request['id'] not in self.created:
                    raise AccessDenied('Unknown session proposal')
                self.workspace.discard(request['id'])
                value = None
            elif operation == 'tool' and set(request) == {'op', 'name', 'arguments'}:
                self.calls += 1
                if (self.max_calls is not None and self.calls > self.max_calls) or not isinstance(request['arguments'], dict):
                    raise AccessDenied('Document IPC budget or arguments rejected')
                sink = getattr(self.workspace, 'task_sink', None)
                if sink:
                    sink('tool_intent', {'name': request['name'], 'arguments': request['arguments']})
                    intent = True
                result, source, proposal = self.dispatcher._dispatch(request['name'], request['arguments'], self.sources)
                if sink: sink('tool_result', {'name': request['name'], 'result': result})
                intent = False
                if source:
                    self.sources.append(source)
                if proposal:
                    self.created.add(proposal)
                value = {'result': result, 'source': asdict(source) if source else None, 'proposal_id': proposal}
            else:
                raise AccessDenied('Document IPC operation is not registered')
            return {'ok': True, 'value': value}
        except AccessDenied as error:
            if intent: sink('tool_result', {'name': request['name'], 'denied': True})
            return {'ok': False, 'error': str(error)}

    def validate(self, result):
        if self.workspace.broker.revision != self.revision:
            raise AccessDenied('Folder permissions changed during the request')
        answer = result['answer']
        if not isinstance(answer, str) or len(answer.encode()) > 64*1024:
            raise AccessDenied('Invalid worker answer')
        citations = DocumentAgent._citations(answer, self.sources)
        if result['references'] != [s.reference for s in citations]:
            raise AccessDenied('Worker citation metadata did not match host sources')
        proposals = result['proposal_ids']
        if not isinstance(proposals, list) or any(i not in self.created for i in proposals):
            raise AccessDenied('Worker returned a proposal outside its session')
        pending = {p.id: p for p in self.workspace.pending_proposals() if p.id in self.created}
        if any(i not in pending for i in proposals):
            raise AccessDenied('Worker returned a proposal outside its session')
        self.requirements.validate(citations, tuple(pending[i] for i in proposals))
        if len(self.sources) > self.initial_source_count and not citations and not proposals:
            raise AccessDenied('Worker document answer omitted its citation')
        return citations

    def discard_all(self):
        for identifier in self.created:
            self.workspace.discard(identifier)

