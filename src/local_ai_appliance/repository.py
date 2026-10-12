"""Host-broker repository snapshots and exact-preimage patch sets.

Imports require an explicit Reference grant. No .git metadata, hooks, secrets,
remote access, original overwrite, or process launch is exposed to the model.
"""
import difflib
import hashlib
from .code_workspace import code_path, MAX_FILES, MAX_FILE
from .folders import AccessDenied
from .model import json_bytes

EXCLUDED = {'.git','.silo','.svn','.hg','.venv','venv','node_modules','__pycache__','target','dist','build'}


class RepositorySnapshot:
    def __init__(self, folder_id, baseline):
        self.folder_id, self.baseline = folder_id, baseline
        self.identity = hashlib.sha256(json_bytes({p:hashlib.sha256(b).hexdigest()
                                for p,b in sorted(baseline.items())})).hexdigest()

    @classmethod
    def import_from(cls, code, folder_id):
        with code._lock:
            code.check()
            if code._running: raise AccessDenied('Cannot import while code is executing')
            return cls._import(code,folder_id)

    @classmethod
    def _import(cls, code, folder_id):
        code.check()
        if code.files: raise AccessDenied('Import into an empty disposable workspace')
        folder=next((f for f in code.workspace.broker.folders() if f.id==folder_id),None)
        if folder is None or folder.access!='read-only': raise AccessDenied('Repository import needs an explicit Reference grant')
        baseline={}; excluded=[]
        def visit(prefix=''):
            listing=code.workspace.broker.list_directory(folder_id,prefix,limit=1000)
            if listing['truncated']: raise AccessDenied('Repository listing is partial; select a smaller explicit subtree')
            for item in listing['entries']:
                path='/'.join(filter(None,(prefix,item['name'])))
                if item['name'].casefold() in EXCLUDED or item['name'].casefold().startswith('.env'):
                    excluded.append(path);continue
                if item['kind']=='directory':
                    if len(path.split('/'))>=8: excluded.append(path);continue
                    visit(path);continue
                try: code_path(path)
                except AccessDenied: excluded.append(path);continue
                if len(baseline)>=MAX_FILES: raise AccessDenied('Repository exceeds the configured workspace inventory')
                data=code.workspace.broker.read_file(folder_id,path)
                if len(data)>MAX_FILE: raise AccessDenied('Source file exceeds the individual storage frame')
                try: data.decode('utf-8')
                except UnicodeError: excluded.append(path);continue
                baseline[path]=data
                code._inventory(baseline)
        visit()
        code._inventory(baseline)
        code.check()  # Refuse a grant/revision change during the import.
        snapshot=cls(folder_id,baseline)
        code.files=dict(baseline);code.repository=snapshot
        return {'files':len(baseline),'baseline_sha256':snapshot.identity,'excluded':excluded,
                'published':False,'note':'Snapshot of supported text files. Originals and repository metadata were not modified.'}

    def changes(self, code):
        return code.diff(self.baseline)

    def conflicts(self, code):
        code.check()
        conflicts=[]
        for change in self.changes(code):
            expected=self.baseline.get(change['path'])
            if expected is None:
                if not self._missing(code,change['path']): conflicts.append(change['path'])
                continue
            try: current=code.workspace.broker.read_file(self.folder_id,change['path'])
            except (OSError,AccessDenied):
                conflicts.append(change['path']);continue
            if current!=expected: conflicts.append(change['path'])
        return conflicts

    def _missing(self, code, path):
        # A denied read is never proof of absence. Check complete held-broker
        # directory inventories, including case aliases and missing parents.
        prefix=''
        components=path.split('/')
        for index,component in enumerate(components):
            code.check()
            try: listing=code.workspace.broker.list_directory(self.folder_id,prefix,limit=1000)
            except (OSError,AccessDenied): return False
            if listing['truncated']: return False
            match=next((entry for entry in listing['entries'] if entry['name'].casefold()==component.casefold()),None)
            if match is None: return True
            if index==len(components)-1 or match['kind']!='directory': return False
            prefix='/'.join(filter(None,(prefix,match['name'])))
        return False

    def patch(self, code):
        conflicts=self.conflicts(code)
        if conflicts: raise AccessDenied('Original preimages changed: '+', '.join(conflicts[:10]))
        changes=self.changes(code)
        return {'format':1,'baseline_sha256':self.identity,'changes':changes,
                'sha256':hashlib.sha256(json_bytes(changes)).hexdigest(),
                'status':'unsaved; review before external application'}

    def propose_patch(self, code, destination_folder, destination_path):
        if not destination_path.endswith('.patch'):
            raise AccessDenied('Export a new .patch file for host Git review')
        patch = self.patch(code)
        changes = patch['changes']
        if any(change['diff'] == '[binary bytes changed]' for change in changes):
            raise AccessDenied('This text patch cannot export binary changes')
        text = ''.join(change['diff'] for change in changes)
        if not text: raise AccessDenied('No repository changes to export')
        if len(text.encode()) > 32*1024:
            raise AccessDenied('Patch exceeds the reviewed text frame; export a smaller explicit change set')
        from dataclasses import replace
        from .workspace import TextSource
        dependencies = tuple(TextSource(self.folder_id,change['path'],
                self.baseline[change['path']].decode('utf-8'),change['before_sha256'])
                for change in changes if change['before_sha256'] is not None)
        with code.workspace._lock:
            proposal=code.workspace.propose(destination_folder,destination_path,text)
            proposal=replace(proposal,dependencies=dependencies)
            code.workspace._pending[proposal.id]=proposal
            return proposal
