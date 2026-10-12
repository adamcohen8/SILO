"""Protected code snapshots contain files and preimages, never processes or approvals."""
import base64
import hashlib
from dataclasses import asdict, replace
from .agent import Source
from .conversation import Conversation
from .folders import AccessDenied
from .model import json_bytes


class CodeStore:
    def __init__(self, vault): self.vault = vault

    def save(self, project_id, code):
        with code._lock:
            code.check()
            if code._running: raise AccessDenied('Cannot snapshot a running execution')
            folders = code.workspace.broker.folders()
            identities = dict(zip((f.id for f in folders), code.workspace.broker.saved_grants(), strict=True))
            repository = getattr(code, 'repository', None)
            snapshot = {'format':2,'project_id':project_id,'files':[], 'inputs':[], 'baseline':[],
                'repository_grant':identities[repository.folder_id] if repository else None,
                'sources':{name:{'source':asdict(source),'grant':identities[source.folder_id]}
                           for name,source in code.sources.items()}, 'configuration':code.configuration,
                'policy':asdict(code.policy)}
            inventories=(('files',code.files),('inputs',code.inputs),
                         ('baseline',repository.baseline if repository else {}))
            for kind,data in inventories:
                for path,content in sorted(data.items()):
                    digest=hashlib.sha256(content).hexdigest()
                    snapshot[kind].append({'path':path,'key':'codeblob-'+project_id+'-'+digest[:32],
                                           'sha256':digest,'size':len(content)})
            from .project_store import MAX_RECORD
            if len(json_bytes(snapshot))>MAX_RECORD:
                raise AccessDenied('Code snapshot metadata exceeds its storage frame; reduce the explicit workspace inventory')
            with self.vault.transaction():
                for kind,data in inventories:
                    for pin in snapshot[kind]:
                        key=pin['key']
                        existing=self.vault.get(key)
                        blob={'sha256':pin['sha256'],'data':base64.b64encode(data[pin['path']]).decode('ascii')}
                        if existing is not None and existing!=blob:
                            raise AccessDenied('Private code blob identity collision')
                        if existing is None:self.vault.put(key,blob)
                self.vault.put('codework-'+project_id,snapshot)
                needed = {p['key'] for kind in ('files','inputs','baseline') for p in snapshot[kind]}
                for key in self.vault.names('codeblob-'+project_id+'-'):
                    if key not in needed: self.vault.delete(key)
        return snapshot

    def restore(self, project_id, code, *, files_only=False):
        with code._lock:
            code.check()
            if type(files_only) is not bool or files_only and code.runner.available:
                raise AccessDenied('Files-only recovery requires execution disabled')
            if code._running: raise AccessDenied('Cannot restore during execution')
            try: return self._restore(project_id, code, files_only=files_only)
            except AccessDenied:
                raise
            except (KeyError, TypeError, ValueError, UnicodeError, AttributeError) as error:
                raise AccessDenied('Malformed retained code snapshot; nothing restored') from error

    def _restore(self, project_id, code, *, files_only=False):
        from .code_workspace import code_path, MAX_FILES, MAX_FILE
        from .windows_folders import parts
        from .repository import RepositorySnapshot
        value = self.vault.get('codework-'+project_id)
        if (not isinstance(value,dict) or set(value)!={'format','project_id','files','inputs','baseline',
                'repository_grant','sources','configuration','policy'} or type(value['format']) is not int
                or value['format']!=2 or value['project_id']!=project_id or value['policy']!=asdict(code.policy)):
            raise AccessDenied('No compatible retained code workspace')
        if code.files or code.inputs or code.runs: raise AccessDenied('Restore into a new empty Code workspace')
        folders = code.workspace.broker.folders()
        current = list(zip(folders,code.workspace.broker.saved_grants(),strict=True))
        def match_grant(grant):
            match = next((folder for folder,saved in current if saved == grant),None)
            if match is None or match.access!='read-only': raise AccessDenied('Retained grant changed or was revoked')
            return match
        sources = {}
        if not isinstance(value['sources'],dict) or len(value['sources'])>16: raise AccessDenied('Invalid retained inputs')
        for name, saved in ({} if files_only else value['sources']).items():
            if len(parts(name))!=1 or set(saved)!={'source','grant'}: raise AccessDenied('Invalid retained input name')
            match = match_grant(saved['grant'])
            sources[name] = replace(Source(**saved['source']),folder_id=match.id)
        if not Conversation.verify_sources(code.workspace,tuple(sources.values())):
            raise AccessDenied('Retained source bytes changed')
        repository_folder = match_grant(value['repository_grant']) if value['repository_grant'] is not None and not files_only else None
        restored = {}
        for kind in ('files','inputs','baseline'):
            if files_only and kind != 'files':
                restored[kind] = {}
                continue
            if not isinstance(value[kind],list) or len(value[kind]) > (16 if kind=='inputs' else MAX_FILES):
                raise AccessDenied('Retained code inventory exceeds resource limits')
            data, aliases = {}, set()
            for pin in value[kind]:
                if set(pin)!={'path','key','sha256','size'} or type(pin['size']) is not int:
                    raise AccessDenied('Invalid retained file pin')
                path = pin['path']
                code_path(path) if kind!='inputs' else parts(path)
                if kind=='inputs' and (len(parts(path))!=1 or path not in sources): raise AccessDenied('Invalid retained input')
                if path.casefold() in aliases: raise AccessDenied('Aliased retained file')
                aliases.add(path.casefold())
                if pin['key'] != 'codeblob-'+project_id+'-'+pin['sha256'][:32]: raise AccessDenied('Invalid code blob identity')
                blob=self.vault.get(pin['key'])
                if not isinstance(blob,dict) or set(blob)!={'data','sha256'}: raise AccessDenied('Missing code blob')
                content=base64.b64decode(blob['data'],validate=True)
                if (len(content)!=pin['size'] or len(content)>MAX_FILE or hashlib.sha256(content).hexdigest()!=pin['sha256']
                        or blob['sha256']!=pin['sha256']): raise AccessDenied('Retained code bytes changed')
                data[path]=content
            restored[kind]=data
        if set(restored['inputs']) != set(sources): raise AccessDenied('Incomplete retained inputs')
        if restored['baseline'] and repository_folder is None: raise AccessDenied('Retained baseline lacks its grant')
        # Preserve the preimages, but never silently claim they are still current.
        repository = RepositorySnapshot(repository_folder.id, restored['baseline']) if repository_folder else None
        old_inputs=code.inputs
        try:
            code.inputs=restored['inputs']; code._inventory(restored['files']); code._inventory(restored['baseline'])
            if repository:
                for path, expected in repository.baseline.items():
                    if code.workspace.broker.read_file(repository.folder_id,path)!=expected:
                        raise AccessDenied('Retained repository source bytes changed')
        except BaseException:
            code.inputs=old_inputs; raise
        code.files,code.sources=restored['files'],sources
        if repository: code.repository=repository
        code.exports.clear();code.reviewed.clear();code.runs.clear()
        return code.page()

    def delete(self, project_id):
        self.vault.delete('codework-'+project_id)
        for key in self.vault.names('codeblob-'+project_id+'-'): self.vault.delete(key)
