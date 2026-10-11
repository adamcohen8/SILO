"""Ordinary-user execution on an administrator-prepared, bounded NTFS volume.

No disk provisioning, mount, detach, elevation or physical-disk selection occurs
in an operational session. An exclusive durable lease and native relative
cleanup block concurrent use and require inspection after unknown outcomes.
"""
import ctypes as C
import hashlib
import os
from pathlib import Path
import re
import secrets

from .folders import AccessDenied
from .model import json_bytes
from .signed_policy import canonical


def volume_record(value):
    if (not isinstance(value,dict) or set(value)!={'format','epoch','drive','volume_name','volume_serial',
            'pool_index','maximum_bytes','user_sid'} or type(value['format']) is not int or value['format']!=1
            or not isinstance(value['epoch'],str) or not re.fullmatch('[a-f0-9]{32}',value['epoch'])
            or value['drive'] not in tuple('QRSTUVWXYZ')
            or not isinstance(value['volume_name'],str)
            or not re.fullmatch(re.escape(r'\\?\Volume{')+
                r'[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12}'+re.escape('}\\'),value['volume_name'])
            or type(value['volume_serial']) is not int or not 0<value['volume_serial']<2**32
            or type(value['pool_index']) is not int or not 0<value['pool_index']<2**64
            or type(value['maximum_bytes']) is not int or value['maximum_bytes']%(1024*1024)
            or not 8*1024*1024<=value['maximum_bytes']<=64*1024*1024
            or not isinstance(value['user_sid'],str) or not re.fullmatch(r'S-1-(?:\d+-){2,14}\d+',value['user_sid'])):
        raise AccessDenied('Administrator must provision an exact bounded code volume and host account')
    return value


def current_user_sid():
    from .windows_container import bind,ok,PTR,U32,BOOL,WSTR
    kernel,adv=C.WinDLL('kernel32',use_last_error=True),C.WinDLL('advapi32',use_last_error=True)
    bind(kernel,'GetCurrentProcess',PTR,[]);bind(kernel,'CloseHandle',BOOL,[PTR]);bind(kernel,'LocalFree',PTR,[PTR])
    bind(adv,'OpenProcessToken',BOOL,[PTR,U32,C.POINTER(PTR)])
    bind(adv,'GetTokenInformation',BOOL,[PTR,U32,PTR,U32,C.POINTER(U32)])
    bind(adv,'ConvertSidToStringSidW',BOOL,[PTR,C.POINTER(PTR)])
    token,text,size=PTR(),PTR(),U32()
    try:
        ok(adv.OpenProcessToken(kernel.GetCurrentProcess(),8,C.byref(token)))
        adv.GetTokenInformation(token,1,None,0,C.byref(size))
        if not 0<size.value<=65536:raise AccessDenied('Host account metadata unavailable')
        buffer=C.create_string_buffer(size.value)
        ok(adv.GetTokenInformation(token,1,buffer,len(buffer),C.byref(size)))
        ok(adv.ConvertSidToStringSidW(PTR.from_buffer(buffer).value,C.byref(text)))
        return C.wstring_at(text)
    finally:
        if text.value:kernel.LocalFree(text)
        if token.value:kernel.CloseHandle(token)


class ManagedVolume:
    def __init__(self,security,max_bytes):
        if os.name!='nt':raise AccessDenied('Managed code storage requires native Windows')
        from .windows_native import NativeFiles
        from .windows_container import bind,ok,BOOL,WSTR,U32,U64,PTR
        security.check()
        self.record=volume_record(security.store.get('code-volume'))
        if self.record['user_sid']!=current_user_sid() or self.record['maximum_bytes']>max_bytes:
            raise AccessDenied('Code volume does not match the accepted host account or disk ceiling')
        self.native=NativeFiles();self.handles=[];self.lease=None;self.closed=False
        self.root=Path(self.record['drive']+':\\')/'pool'
        self.id=secrets.token_hex(16)
        self.kernel=self.native.kernel
        bind(self.kernel,'GetVolumeNameForVolumeMountPointW',BOOL,[WSTR,WSTR,U32])
        bind(self.kernel,'GetDiskFreeSpaceExW',BOOL,[WSTR,C.POINTER(U64),C.POINTER(U64),C.POINTER(U64)])
        bind(self.kernel,'GetVolumeInformationW',BOOL,[WSTR,WSTR,U32,PTR,PTR,PTR,WSTR,U32])
        try:
            drive=self.native.open_drive(self.record['drive']+':\\');self.handles.append(drive)
            name=C.create_unicode_buffer(64)
            ok(self.kernel.GetVolumeNameForVolumeMountPointW(self.record['drive']+':\\',name,len(name)))
            if name.value.casefold()!=self.record['volume_name'].casefold():raise AccessDenied('Code volume mapping changed')
            pool=self.native.open_child(drive,'pool',directory=True,security=True);self.handles.append(pool)
            info=self.native.info(pool)
            if (info.reparse or info.offline or not info.disk or not info.directory
                    or (info.volume,info.index)!=(self.record['volume_serial'],self.record['pool_index'])):
                raise AccessDenied('Code workspace pool identity changed')
            from .machine_security import protected_acl
            protected_acl(pool,private_user=self.record['user_sid'])
            total,free,available=U64(),U64(),U64();fs=C.create_unicode_buffer(32)
            ok(self.kernel.GetDiskFreeSpaceExW(str(self.root),C.byref(available),C.byref(total),C.byref(free)))
            ok(self.kernel.GetVolumeInformationW(self.record['drive']+':\\',None,0,None,None,None,fs,len(fs)))
            if fs.value!='NTFS' or not 0<total.value<=self.record['maximum_bytes']:
                raise AccessDenied('Prepared code volume is not bounded NTFS')
            if self._names(pool):raise AccessDenied('Code pool is leased or contains unreconciled output')
            # CREATE_NEW, no sharing: neither concurrency nor an ordinary-user
            # deletion race can retire the live lease. A crash leaves the marker.
            self.lease=self.native.open_child(pool,'lease.json',directory=False,create=True)
            if set(self._names(pool))!={'lease.json'}:raise AccessDenied('Code pool changed during lease acquisition')
            self.native.write(self.lease,json_bytes({'format':1,'id':self.id,'epoch':self.record['epoch'],
                'configuration_sha256':hashlib.sha256(canonical(self.record)).hexdigest()}))
            self.capacity_bytes=total.value
        except BaseException:
            # Once acquired, keep an outcome-unknown marker. Never infer safety
            # from a missing process handle or an incomplete startup.
            if self.lease:self.native.close(self.lease);self.lease=None
            for handle in reversed(self.handles):self.native.close(handle)
            self.handles.clear();raise

    def _names(self,handle):
        result=[]
        for name in self.native.names(handle):
            if name in {'.','..'}:continue
            result.append(name)
            if len(result)>1024:raise AccessDenied('Code pool inventory requires administrative reconciliation')
        return result

    def close(self):
        if self.closed:return
        pool=self.handles[-1]
        count=0
        def remove(parent,name,depth=0):
            nonlocal count
            count+=1
            if count>1024 or depth>16:raise AccessDenied('Code cleanup requires bounded administrative reconciliation')
            node=self.native.open_child(parent,name,delete=True)
            try:
                info=self.native.info(node)
                if info.reparse or info.offline or not info.disk or info.volume!=self.record['volume_serial']:
                    raise AccessDenied('Unsafe code cleanup object; lease retained')
                if info.directory:
                    self.native.close(node);node=None
                    node=self.native.open_child(parent,name,directory=True,delete=True)
                    for child in self._names(node):remove(node,child,depth+1)
                elif info.links!=1:raise AccessDenied('Linked code cleanup object; lease retained')
                self.native.discard(node)
            finally:
                if node:self.native.close(node)
        try:
            names=self._names(pool)
            if any(name not in {'work','lease.json'} for name in names):raise AccessDenied('Unexpected code pool storage; lease retained')
            if 'work' in names:remove(pool,'work')
            if set(self._names(pool))!={'lease.json'}:raise AccessDenied('Code pool cleanup incomplete')
            self.native.discard(self.lease)
            self.native.close(self.lease);self.lease=None
            if self._names(pool):raise AccessDenied('Code lease retirement did not complete')
        finally:
            if self.lease:self.native.close(self.lease);self.lease=None
            for handle in reversed(self.handles):self.native.close(handle)
            self.handles.clear();self.closed=True
