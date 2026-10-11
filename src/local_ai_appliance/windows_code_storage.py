"""Owned fixed-size NTFS VHD for candidate generated-code execution.

Host-only DiskPart commands, with no generated script text or physical disk
selection. Never elevates, never changes machine execution/network policies.
"""
import ctypes as C
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess

from .asset_integrity import ordinary
from .folders import AccessDenied
from .windows_container import bind, ok, U32, U64, WSTR, PTR, BOOL


def provision_script(image, drive, size_mib):
    image=str(image)
    if (any(c in image for c in '"\r\n') or not image.lower().endswith('.vhd')
            or drive not in 'QRSTUVWXYZ' or type(size_mib) is not int or not 8<=size_mib<=64):
        raise AccessDenied('Invalid owned virtual disk parameters')
    return (f'create vdisk file="{image}" maximum={size_mib} type=fixed\n'
            f'select vdisk file="{image}"\nattach vdisk\ncreate partition primary\n'
            f'format fs=ntfs quick label=SILO\nassign letter={drive}\nexit\n')


class FixedVolume:
    def __init__(self,state,max_bytes):
        if os.name!='nt': raise AccessDenied('Code storage requires native Windows')
        if type(max_bytes) is not int or max_bytes % (1024*1024) or not 8*1024*1024<=max_bytes<=64*1024*1024:
            raise AccessDenied('Native disk budget must be 8–64 whole MiB')
        state=Path(state).absolute(); ordinary(state,directory=True)
        self.kernel=C.WinDLL('kernel32',use_last_error=True)
        bind(self.kernel,'GetLogicalDrives',U32,[])
        bind(self.kernel,'GetVolumeNameForVolumeMountPointW',BOOL,[WSTR,WSTR,U32])
        bind(self.kernel,'GetDiskFreeSpaceExW',BOOL,[WSTR,C.POINTER(U64),C.POINTER(U64),C.POINTER(U64)])
        bind(self.kernel,'GetVolumeInformationW',BOOL,[WSTR,WSTR,U32,PTR,PTR,PTR,WSTR,U32])
        self.id=secrets.token_hex(16)
        self.directory=state/('run-'+self.id); self.directory.mkdir()
        self.image=self.directory/'workspace.vhd'
        self.receipt=self.directory/'lease.json'
        self.closed=False; self.attached=False; self.identity=None; self.volume=None
        available=~self.kernel.GetLogicalDrives()
        self.drive=next((d for d in reversed('QRSTUVWXYZ') if available & (1 << (ord(d)-ord('A')))),None)
        if self.drive is None: raise AccessDenied('No unused evaluation drive letter')
        self.root=Path(self.drive+':\\')
        self.receipt.write_text(json.dumps({'version':1,'id':self.id,'image':'workspace.vhd','drive':self.drive})+'\n')
        try:
            # Mark possible attachment before attempting an outcome-unknown command.
            self.attached=True
            self._command(provision_script(self.image,self.drive,max_bytes//(1024*1024)))
            info=ordinary(self.image)
            if not max_bytes <= info.st_size <= max_bytes+1024*1024:
                raise AccessDenied('Owned fixed VHD has an unexpected allocation')
            self.identity=(info.st_dev,info.st_ino)
            self.volume=self._volume()
            total,free,available_bytes=U64(),U64(),U64()
            ok(self.kernel.GetDiskFreeSpaceExW(str(self.root),C.byref(available_bytes),C.byref(total),C.byref(free)))
            fs=C.create_unicode_buffer(32)
            ok(self.kernel.GetVolumeInformationW(str(self.root),None,0,None,None,None,fs,len(fs)))
            if fs.value!='NTFS' or not 0 < total.value <= max_bytes:
                raise AccessDenied('Code storage is not a bounded NTFS volume')
            self.capacity_bytes=total.value
        except BaseException:
            # An unproven/missing image is never deleted as a presumed successful
            # cleanup. The lease remains and blocks another session.
            if self.image.exists():
                info=ordinary(self.image); self.identity=(info.st_dev,info.st_ino)
                try: self.close()
                except Exception: pass
            raise

    def _volume(self):
        result=C.create_unicode_buffer(64)
        ok(self.kernel.GetVolumeNameForVolumeMountPointW(str(self.root),result,len(result)))
        return result.value

    def _command(self,text):
        script=self.directory/('diskpart-'+secrets.token_hex(8)+'.txt')
        script.write_text(text,encoding='ascii')
        bind(self.kernel,'GetSystemDirectoryW',U32,[WSTR,U32])
        directory=C.create_unicode_buffer(32768)
        length=self.kernel.GetSystemDirectoryW(directory,len(directory))
        if not 0<length<len(directory): raise AccessDenied('Trusted Windows system directory unavailable')
        system_directory=Path(directory.value); ordinary(system_directory,directory=True)
        command=system_directory/'diskpart.exe'
        info=command.lstat()
        # OS servicing can hard-link this trusted system executable. Application
        # payloads and owned VHD files still require ordinary single-link files.
        if not stat.S_ISREG(info.st_mode) or getattr(info,'st_file_attributes',0)&0x441400:
            raise AccessDenied('Trusted disk provisioning executable unavailable')
        try:
            # One fixed, host-authored command file; output is bounded by command
            # count, and contains no task data. No shell or automatic elevation.
            completed=subprocess.run([str(command),'/s',str(script)],stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30,check=False,
                creationflags=0x08000000)
            if completed.returncode!=0: raise AccessDenied('Owned VHD provisioning failed; native permissions or NTFS support unavailable')
        finally: script.unlink()

    def close(self):
        if self.closed: return
        if self.identity is None: raise AccessDenied('Unverified disk lease requires explicit reconciliation')
        info=ordinary(self.image)
        if (info.st_dev,info.st_ino)!=self.identity:
            raise AccessDenied('Owned disk identity changed; cleanup refused')
        if self.attached:
            if self.volume is not None and self._volume()!=self.volume:
                raise AccessDenied('Owned volume identity changed; cleanup refused')
            self._command(f'select vdisk file="{self.image}"\ndetach vdisk\nexit\n')
            try: current=self._volume()
            except OSError: current=None
            if self.volume is not None and current==self.volume:
                raise AccessDenied('Owned volume remained attached after cleanup')
            self.attached=False
        info=ordinary(self.image)
        if (info.st_dev,info.st_ino)!=self.identity: raise AccessDenied('Owned image changed before deletion')
        self.image.unlink(); self.receipt.unlink(); self.directory.rmdir(); self.closed=True


def require_clean_state(state):
    state=Path(state)
    state.mkdir(parents=True,exist_ok=True)
    ordinary(state,directory=True)
    if any(state.iterdir()):
        raise AccessDenied('Unreconciled code-run lease exists; inspect owned VHD/profile cleanup before new execution')
