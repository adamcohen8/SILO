"""Host-only per-file publication primitives. Never registered as model tools."""
import os
import secrets
from .folders import AccessDenied


def windows_change(broker,folder,path,before,after,*,journal=None):
    from .windows_folders import parts
    components=parts(path); native=broker._native
    with broker._lock:
        grant=broker._get(folder,write=True)
        with broker._directory(grant,components[:-1],create=before is None and after is not None) as parent:
            old=new=None; moved=published=False
            backup='.silo-replace-'+secrets.token_hex(16)
            temporary='.silo-write-'+secrets.token_hex(16)
            artifacts={'backup':backup,'temporary':temporary,'backup_identity':None,'temporary_identity':None}
            if journal: journal(dict(artifacts))
            try:
                if before is None: broker._absent(parent,components[-1])
                else:
                    old=native.open_child(parent,components[-1],directory=False,edit=True)
                    info=broker._check(old,volume=grant.info.volume,directory=False)
                    if native.read(old,broker.max_file_bytes)!=before: raise AccessDenied('Reviewed preimage changed')
                    artifacts['backup_identity']={'volume':info.volume,'index':info.index}
                    if journal:journal(dict(artifacts))
                if after is not None:
                    if not isinstance(after,bytes) or len(after)>broker.max_file_bytes: raise AccessDenied('Oversized reviewed change')
                    new=native.open_child(parent,temporary,directory=False,create=True)
                    info=broker._check(new,volume=grant.info.volume,directory=False)
                    artifacts['temporary_identity']={'volume':info.volume,'index':info.index}
                    if journal:journal(dict(artifacts))
                    native.write(new,after)
                    if old is not None:
                        native.publish(old,parent,backup); moved=True
                    native.publish(new,parent,components[-1]); published=True
                if old is not None: native.discard(old)
            except BaseException:
                if moved and not published:
                    # Exclusive publication refuses a concurrent destination.
                    # A refused restoration keeps the old bytes under backup.
                    try: native.publish(old,parent,components[-1]); moved=False
                    except OSError: raise AccessDenied('Publication interrupted; preserved original at '+backup) from None
                raise
            finally:
                if new is not None:
                    try:
                        if not published: native.discard(new)
                    finally: native.close(new)
                if old is not None: native.close(old)


def posix_change(broker,folder,path,before,after,*,journal=None):
    """Development fixture only: POSIX advisory access does not qualify Windows."""
    from .folders import _parts
    with broker._lock:
        grant=broker._get(folder,write=True); parent=broker._parent(grant,_parts(path),create=before is None and after is not None)
        name=_parts(path)[-1]; temporary='.silo-write-'+secrets.token_hex(16); created=False
        try:
            if before is None:
                try: os.stat(name,dir_fd=parent,follow_symlinks=False)
                except FileNotFoundError: pass
                else: raise AccessDenied('Reviewed destination exists')
            else:
                fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent)
                with os.fdopen(fd,'rb') as f:
                    broker._check_file(grant,os.fstat(f.fileno()))
                    if f.read(broker.max_file_bytes+1)!=before: raise AccessDenied('Reviewed preimage changed')
            if after is None:
                if before is None: raise AccessDenied('Cannot delete an absent target')
                os.unlink(name,dir_fd=parent)
            else:
                if not isinstance(after,bytes) or len(after)>broker.max_file_bytes: raise AccessDenied('Oversized reviewed change')
                fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent); created=True
                with os.fdopen(fd,'wb') as f: f.write(after); f.flush(); os.fsync(f.fileno())
                if before is None: os.link(temporary,name,src_dir_fd=parent,dst_dir_fd=parent,follow_symlinks=False)
                else: os.replace(temporary,name,src_dir_fd=parent,dst_dir_fd=parent); created=False
            os.fsync(parent)
        finally:
            if created: os.unlink(temporary,dir_fd=parent)
            os.close(parent)


def windows_reconcile(broker,folder,path,before,after,artifacts):
    """Restore an interrupted replacement gap; retire only verified owned remnants."""
    import re
    from .windows_folders import parts
    from .repository_apply import observed
    if (not isinstance(artifacts,dict) or set(artifacts)!={'backup','temporary','backup_identity','temporary_identity'}
            or not re.fullmatch(r'\.silo-replace-[0-9a-f]{32}',artifacts['backup'])
            or not re.fullmatch(r'\.silo-write-[0-9a-f]{32}',artifacts['temporary'])):
        raise AccessDenied('Invalid owned repository recovery receipt')
    components=parts(path); native=broker._native
    with broker._lock:
        grant=broker._get(folder,write=True)
        with broker._directory(grant,components[:-1]) as parent:
            current=observed(broker,folder,path)
            if current not in (before,after,None): raise AccessDenied('Concurrent repository bytes must be preserved')
            for key,expected in (('backup',before),('temporary',after)):
                handle=None
                try:
                    try: handle=native.open_child(parent,artifacts[key],directory=False,edit=True)
                    except FileNotFoundError: continue
                    info=broker._check(handle,volume=grant.info.volume,directory=False)
                    if artifacts[key+'_identity']!={'volume':info.volume,'index':info.index}:
                        raise AccessDenied('Recovery remnant identity changed; preserve it for inspection')
                    content=native.read(handle,broker.max_file_bytes)
                    if expected is None or (content!=expected and not(key=='temporary' and expected.startswith(content))):
                        raise AccessDenied('Recovery remnant differs from the reviewed bytes; preserve for inspection')
                    if key=='backup' and current is None and before is not None:
                        native.publish(handle,parent,components[-1]);current=before
                    else: native.discard(handle)
                finally:
                    if handle is not None: native.close(handle)
