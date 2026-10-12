"""Bounded LSP 3.17 client for an independently contained stdio transport.

Servers never get host paths/grants. Workspace edits, commands, registrations,
downloads, telemetry and arbitrary server requests are refused.
"""
import json
from pathlib import Path
from urllib.parse import urlparse,unquote
from .folders import AccessDenied
from .model import json_bytes,strict_json

METHODS={'symbols':'textDocument/documentSymbol','definitions':'textDocument/definition',
         'references':'textDocument/references','diagnostics':'textDocument/diagnostic'}


class LanguageClient:
    def __init__(self,transport,root,files):
        self.transport,self.root,self.files=transport,Path(root).absolute(),files
        self.sequence=0; self.diagnostics=[]

    def send(self,value):
        data=json_bytes(value)
        if len(data)>256*1024: raise AccessDenied('Language message exceeds its frame')
        self.transport.write(b'Content-Length: '+str(len(data)).encode()+b'\r\n\r\n'+data)

    def receive(self):
        header=bytearray()
        while not header.endswith(b'\r\n\r\n'):
            if len(header)>=4096: raise AccessDenied('Language header is oversized')
            header.extend(self.transport.read_exact(1))
        lengths=[]
        for line in bytes(header[:-4]).split(b'\r\n'):
            name,sep,value=line.partition(b':')
            if not sep: raise AccessDenied('Malformed language header')
            if name.lower()==b'content-length': lengths.append(value.strip())
        if len(lengths)!=1 or not lengths[0].isdigit(): raise AccessDenied('One literal language content length is required')
        size=int(lengths[0])
        if not 0<size<=256*1024: raise AccessDenied('Language response exceeds its frame')
        value=strict_json(self.transport.read_exact(size))
        if not isinstance(value,dict) or value.get('jsonrpc')!='2.0': raise AccessDenied('Malformed language response')
        return value

    def request(self,method,params):
        self.sequence+=1; identifier=self.sequence
        self.send({'jsonrpc':'2.0','id':identifier,'method':method,'params':params})
        for _ in range(256):
            v=self.receive()
            if 'method' in v:
                if 'id' in v:
                    self.send({'jsonrpc':'2.0','id':v['id'],'error':{'code':-32601,'message':'Host actions are unavailable'}})
                elif v['method']=='textDocument/publishDiagnostics':
                    self.diagnostics.append(v.get('params',{}))
                continue
            if type(v.get('id')) is not int or v['id']!=identifier: raise AccessDenied('Unexpected language response identity')
            if 'error' in v: raise AccessDenied('Language server rejected this operation')
            if set(v)!={'jsonrpc','id','result'}: raise AccessDenied('Malformed language result')
            return v['result']
        raise AccessDenied('Language server did not make progress')

    def query(self,action,path,*,line=1,column=1):
        if action not in METHODS or path not in self.files or type(line) is not int or type(column) is not int or min(line,column)<1:
            raise AccessDenied('Select a workspace document and positive source position')
        text=self.files[path].decode('utf-8'); lines=text.splitlines()
        if line>max(1,len(lines)) or column>len(lines[line-1] if lines else '')+1: raise AccessDenied('Source position is outside the document')
        capabilities=self.request('initialize',{'processId':None,'rootUri':self.root.as_uri(),
            'capabilities':{'general':{'positionEncodings':['utf-16']},'textDocument':{'diagnostic':{'dynamicRegistration':False}}},
            'initializationOptions':{},'workspaceFolders':None})
        encoding=(capabilities or {}).get('capabilities',{}).get('positionEncoding','utf-16')
        if encoding!='utf-16': raise AccessDenied('Unsupported language position encoding')
        self.send({'jsonrpc':'2.0','method':'initialized','params':{}})
        uri=(self.root/path).as_uri()
        language={'.py':'python','.js':'javascript','.ts':'typescript','.rs':'rust','.c':'c','.cpp':'cpp'}.get(Path(path).suffix,'plaintext')
        self.send({'jsonrpc':'2.0','method':'textDocument/didOpen','params':{'textDocument':{'uri':uri,'languageId':language,'version':1,'text':text}}})
        # LSP positions count UTF-16 code units, not Python characters.
        character=len((lines[line-1] if lines else '')[:column-1].encode('utf-16-le'))//2
        params={'textDocument':{'uri':uri}}
        if action in {'definitions','references'}: params['position']={'line':line-1,'character':character}
        if action=='references': params['context']={'includeDeclaration':True}
        result=self.request(METHODS[action],params)
        self.request('shutdown',None); self.send({'jsonrpc':'2.0','method':'exit'})
        return {'action':action,'path':path,'result':self._sanitize(result),'engine':'qualified-lsp',
                'source':'Untrusted server response; locations restricted to the disposable snapshot.'}

    def _sanitize(self,value,depth=0):
        if depth>24: raise AccessDenied('Language result is too deeply nested')
        if isinstance(value,list): return [self._sanitize(v,depth+1) for v in value[:100]]
        if isinstance(value,dict):
            result={}
            for key,v in value.items():
                if key in {'command','edit','data'}: continue
                if key in {'uri','targetUri'}:
                    u=urlparse(v)
                    if u.scheme!='file' or u.netloc not in {'','localhost'}: raise AccessDenied('External language location refused')
                    p=Path(unquote(u.path))
                    if len(u.path)>3 and u.path[0]=='/' and u.path[2]==':': p=Path(unquote(u.path[1:]))
                    try: relative=p.relative_to(self.root).as_posix()
                    except ValueError: raise AccessDenied('Language location is outside the snapshot') from None
                    if relative not in self.files: raise AccessDenied('Language location is not a staged file')
                    result['path']=relative
                else: result[key]=self._sanitize(v,depth+1)
            return result
        if isinstance(value,str) and len(value)>8192: return value[:8192]
        if value is None or type(value) in (str,int,float,bool): return value
        raise AccessDenied('Invalid language result')


class NativeLanguageTransport:
    """Private inherited pipes only; every read shares one finite query deadline."""
    def __init__(self,process,*,timeout=20,max_output=256*1024):
        import queue,threading,time
        self.process=process; self.queue=queue.Queue(); self.pending=bytearray(); self.written=0
        self.deadline=time.monotonic()+timeout; self.limit=max_output
        self.output=0;self.output_lock=threading.Lock()
        self.timer=threading.Timer(timeout,lambda:process.kernel.TerminateJobObject(process.job,124)); self.timer.start()
        self.threads=[]
        def read(index):
            import ctypes as C
            from .windows_container import U32
            try:
                while True:
                    buffer,count=C.create_string_buffer(4096),U32()
                    ok=process.kernel.ReadFile(process.parent_handles[index],buffer,len(buffer),C.byref(count),None)
                    if not ok or not count.value: break
                    with self.output_lock:
                        self.output+=count.value
                        if self.output>self.limit: raise AccessDenied('Language output limit exceeded')
                    if index==1: self.queue.put(buffer.raw[:count.value])
            except BaseException as e:
                process.kernel.TerminateJobObject(process.job,125); self.queue.put(e)
            finally:
                if index==1: self.queue.put(None)
        for index in (1,2):
            thread=threading.Thread(target=read,args=(index,),daemon=True);thread.start();self.threads.append(thread)

    def write(self,data):
        import ctypes as C
        from .windows_container import U32,ok
        self.written+=len(data)
        if self.written>1024*1024: raise AccessDenied('Language request limit exceeded')
        while data:
            count=U32(); buffer=C.create_string_buffer(data)
            ok(self.process.kernel.WriteFile(self.process.parent_handles[0],buffer,len(data),C.byref(count),None))
            if not count.value: raise AccessDenied('Language input made no progress')
            data=data[count.value:]

    def read_exact(self,size):
        import time,queue
        while len(self.pending)<size:
            remaining=self.deadline-time.monotonic()
            if remaining<=0: raise AccessDenied('Language query timed out')
            try: value=self.queue.get(timeout=remaining)
            except queue.Empty: raise AccessDenied('Language query timed out') from None
            if value is None: raise AccessDenied('Language server closed its response pipe')
            if isinstance(value,BaseException): raise value
            self.pending.extend(value)
        result=bytes(self.pending[:size]);del self.pending[:size];return result

    def close(self):
        self.timer.cancel(); self.process.close()
        for thread in self.threads: thread.join(timeout=2)
        if any(t.is_alive() for t in self.threads): raise AccessDenied('Language pipe cleanup incomplete')
