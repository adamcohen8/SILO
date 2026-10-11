"""Explicit administrator preparation of a new empty fixed-size virtual volume.

Creates only a new owned VHD; no physical-disk identifier is accepted. Leaves
unknown outcomes and existing allocations for operator inspection. Run before
collecting independent native acceptance, never from a model tool or session.
"""
import argparse
import ctypes as C
import hashlib
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from local_ai_appliance.machine_security import MachineStore,ADMIN_SDDL
from local_ai_appliance.managed_code_storage import volume_record
from local_ai_appliance.windows_code_storage import FixedVolume
from local_ai_appliance.signed_policy import administrative_access,canonical
from local_ai_appliance.folders import AccessDenied


def set_acl(handle,sddl):
    from local_ai_appliance.windows_container import bind,ok,PTR,U32,BOOL,WSTR
    adv,kernel=C.WinDLL('advapi32',use_last_error=True),C.WinDLL('kernel32',use_last_error=True)
    bind(adv,'ConvertStringSecurityDescriptorToSecurityDescriptorW',BOOL,[WSTR,U32,C.POINTER(PTR),PTR])
    bind(adv,'GetSecurityDescriptorOwner',BOOL,[PTR,C.POINTER(PTR),C.POINTER(BOOL)])
    bind(adv,'GetSecurityDescriptorDacl',BOOL,[PTR,C.POINTER(BOOL),C.POINTER(PTR),C.POINTER(BOOL)])
    bind(adv,'SetSecurityInfo',U32,[PTR,U32,U32,PTR,PTR,PTR,PTR]);bind(kernel,'LocalFree',PTR,[PTR])
    descriptor,owner,dacl=PTR(),PTR(),PTR();present,defaulted=BOOL(),BOOL()
    try:
        ok(adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl,1,C.byref(descriptor),None))
        ok(adv.GetSecurityDescriptorOwner(descriptor,C.byref(owner),C.byref(defaulted)))
        ok(adv.GetSecurityDescriptorDacl(descriptor,C.byref(present),C.byref(dacl),C.byref(defaulted)))
        if not present.value or adv.SetSecurityInfo(handle,1,0x80000005,owner,None,dacl,None):
            raise AccessDenied('Code-volume ACL provisioning failed')
    finally:
        if descriptor.value:kernel.LocalFree(descriptor)


def acl_handle(native,path,*,directory):
    handle=native.kernel.CreateFileW(str(path),0xe0080,3,None,3,0x02300000,None)
    if handle in {None,C.c_void_p(-1).value}:raise AccessDenied('New owned volume ACL handle unavailable')
    info=native.info(handle)
    if (info.reparse or info.offline or not info.disk or info.directory!=directory
            or not directory and info.links!=1):
        native.close(handle);raise AccessDenied('Unsafe newly provisioned volume object')
    return handle


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user-sid',required=True,help='Exact ordinary SILO host account SID')
    parser.add_argument('--size-mib',type=int,choices=range(8,65),default=16)
    args=parser.parse_args();administrative_access()
    if not re.fullmatch(r'S-1-(?:\d+-){2,14}\d+',args.user_sid):parser.error('Exact host account SID required')
    from local_ai_appliance.windows_native import NativeFiles
    from local_ai_appliance.security_events import WindowsEventSink,SecurityAudit
    with_store=MachineStore(writable=True);sink=WindowsEventSink();audit=SecurityAudit(sink)
    native=NativeFiles();handles=[];volume=None
    try:
        if with_store.get('code-volume') is not None:raise AccessDenied('A code pool already exists; inspect/reconcile it instead of replacing it')
        audit.emit('policy','attempt')
        base=with_store.path/'code-volumes'
        if base.exists():raise AccessDenied('Existing code-volume preparations require inspection; nothing was replaced')
        base.mkdir()
        handle=acl_handle(native,base,directory=True);handles.append(handle)
        set_acl(handle,ADMIN_SDDL.replace('(A;OICI;0x1200a9;;;BU)',''))
        volume=FixedVolume(base,args.size_mib*1024*1024)
        # The backing image can retain plaintext CUI sectors after logical
        # cleanup. Only SYSTEM/Administrators can read it; the registered host
        # account accesses the mounted NTFS filesystem, not the image file.
        for path,directory in ((volume.directory,True),(volume.image,False)):
            handle=acl_handle(native,path,directory=directory);handles.append(handle)
            set_acl(handle,'O:BAD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)')
        root=acl_handle(native,volume.root,directory=True);handles.append(root)
        name=C.create_unicode_buffer(32768)
        from local_ai_appliance.windows_container import bind,U32,PTR,WSTR
        bind(native.kernel,'GetFinalPathNameByHandleW',U32,[PTR,WSTR,U32,U32])
        length=native.kernel.GetFinalPathNameByHandleW(root,name,len(name),1)
        if not 0<length<len(name) or name.value.rstrip('\\').casefold()!=volume.volume.rstrip('\\').casefold():
            raise AccessDenied('Owned virtual volume mapping changed; no root ACL was modified')
        set_acl(root,f'O:BAD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;{args.user_sid})')
        pool=native.open_child(root,'pool',directory=True,create=True);handles.append(pool)
        info=native.info(pool)
        pool_acl=acl_handle(native,volume.root/'pool',directory=True);handles.append(pool_acl)
        check=native.info(pool_acl)
        if (check.volume,check.index)!=(info.volume,info.index):raise AccessDenied('New code-pool identity changed before protection')
        set_acl(pool_acl,f'O:BAD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;{args.user_sid})')
        record=volume_record({'format':1,'epoch':volume.id,'drive':volume.drive,'volume_name':volume.volume,
            'volume_serial':info.volume,'pool_index':info.index,'maximum_bytes':args.size_mib*1024*1024,'user_sid':args.user_sid})
        with_store.put('code-volume',record)
        audit.emit('policy','success',policy_sha256=hashlib.sha256(canonical(record)).hexdigest())
        print('Empty bounded code volume enrolled; leave it mounted. Independent acceptance for this exact volume configuration is still required.')
    except Exception:
        try:audit.emit('policy','failed')
        except Exception:pass
        # Do not detach/delete an outcome-unknown image or format any existing
        # disk. Durable preparation receipts identify the exact owned VHD.
        raise
    finally:
        for handle in reversed(handles):native.close(handle)
        with_store.close();sink.close()


if __name__=='__main__':main()
