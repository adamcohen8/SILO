"""Host-only reviewed repository transactions with encrypted intent/recovery receipts.

Publication is atomic per file, not across files. A stopped transaction is unknown
until explicit inspection/reconciliation; recovery never restores approval.
"""
import base64
import hashlib
import secrets
import os
from .code_workspace import code_path,digest
from .folders import AccessDenied
from .model import json_bytes


def observed(broker,folder,path):
    prefix=''; components=path.split('/')
    for i,component in enumerate(components):
        listing=broker.list_directory(folder,prefix,limit=1000)
        if listing['truncated']: raise AccessDenied('Cannot establish absence from a partial listing')
        found=next((e for e in listing['entries'] if e['name'].casefold()==component.casefold()),None)
        if found is None: return None
        if found['name']!=component: raise AccessDenied('Case alias in repository target')
        if i<len(components)-1:
            if found['kind']!='directory': raise AccessDenied('Repository parent is not a directory')
            prefix='/'.join(filter(None,(prefix,component)))
        elif found['kind']!='file': raise AccessDenied('Repository target is not a regular file')
    return broker.read_file(folder,path)


class RepositoryApply:
    def __init__(self,code,vault,project_id,*,security=None,development=False):
        self.code,self.vault,self.project_id=code,vault,project_id
        self.reviewed=set()
        self.security,self.development=security,development

    def _authorized(self):
        if self.development is True and os.name=='posix': return
        from .host_capabilities import require_capability
        require_capability(self.security,'repository-apply',{'boundary':'held-handle-repository-1'},
            {'exclusive_preimages','case_aliases','reparse_links','concurrent_create','per_file_publication',
             'interrupted_set','recovery','grant_revocation','cleanup'})

    def _load(self,identifier):
        if not isinstance(identifier,str) or len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):
            raise AccessDenied('Invalid repository transaction')
        value=self.vault.get('repoapply-'+self.project_id+'-'+identifier)
        if value is None or value['project_id']!=self.project_id: raise AccessDenied('Unknown project transaction')
        return value

    def _save(self,value): self.vault.put('repoapply-'+self.project_id+'-'+value['id'],value)

    def listing(self,offset=0):
        if type(offset) is not int or offset<0:raise AccessDenied('Invalid transaction page')
        names=self.vault.names('repoapply-'+self.project_id+'-')
        values=[self.vault.get(n) for n in names[offset:offset+100]]
        return {'transactions':[{'id':v['id'],'state':v['state'],'folder_id':v['folder_id']} for v in values],
                'next_offset':offset+100 if offset+100<len(names) else None}

    def prepare(self,folder_id):
        with self.code._lock:
            self.code.check()
            if self.code._running: raise AccessDenied('Repository is executing')
            repository=getattr(self.code,'repository',None)
            if repository is None: raise AccessDenied('Import a repository first')
            broker=self.code.workspace.broker
            grant=next((f for f in broker.folders() if f.id==folder_id),None)
            if grant is None or grant.access!='editable': raise AccessDenied('Select an explicit writable working copy')
            patch=repository.patch(self.code); changes=[]
            for c in patch['changes']:
                if c['diff']=='[binary bytes changed]':raise AccessDenied('Use reviewed artifact export for binary assets')
                path=code_path(c['path']); before=repository.baseline.get(path); after=self.code.files.get(path)
                if observed(broker,folder_id,path)!=before: raise AccessDenied('Working-copy preimage differs: '+path)
                changes.append({'path':path,'before':self._pack(before),'after':self._pack(after),
                                'diff':c['diff'][:32768],'diff_partial':len(c['diff'])>32768})
            if not changes: raise AccessDenied('No repository changes to apply')
            value={'id':secrets.token_hex(16),'project_id':self.project_id,'folder_id':folder_id,
                   'grant_identity':broker.saved_grants()[broker.folders().index(grant)],
                   'permission_revision':broker.revision,'code_id':self.code.id,
                   'inventory_sha256':digest(json_bytes(self.code.listing())),
                   'changes':changes,'state':'prepared','completed':[]}
            value['review_sha256']=digest(json_bytes(value))
            self._save(value); return self.inspect(value['id'])

    def inspect(self,identifier):
        v=self._load(identifier)
        return {'id':v['id'],'folder_id':v['folder_id'],'state':v['state'],'review_sha256':v['review_sha256'],
                'changes':[{'path':c['path'],'diff':c['diff'],'diff_partial':c['diff_partial'],
                            'before_blob':c['before'],'after_blob':c['after']} for c in v['changes']],
                'completed':v['completed'],'publication':'Per-file atomic; multi-file interruption needs explicit reconciliation.'}

    def review(self,identifier):
        result=self.inspect(identifier)
        if result['state']!='prepared': raise AccessDenied('Only a fresh prepared transaction can be approved')
        self.reviewed.add(identifier); return result

    def apply(self,identifier,review_sha256):
        self._authorized()
        with self.code._lock:
            v=self._load(identifier); self.code.check()
            if (identifier not in self.reviewed or v['state']!='prepared' or review_sha256!=v['review_sha256']
                    or v['permission_revision']!=self.code.workspace.broker.revision or v['code_id']!=self.code.id
                    or v['inventory_sha256']!=digest(json_bytes(self.code.listing())) or self.code._running):
                raise AccessDenied('Review, code, permissions or approval changed; prepare and review again')
            # Recheck every preimage before the first effect, then atomically in the broker.
            broker=self.code.workspace.broker
            self.code.repository.patch(self.code)
            for c in v['changes']:
                if observed(broker,v['folder_id'],c['path'])!=self._bytes(c['before']):
                    raise AccessDenied('Working copy changed after review')
            self.reviewed.discard(identifier); v['state']='applying'; self._save(v)
            try:
                for c in v['changes']:
                    self.code.check()
                    v['intent']=c['path']; self._save(v)
                    def journal(artifacts):
                        v.setdefault('artifacts',{})[c['path']]={'direction':'apply','names':artifacts}; self._save(v)
                    broker.apply_reviewed_change(v['folder_id'],c['path'],self._bytes(c['before']),self._bytes(c['after']),journal=journal)
                    v['completed'].append(c['path']); v.pop('intent',None); self._save(v)
                v['state']='completed'; self._save(v)
            except BaseException:
                v['state']='unknown'; self._save(v); raise
            return self.inspect(identifier)

    def _pack(self,data):
        if data is None: return None
        sha=digest(data); key='codeblob-'+self.project_id+'-'+sha[:32]
        value={'data':base64.b64encode(data).decode(),'sha256':sha}
        old=self.vault.get(key)
        if old is not None and old!=value: raise AccessDenied('Repository blob identity collision')
        self.vault.put(key,value); return key

    def _bytes(self,value):
        if value is None: return None
        if not isinstance(value,str) or not value.startswith('codeblob-'+self.project_id+'-'):
            raise AccessDenied('Repository blob belongs to another project')
        record=self.vault.get(value)
        if record is None: raise AccessDenied('Repository recovery bytes are missing')
        data=base64.b64decode(record['data'],validate=True)
        if digest(data)!=record['sha256'] or value!='codeblob-'+self.project_id+'-'+digest(data)[:32]:
            raise AccessDenied('Repository recovery bytes changed')
        return data

    def reconcile(self,identifier,action):
        self._authorized()
        if action not in {'keep','rollback'}: raise AccessDenied('Reconcile by keeping inspected changes or explicitly rolling back')
        with self.code._lock:
            v=self._load(identifier); broker=self.code.workspace.broker
            if v['state'] not in {'unknown','applying'}: raise AccessDenied('Only interrupted transactions need reconciliation')
            matches=[f.id for f,g in zip(broker.folders(),broker.saved_grants(),strict=True)
                     if f.access=='editable' and g==v['grant_identity']]
            if len(matches)!=1: raise AccessDenied('Restore the same identity-verified writable grant before reconciliation')
            v['folder_id']=matches[0]
            for c in v['changes']:
                artifacts=v.get('artifacts',{}).get(c['path'])
                if artifacts:
                    before,after=self._bytes(c['before']),self._bytes(c['after'])
                    if artifacts['direction']=='rollback':before,after=after,before
                    broker.reconcile_reviewed_artifacts(v['folder_id'],c['path'],before,after,artifacts['names'])
            current={c['path']:observed(broker,v['folder_id'],c['path']) for c in v['changes']}
            for c in v['changes']:
                if current[c['path']] not in (self._bytes(c['before']),self._bytes(c['after'])):
                    raise AccessDenied('Concurrent content must be preserved; reconcile this path manually')
            if action=='rollback':
                for c in reversed(v['changes']):
                    before,after=self._bytes(c['before']),self._bytes(c['after'])
                    if current[c['path']]==after and before!=after:
                        v['intent']='rollback:'+c['path']; self._save(v)
                        def journal(artifacts):
                            v.setdefault('artifacts',{})[c['path']]={'direction':'rollback','names':artifacts}; self._save(v)
                        broker.apply_reviewed_change(v['folder_id'],c['path'],after,before,journal=journal)
            v.pop('intent',None); v['state']='reconciled-'+action; self._save(v)
            self.reviewed.discard(identifier); return self.inspect(identifier)
