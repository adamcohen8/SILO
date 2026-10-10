"""Scoped recovery after an explicit request to restart a frozen interface.

Identify the model's actual AppContainer token before stopping the verified
process tree. Revoke only that SID's known asset leases and remove its profile.
No blanket Python/model termination, host ACL reset or network-policy changes.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import re
import shutil
import sys
import winreg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from local_ai_appliance.windows_container import AppContainer, PTR, U32, BOOL, WSTR, ExplicitAccess, bind, ok
from local_ai_appliance.windows_native import NativeFiles


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-pid', type=int, required=True)
    parser.add_argument('--gui-pid', type=int, required=True)
    parser.add_argument('--launcher-pid', type=int, required=True)
    parser.add_argument('--ipc', required=True)
    args = parser.parse_args()
    runtime = ROOT/'artifacts/inference/runtime-b11433-cuda12.4'
    sdk = ROOT/'artifacts/isolation-evaluation/python'
    profile = json.loads((ROOT/'profiles/nemotron-30b-4090-candidate.json').read_text())
    model_name = profile['model']['file']
    if Path(model_name).name != model_name:
        raise RuntimeError('Unsafe model path')
    model = ROOT/'artifacts/inference/downloads'/model_name
    ipc = Path(args.ipc).resolve()
    if (ipc.parent != (ROOT/'artifacts').resolve() or not re.fullmatch(r'i-[0-9a-f]{8}', ipc.name)
            or ipc.is_symlink()):
        raise RuntimeError('Unsafe IPC recovery target')
    owner = AppContainer.__new__(AppContainer)
    owner.kernel = k = C.WinDLL('kernel32', use_last_error=True)
    owner.adv = a = C.WinDLL('advapi32', use_last_error=True)
    u = C.WinDLL('userenv', use_last_error=True)
    bind(k, 'OpenProcess', PTR, [U32, BOOL, U32])
    bind(k, 'CloseHandle', BOOL, [PTR])
    bind(k, 'QueryFullProcessImageNameW', BOOL, [PTR, U32, WSTR, C.POINTER(U32)])
    bind(k, 'TerminateProcess', BOOL, [PTR, U32])
    bind(k, 'WaitForSingleObject', U32, [PTR, U32])
    bind(k, 'CreateFileW', PTR, [WSTR, U32, U32, PTR, U32, U32, PTR])
    bind(k, 'LocalFree', PTR, [PTR])
    bind(a, 'OpenProcessToken', BOOL, [PTR, U32, C.POINTER(PTR)])
    bind(a, 'GetTokenInformation', BOOL, [PTR, U32, PTR, U32, C.POINTER(U32)])
    bind(a, 'ConvertSidToStringSidW', BOOL, [PTR, C.POINTER(PTR)])
    bind(a, 'ConvertStringSidToSidW', BOOL, [WSTR, C.POINTER(PTR)])
    bind(a, 'GetSecurityInfo', U32, [PTR, U32, U32]+[C.POINTER(PTR)]*5)
    bind(a, 'SetEntriesInAclW', U32, [U32, C.POINTER(ExplicitAccess), PTR, C.POINTER(PTR)])
    bind(a, 'SetSecurityInfo', U32, [PTR, U32, U32, PTR, PTR, PTR, PTR])
    bind(a, 'FreeSid', PTR, [PTR])
    bind(u, 'DeriveAppContainerSidFromAppContainerName', C.c_int32, [WSTR, C.POINTER(PTR)])
    bind(u, 'DeleteAppContainerProfile', C.c_int32, [WSTR])
    expected = [(args.model_pid, runtime/'llama-server.exe'),
                (args.gui_pid, Path(sys.base_prefix)/'pythonw.exe'),
                (args.launcher_pid, ROOT/'artifacts/windows-evaluation/venv/Scripts/pythonw.exe')]
    handles = []
    report = {'processes_stopped': [], 'asset_leases_revoked': [], 'cleanup_complete': False}
    owner.sid = PTR()
    try:
        for pid, executable in expected:
            handle = ok(k.OpenProcess(0x101001, False, pid))
            handles.append(handle)
            path, size = C.create_unicode_buffer(32768), U32(32768)
            ok(k.QueryFullProcessImageNameW(handle, 0, path, C.byref(size)))
            if Path(path.value).resolve() != executable.resolve():
                raise RuntimeError('Recovery process identity did not match the project launcher')
        token = PTR()
        ok(a.OpenProcessToken(handles[0], 8, C.byref(token)))
        try:
            sid_buffer = owner._token_value(token, 31)
            sid = owner._sid_string(PTR.from_buffer(sid_buffer).value)
            owner.sid_text = sid
        finally:
            k.CloseHandle(token)
        # Native verification requires zero capabilities and the low label.
        report['model_token'] = owner.verify_token(handles[0])
        key = r'Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppContainer\Mappings'+'\\'+sid
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as mapping:
            name = winreg.QueryValueEx(mapping, 'Moniker')[0]
        if not re.fullmatch(r'localai\.eval\.[0-9a-f]{24}', name):
            raise RuntimeError('The model token is not an owned evaluation profile')
        derived = PTR()
        if u.DeriveAppContainerSidFromAppContainerName(name, C.byref(derived)) != 0:
            raise RuntimeError('Could not verify the profile identity')
        try:
            if owner._sid_string(derived) != sid:
                raise RuntimeError('Profile SID mismatch')
        finally:
            a.FreeSid(derived)
        report['profile_name'] = name
        # Persist exact recovery ownership before terminating the GUI host.
        report_path = ROOT/'artifacts/windows-ui/restart-recovery.json'
        report_path.write_text(json.dumps(report, indent=2)+'\n')
        for handle, (pid, _) in zip(handles, expected):
            if k.WaitForSingleObject(handle, 0) != 0:
                ok(k.TerminateProcess(handle, 126))
            if k.WaitForSingleObject(handle, 10000) != 0:
                raise RuntimeError('Owned process did not stop')
            report['processes_stopped'].append(pid)
        ok(a.ConvertStringSidToSidW(sid, C.byref(owner.sid)))
        for path, directory in ((runtime, True), (model, False), (sdk, True), (ipc, True)):
            if not path.exists():
                continue
            handle = k.CreateFileW(str(path), 0x60080, 7, None, 3, 0x02300000, None)
            if handle in {None, C.c_void_p(-1).value}:
                raise RuntimeError('Recovery ACL handle unavailable')
            try:
                info = NativeFiles().info(handle)
                if (not info.disk or info.reparse or info.offline or info.directory != directory
                        or not directory and info.links != 1):
                    raise RuntimeError('Recovery asset changed identity')
                owner._acl(handle, 4, 0, 0)
                report['asset_leases_revoked'].append(str(path.relative_to(ROOT)))
            finally:
                k.CloseHandle(handle)
        if u.DeleteAppContainerProfile(name) != 0:
            raise RuntimeError('Evaluation profile recovery failed')
        if ipc.exists():
            shutil.rmtree(ipc)
        report['cleanup_complete'] = True
        report_path.write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))
    finally:
        if owner.sid.value:
            k.LocalFree(owner.sid)
        for handle in handles:
            k.CloseHandle(handle)

if __name__ == '__main__':
    main()
