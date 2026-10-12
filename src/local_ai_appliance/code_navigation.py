"""Incremental source navigation. Python AST; explicitly lexical results elsewhere.

No source is imported, compiled to executable code, or sent to a service. The
index is discarded when the workspace closes and rebuilt after permission drift.
"""
import ast
import io
import re
import tokenize
from .code_workspace import digest
from .folders import AccessDenied
from .model import json_bytes

SUPPORTED={'.py','.js','.jsx','.cjs','.mjs','.ts','.tsx','.rs','.c','.cpp','.h','.hpp'}


class NavigationIndex:
    def __init__(self): self.cache={};self.partial=[];self.next_file_offset=None;self.total_source_files=0

    @classmethod
    def for_code(cls,code,*,file_offset=0):
        index=getattr(code,'navigation',None)
        if index is None: index=code.navigation=cls()
        with code._lock:
            code.check()
            if type(file_offset) is not int or file_offset<0:raise AccessDenied('Invalid source inventory page')
            paths=sorted(p for p in code.files if '.'+p.rsplit('.',1)[-1] in SUPPORTED)
            index.refresh({p:code.files[p] for p in paths[file_offset:file_offset+128]})
            index.total_source_files=len(paths)
            index.next_file_offset=file_offset+128 if file_offset+128<len(paths) else None
        return index

    def refresh(self,files):
        self.partial=[]
        self.cache={p:c for p,c in self.cache.items() if p in files}
        for path,data in files.items():
            if '.'+path.rsplit('.',1)[-1] not in SUPPORTED: continue
            sha=digest(data)
            if path in self.cache and self.cache[path]['sha256']==sha:
                if self.cache[path].get('partial'):self.partial.append(path)
                continue
            symbols=[]; refs=[]; diagnostics=[]
            if len(data)>256*1024:
                self.cache.pop(path,None); self.partial.append(path); continue
            try: text=data.decode('utf-8')
            except UnicodeError: continue
            engine='python-ast' if path.endswith('.py') else 'lexical'
            if engine=='python-ast':
                try:
                    tree=ast.parse(text,filename=path)
                    for node in ast.walk(tree):
                        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                            symbols.append({'name':node.name,'kind':'class' if isinstance(node,ast.ClassDef) else 'function',
                                            'line':node.lineno,'column':node.col_offset+1})
                            if len(symbols)>=2000:self.partial.append(path);break
                    for token in tokenize.generate_tokens(io.StringIO(text).readline):
                        if token.type==tokenize.NAME:
                            refs.append({'name':token.string,'line':token.start[0],'column':token.start[1]+1})
                            if len(refs)>=2000:self.partial.append(path);break
                except (SyntaxError,tokenize.TokenError,RecursionError) as e:
                    diagnostics.append({'kind':'error','line':getattr(e,'lineno',1) or 1,
                                        'column':getattr(e,'offset',1) or 1,'message':getattr(e,'msg',str(e))[:1024]})
            else:
                for line_number,line in enumerate(text.splitlines(),1):
                    for match in re.finditer(r'\b[A-Za-z_][A-Za-z_0-9]*\b',line):
                        refs.append({'name':match[0],'line':line_number,'column':match.start()+1})
                        if len(refs)>=2000:self.partial.append(path);break
                    m=re.search(r'\b(class|function|interface|enum|struct|trait|fn)\s+([A-Za-z_][A-Za-z_0-9]*)',line)
                    if m: symbols.append({'name':m[2],'kind':m[1],'line':line_number,'column':m.start(2)+1})
                    if len(refs)>=2000:break
            if len(refs)>2000 or len(symbols)>2000: self.partial.append(path)
            symbols,refs=symbols[:2000],refs[:2000]
            self.cache[path]={'sha256':sha,'engine':engine,'symbols':symbols,'references':refs,'diagnostics':diagnostics,'partial':path in self.partial}

    def query(self,action,query='',offset=0):
        if action not in {'symbols','definitions','references','diagnostics'} or not isinstance(query,str) or len(query)>256:
            raise AccessDenied('Navigate symbols, definitions, references or diagnostics with bounded text')
        if type(offset) is not int or offset<0: raise AccessDenied('Invalid navigation offset')
        key='symbols' if action in {'symbols','definitions'} else action
        items=[]
        for path,v in sorted(self.cache.items()):
            for item in v[key]:
                name=item.get('name','')
                if query and (name!=query if action in {'definitions','references'} else query.casefold() not in json_bytes(item).decode().casefold()): continue
                items.append({'path':path,'sha256':v['sha256'],'engine':v['engine'],**item})
        page=items[offset:offset+100]
        while len(json_bytes(page))>32*1024: page.pop()
        return {'items':page,'total':len(items),'next_offset':offset+len(page) if offset+len(page)<len(items) else None,
                'partial_files':self.partial,
                'total_source_files':self.total_source_files,'next_file_offset':self.next_file_offset,
                'limitations':'References are name occurrences, not resolved bindings. Non-Python results are lexical; use a qualified language server for semantic navigation.'}
