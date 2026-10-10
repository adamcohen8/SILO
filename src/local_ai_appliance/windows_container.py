"""Explicit AppContainer evaluation launcher, not a production supervisor.

Trusted host use only. Creates a unique, zero-capability profile; validates the
suspended token; bounds the process in a job; inherits only three private pipe
ends; disallows child creation. No permissive launch fallback. ACL leases apply
only to caller-selected evaluation software and are removed on cleanup.
"""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import threading

U32, U64, SIZE, PTR, BOOL = C.c_uint32, C.c_uint64, C.c_size_t, C.c_void_p, C.c_int32
WSTR = C.c_wchar_p


class SecurityAttributes(C.Structure):
    _fields_ = [("length", U32), ("descriptor", PTR), ("inherit", BOOL)]


class SecurityCapabilities(C.Structure):
    _fields_ = [("sid", PTR), ("capabilities", PTR), ("count", U32), ("reserved", U32)]


class StartupInfo(C.Structure):
    _fields_ = [("cb", U32), ("reserved", WSTR), ("desktop", WSTR), ("title", WSTR),
                ("x", U32), ("y", U32), ("xsize", U32), ("ysize", U32),
                ("xchars", U32), ("ychars", U32), ("fill", U32), ("flags", U32),
                ("show", C.c_uint16), ("reserved_size", C.c_uint16), ("reserved_data", PTR),
                ("stdin", PTR), ("stdout", PTR), ("stderr", PTR)]


class StartupInfoEx(C.Structure):
    _fields_ = [("startup", StartupInfo), ("attributes", PTR)]


class ProcessInfo(C.Structure):
    _fields_ = [("process", PTR), ("thread", PTR), ("pid", U32), ("tid", U32)]


class BasicLimits(C.Structure):
    _fields_ = [("process_time", C.c_int64), ("job_time", C.c_int64), ("flags", U32),
                ("minimum_working_set", SIZE), ("maximum_working_set", SIZE),
                ("active_processes", U32), ("affinity", SIZE), ("priority", U32), ("scheduling", U32)]


class ExtendedLimits(C.Structure):
    _fields_ = [("basic", BasicLimits), ("io", U64 * 6), ("process_memory", SIZE),
                ("job_memory", SIZE), ("peak_process_memory", SIZE), ("peak_job_memory", SIZE)]


class Trustee(C.Structure):
    _fields_ = [("multiple", PTR), ("operation", U32), ("form", U32), ("kind", U32), ("name", PTR)]


class ExplicitAccess(C.Structure):
    _fields_ = [("permissions", U32), ("mode", U32), ("inheritance", U32), ("trustee", Trustee)]


def bind(library, name, result, arguments):
    function = getattr(library, name)
    function.restype, function.argtypes = result, arguments
    return function


def ok(value):
    if not value:
        raise OSError(C.get_last_error(), "Contained Windows API operation failed")
    return value


class AppContainer:
    def __init__(self, *, evaluation=False, private_desktop=True):
        if os.name != "nt" or evaluation is not True:
            raise RuntimeError("Explicit native Windows evaluation required")
        self.kernel = C.WinDLL("kernel32", use_last_error=True)
        self.adv = C.WinDLL("advapi32", use_last_error=True)
        self.userenv = C.WinDLL("userenv", use_last_error=True)
        k, a, u = self.kernel, self.adv, self.userenv
        bind(u, "CreateAppContainerProfile", C.c_int32, [WSTR, WSTR, WSTR, PTR, U32, C.POINTER(PTR)])
        bind(u, "DeleteAppContainerProfile", C.c_int32, [WSTR])
        bind(a, "FreeSid", PTR, [PTR])
        bind(k, "CloseHandle", BOOL, [PTR])
        bind(k, "LocalFree", PTR, [PTR])
        bind(k, "CreatePipe", BOOL, [C.POINTER(PTR), C.POINTER(PTR), C.POINTER(SecurityAttributes), U32])
        bind(k, "SetHandleInformation", BOOL, [PTR, U32, U32])
        bind(k, "InitializeProcThreadAttributeList", BOOL, [PTR, U32, U32, C.POINTER(SIZE)])
        bind(k, "UpdateProcThreadAttribute", BOOL, [PTR, U32, SIZE, PTR, SIZE, PTR, PTR])
        bind(k, "DeleteProcThreadAttributeList", None, [PTR])
        bind(k, "CreateProcessW", BOOL, [WSTR, WSTR, PTR, PTR, BOOL, U32, PTR, WSTR,
                                        C.POINTER(StartupInfoEx), C.POINTER(ProcessInfo)])
        bind(k, "CreateJobObjectW", PTR, [PTR, WSTR])
        bind(k, "SetInformationJobObject", BOOL, [PTR, U32, PTR, U32])
        bind(k, "AssignProcessToJobObject", BOOL, [PTR, PTR])
        bind(k, "TerminateJobObject", BOOL, [PTR, U32])
        bind(k, "ResumeThread", U32, [PTR])
        bind(k, "WaitForSingleObject", U32, [PTR, U32])
        bind(k, "GetExitCodeProcess", BOOL, [PTR, C.POINTER(U32)])
        bind(k, "TerminateProcess", BOOL, [PTR, U32])
        bind(k, "ReadFile", BOOL, [PTR, PTR, U32, C.POINTER(U32), PTR])
        bind(k, "WriteFile", BOOL, [PTR, PTR, U32, C.POINTER(U32), PTR])
        bind(a, "OpenProcessToken", BOOL, [PTR, U32, C.POINTER(PTR)])
        bind(a, "GetTokenInformation", BOOL, [PTR, U32, PTR, U32, C.POINTER(U32)])
        bind(a, "ConvertSidToStringSidW", BOOL, [PTR, C.POINTER(PTR)])
        bind(k, "CreateFileW", PTR, [WSTR, U32, U32, PTR, U32, U32, PTR])
        bind(a, "GetSecurityInfo", U32, [PTR, U32, U32] + [C.POINTER(PTR)] * 5)
        bind(a, "SetEntriesInAclW", U32, [U32, C.POINTER(ExplicitAccess), PTR, C.POINTER(PTR)])
        bind(a, "SetSecurityInfo", U32, [PTR, U32, U32, PTR, PTR, PTR, PTR])
        self.name = "localai.eval." + secrets.token_hex(12)
        self.sid = PTR()
        self.leases, self.processes = [], []
        self.station, self.desktop = None, None
        self.closed = False
        result = u.CreateAppContainerProfile(self.name, "Local AI synthetic evaluation",
                                             "Temporary zero-capability profile", None, 0, C.byref(self.sid))
        if result != 0:
            raise OSError(f"Profile creation failed: HRESULT 0x{result & 0xffffffff:08X}")
        try:
            self.sid_text = self._sid_string(self.sid)
            if private_desktop is True:
                self._private_desktop()
            elif private_desktop is False:
                self.desktop_name = ""  # Explicit compatibility diagnostic, not a UI qualification.
            else:
                raise OSError("Invalid evaluation desktop mode")
        except BaseException:
            self.close()
            raise

    def _private_desktop(self):
        """Own invisible low-integrity UI objects; never modify WinSta0 ACLs."""
        u = self.ui = C.WinDLL("user32", use_last_error=True)
        bind(u, "GetProcessWindowStation", PTR, [])
        bind(u, "GetUserObjectInformationW", BOOL, [PTR, C.c_int32, PTR, U32, C.POINTER(U32)])
        bind(u, "CreateDesktopW", PTR, [WSTR, WSTR, PTR, U32, U32, C.POINTER(SecurityAttributes)])
        bind(u, "CloseWindowStation", BOOL, [PTR])
        bind(u, "CloseDesktop", BOOL, [PTR])
        bind(self.adv, "ConvertStringSecurityDescriptorToSecurityDescriptorW", BOOL,
             [WSTR, U32, C.POINTER(PTR), C.POINTER(U32)])
        bind(self.adv, "GetSecurityDescriptorSacl", BOOL, [PTR, C.POINTER(BOOL), C.POINTER(PTR), C.POINTER(BOOL)])
        token, descriptor = PTR(), PTR()
        ok(self.adv.OpenProcessToken(PTR(-1), 8, C.byref(token)))
        try:
            user_buffer = self._token_value(token, 1)
            user = self._sid_string(PTR.from_buffer(user_buffer).value)
            sddl = f"D:P(A;;GA;;;{user})(A;;GA;;;SY)(A;;GA;;;{self.sid_text})"
            ok(self.adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, C.byref(descriptor), None))
            sa = SecurityAttributes(C.sizeof(SecurityAttributes), descriptor, 0)
            station = ok(u.GetProcessWindowStation())  # Existing handle; never changed or closed here.
            station_name, needed = C.create_unicode_buffer(512), U32()
            ok(u.GetUserObjectInformationW(station, 2, station_name, C.sizeof(station_name), C.byref(needed)))
            self.desktop = ok(u.CreateDesktopW(self.name, None, None, 0, 0xF01FF, C.byref(sa)))
            label = PTR()
            ok(self.adv.ConvertStringSecurityDescriptorToSecurityDescriptorW("S:(ML;;NW;;;LW)", 1, C.byref(label), None))
            try:
                present, defaulted, sacl = BOOL(), BOOL(), PTR()
                ok(self.adv.GetSecurityDescriptorSacl(label, C.byref(present), C.byref(sacl), C.byref(defaulted)))
                for handle in (self.desktop,):
                    result = self.adv.SetSecurityInfo(handle, 7, 0x10, None, None, None, sacl)
                    if result:
                        raise OSError(result, "Private UI label update failed")
            finally:
                self.kernel.LocalFree(label)
            self.desktop_name = station_name.value + "\\" + self.name
        finally:
            if descriptor.value:
                self.kernel.LocalFree(descriptor)
            self.kernel.CloseHandle(token)

    def _sid_string(self, sid):
        text = PTR()
        ok(self.adv.ConvertSidToStringSidW(sid, C.byref(text)))
        try:
            return C.wstring_at(text)
        finally:
            self.kernel.LocalFree(text)

    def _token_value(self, token, kind):
        size = U32()
        self.adv.GetTokenInformation(token, kind, None, 0, C.byref(size))
        if not 0 < size.value <= 65536:
            raise OSError("Contained token metadata unavailable")
        data = C.create_string_buffer(size.value)
        ok(self.adv.GetTokenInformation(token, kind, data, len(data), C.byref(size)))
        return data

    def verify_token(self, process):
        token = PTR()
        ok(self.adv.OpenProcessToken(process, 8, C.byref(token)))
        try:
            contained = U32.from_buffer(self._token_value(token, 29)).value
            capabilities = U32.from_buffer(self._token_value(token, 30)).value
            sid_buffer = self._token_value(token, 31)
            sid = self._sid_string(PTR.from_buffer(sid_buffer).value)
            integrity_buffer = self._token_value(token, 25)
            integrity = self._sid_string(PTR.from_buffer(integrity_buffer).value)
            if contained != 1 or capabilities != 0 or sid != self.sid_text or integrity != "S-1-16-4096":
                raise OSError("Contained token failed verification; process stays suspended")
            return {"appcontainer": True, "capability_count": 0, "integrity": "low",
                    "profile_sid_sha256": hashlib.sha256(sid.encode()).hexdigest()}
        finally:
            self.kernel.CloseHandle(token)

    def verify_no_loopback_exemption(self):
        """Read the effective exemption list without changing any host policy."""
        class SidAndAttributes(C.Structure):
            _fields_ = [("sid", PTR), ("attributes", U32)]
        firewall = C.WinDLL("FirewallAPI", use_last_error=True)
        bind(firewall, "NetworkIsolationGetAppContainerConfig", U32,
             [C.POINTER(U32), C.POINTER(PTR)])
        bind(self.kernel, "GetProcessHeap", PTR, [])
        bind(self.kernel, "HeapFree", BOOL, [PTR, U32, PTR])
        count, entries = U32(), PTR()
        result = firewall.NetworkIsolationGetAppContainerConfig(C.byref(count), C.byref(entries))
        if result:
            raise OSError(result, "Loopback exemption policy unavailable")
        try:
            if count.value > 65536:
                raise OSError("Loopback exemption policy exceeded bounds")
            values = C.cast(entries, C.POINTER(SidAndAttributes))
            if any(self._sid_string(values[i].sid) == self.sid_text for i in range(count.value)):
                raise OSError("Evaluation profile has a loopback exemption")
            return {"profile_loopback_exempt": False, "policy_queried": True}
        finally:
            if entries.value:
                for i in range(min(count.value, 65536)):
                    ok(self.kernel.HeapFree(self.kernel.GetProcessHeap(), 0, values[i].sid))
                ok(self.kernel.HeapFree(self.kernel.GetProcessHeap(), 0, entries))

    def _acl(self, handle, mode, permissions, inheritance):
        descriptor, dacl = PTR(), PTR()
        new_acl = PTR()
        result = self.adv.GetSecurityInfo(handle, 1, 4, None, None, C.byref(dacl), None, C.byref(descriptor))
        if result:
            raise OSError(result, "Evaluation ACL query failed")
        try:
            if not dacl.value:
                raise OSError("Null evaluation DACL is forbidden")
            ace = ExplicitAccess(permissions, mode, inheritance, Trustee(None, 0, 0, 0, self.sid))
            result = self.adv.SetEntriesInAclW(1, C.byref(ace), dacl, C.byref(new_acl))
            if result:
                raise OSError(result, "Evaluation ACL composition failed")
            result = self.adv.SetSecurityInfo(handle, 1, 4, None, None, new_acl, None)
            if result:
                raise OSError(result, "Evaluation ACL update failed")
        finally:
            if new_acl.value:
                self.kernel.LocalFree(new_acl)
            self.kernel.LocalFree(descriptor)

    def allow_read(self, path, *, directory=False):
        """Temporary RX for selected software tree, R for a selected data file.

        Caller must own/select these evaluation assets. No all-package ACLs or
        write permissions. Retained object handle is also used to revoke the
        unique profile SID, preserving other principals' ACL entries.
        """
        from .windows_native import NativeFiles
        path = Path(path).absolute()
        handle = self.kernel.CreateFileW(str(path), 0x60080, 3, None, 3, 0x02300000, None)
        if handle in {None, C.c_void_p(-1).value}:
            raise OSError(C.get_last_error(), "Selected evaluation asset ACL handle unavailable")
        try:
            info = NativeFiles().info(handle)
            if (not info.disk or info.reparse or info.offline or info.directory != directory
                    or not directory and info.links != 1):
                raise OSError("Selected evaluation asset is not an ordinary local object")
            self._acl(handle, 1, 0x1200A9 if directory else 0x120089, 3 if directory else 0)
            self.leases.append(handle)
        except BaseException:
            self.kernel.CloseHandle(handle)
            raise

    def launch(self, command, *, cwd, memory_mib=512):
        if self.closed or not command or not Path(command[0]).is_absolute():
            raise OSError("An explicit contained executable is required")
        if type(memory_mib) is not int or not 128 <= memory_mib <= 32768:
            raise OSError("Invalid evaluation memory ceiling")
        process = ContainedProcess(self, command, cwd, memory_mib)
        self.processes.append(process)
        return process

    def create_private_ipc(self, path):
        """Create an owned disposable directory with a protected DACL/low label.

        Caller deletes this exact directory after container cleanup. Never
        accepts an existing directory or changes a document/software label.
        """
        path = Path(path).absolute()
        bind(self.kernel, "CreateDirectoryW", BOOL, [WSTR, C.POINTER(SecurityAttributes)])
        token, descriptor = PTR(), PTR()
        ok(self.adv.OpenProcessToken(PTR(-1), 8, C.byref(token)))
        try:
            user = self._sid_string(PTR.from_buffer(self._token_value(token, 1)).value)
            sddl = (f"D:P(A;OICI;FA;;;{user})(A;OICI;FA;;;SY)"
                    f"(A;OICI;0x1301BF;;;{self.sid_text})S:(ML;OICI;NW;;;LW)")
            ok(self.adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, C.byref(descriptor), None))
            sa = SecurityAttributes(C.sizeof(SecurityAttributes), descriptor, 0)
            ok(self.kernel.CreateDirectoryW(str(path), C.byref(sa)))
        finally:
            if descriptor.value:
                self.kernel.LocalFree(descriptor)
            self.kernel.CloseHandle(token)
        self.allow_read(path, directory=True)  # Retained identity/cleanup handle.

    def close(self):
        if self.closed:
            return
        errors = []
        for process in reversed(self.processes):
            try:
                process.close()
            except Exception as error:
                errors.append(error)
        for handle in reversed(self.leases):
            try:
                self._acl(handle, 4, 0, 0)  # Revoke only the newly created unique SID.
            except Exception as error:
                errors.append(error)
            finally:
                self.kernel.CloseHandle(handle)
        result = self.userenv.DeleteAppContainerProfile(self.name)
        for handle, closer in ((self.desktop, getattr(getattr(self, "ui", None), "CloseDesktop", None)),
                               (self.station, getattr(getattr(self, "ui", None), "CloseWindowStation", None))):
            if handle and closer is not None and not closer(handle):
                errors.append(OSError("Private UI-object cleanup failed"))
        self.adv.FreeSid(self.sid)
        self.closed = True
        if result != 0 or errors:
            raise OSError("Temporary container cleanup was incomplete")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class ContainedProcess:
    def __init__(self, container, command, cwd, memory_mib):
        self.container, self.kernel = container, container.kernel
        self.info, self.job = ProcessInfo(), None
        self.parent_handles, children = [], []
        self.closed = False
        attributes = None
        attributes_initialized = False
        try:
            sa = SecurityAttributes(C.sizeof(SecurityAttributes), None, 1)
            for reverse in (True, False, False):
                read, write = PTR(), PTR()
                ok(self.kernel.CreatePipe(C.byref(read), C.byref(write), C.byref(sa), 0))
                parent, child = (write.value, read.value) if reverse else (read.value, write.value)
                self.parent_handles.append(parent)
                children.append(child)
                ok(self.kernel.SetHandleInformation(parent, 1, 0))
            self.job = ok(self.kernel.CreateJobObjectW(None, None))
            limits = ExtendedLimits()
            limits.basic.flags = 0x2000 | 0x8 | 0x100  # Kill on close, active-process and process-memory limits.
            limits.basic.active_processes = 1
            limits.process_memory = memory_mib * 1024 * 1024
            ok(self.kernel.SetInformationJobObject(self.job, 9, C.byref(limits), C.sizeof(limits)))
            size = SIZE()
            self.kernel.InitializeProcThreadAttributeList(None, 3, 0, C.byref(size))
            if C.get_last_error() != 122 or not 0 < size.value < 65536:
                raise OSError("Process attribute allocation failed")
            attributes = C.create_string_buffer(size.value)
            ok(self.kernel.InitializeProcThreadAttributeList(attributes, 3, 0, C.byref(size)))
            attributes_initialized = True
            security = SecurityCapabilities(container.sid, None, 0, 0)
            inherited = (PTR * 3)(*children)
            child_policy = U32(1)
            for kind, data in ((0x20009, security), (0x20002, inherited), (0x2000E, child_policy)):
                ok(self.kernel.UpdateProcThreadAttribute(attributes, 0, kind, C.byref(data), C.sizeof(data), None, None))
            startup = StartupInfoEx()
            startup.startup.cb = C.sizeof(StartupInfoEx)
            startup.startup.flags = 0x101  # Explicit standard handles; hidden window.
            startup.startup.desktop = container.desktop_name
            startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = children
            startup.attributes = C.cast(attributes, PTR)
            commandline = subprocess.list2cmdline([str(c) for c in command])
            if len(commandline) >= 32760:
                raise OSError("Contained command exceeds Windows limit")
            commandbuffer = C.create_unicode_buffer(commandline)
            env = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR") if key in os.environ}
            # Windows requires these inputs to construct its redirected
            # AppContainer environment. No proxy, credential or tracing env.
            for key in ("LOCALAPPDATA", "TEMP", "TMP", "USERPROFILE", "APPDATA", "SYSTEMDRIVE"):
                if key not in os.environ:
                    raise OSError("Required Windows container environment unavailable")
                env[key] = os.environ[key]
            env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", CUDA_VISIBLE_DEVICES="0")
            envbuffer = C.create_unicode_buffer("\0".join(f"{key}={value}" for key, value in sorted(env.items())) + "\0\0")
            # DETACHED_PROCESS avoids lowbox console initialization (which failed
            # with CREATE_NO_WINDOW). Private pipes supply all standard IO.
            ok(self.kernel.CreateProcessW(str(command[0]), commandbuffer, None, None, True,
                                          0x8 | 0x80000 | 0x400 | 4, envbuffer, str(cwd),
                                          C.byref(startup), C.byref(self.info)))
            ok(self.kernel.AssignProcessToJobObject(self.job, self.info.process))
            self.token_evidence = container.verify_token(self.info.process)
            self.token_evidence.update(container.verify_no_loopback_exemption())
            if self.kernel.ResumeThread(self.info.thread) == 0xffffffff:
                raise OSError(C.get_last_error(), "Contained thread resume failed")
        except BaseException:
            self.close()
            raise
        finally:
            for handle in children:
                self.kernel.CloseHandle(handle)
            if attributes_initialized:
                self.kernel.DeleteProcThreadAttributeList(attributes)

    def exchange(self, initial, handler, *, timeout=150, max_frames=64, limit=256*1024):
        """Bounded evaluation RPC over this process's private inherited pipes.

        Every frame is bound to a fresh session and strictly increasing number.
        The trusted handler must expose its own fixed data-only registry.
        """
        from .model import strict_json, json_bytes
        if not 0 < timeout <= 300 or not 1 <= max_frames <= 128 or not 1024 <= limit <= 2*1024*1024:
            raise OSError('Invalid evaluation IPC bounds')
        session = secrets.token_hex(16)
        result, errors, stderr = [], [], bytearray()

        def write(frame):
            data = json_bytes(frame) + b'\n'
            if len(data) > limit:
                raise OSError('Evaluation IPC response exceeds bounds')
            offset = 0
            while offset < len(data):
                chunk = data[offset:offset+65536]
                buffer, count = C.create_string_buffer(chunk), U32()
                ok(self.kernel.WriteFile(self.parent_handles[0], buffer, len(chunk), C.byref(count), None))
                if not count.value:
                    raise OSError('Evaluation IPC write made no progress')
                offset += count.value

        def protocol():
            try:
                write({'session': session, 'sequence': 0, 'kind': 'initial', 'payload': initial})
                pending = bytearray()
                sequence = 1
                while sequence <= max_frames:
                    while b'\n' not in pending:
                        buffer, count = C.create_string_buffer(8192), U32()
                        ok(self.kernel.ReadFile(self.parent_handles[1], buffer, len(buffer), C.byref(count), None))
                        if not count.value:
                            raise OSError('Evaluation IPC ended before its result')
                        pending.extend(buffer.raw[:count.value])
                        if len(pending) > limit:
                            raise OSError('Evaluation IPC request exceeds bounds')
                    line, _, tail = pending.partition(b'\n')
                    pending = bytearray(tail)
                    frame = strict_json(bytes(line))
                    if (not isinstance(frame, dict) or set(frame) != {'session', 'sequence', 'kind', 'payload'}
                            or frame['session'] != session or type(frame['sequence']) is not int
                            or frame['sequence'] != sequence):
                        raise OSError('Malformed or replayed evaluation IPC frame')
                    if frame['kind'] == 'result':
                        if pending:
                            raise OSError('Unexpected evaluation IPC trailing data')
                        result.append(frame['payload'])
                        return
                    if frame['kind'] != 'request':
                        raise OSError('Unregistered evaluation IPC frame kind')
                    response = handler(frame['payload'])
                    write({'session': session, 'sequence': sequence, 'kind': 'response', 'payload': response})
                    sequence += 1
                raise OSError('Evaluation IPC frame budget exhausted')
            except BaseException as error:
                errors.append(error)
                self.kernel.TerminateJobObject(self.job, 125)
            finally:
                self.kernel.CloseHandle(self.parent_handles[0])
                self.parent_handles[0] = None

        def diagnostics():
            try:
                while True:
                    buffer, count = C.create_string_buffer(8192), U32()
                    if not self.kernel.ReadFile(self.parent_handles[2], buffer, len(buffer), C.byref(count), None):
                        if C.get_last_error() == 109:
                            return
                        raise OSError('Evaluation diagnostic pipe failed')
                    if not count.value:
                        return
                    stderr.extend(buffer.raw[:count.value])
                    if len(stderr) > 128*1024:
                        raise OSError('Evaluation diagnostic output exceeds bounds')
            except BaseException as error:
                errors.append(error)
                self.kernel.TerminateJobObject(self.job, 125)

        threads = [threading.Thread(target=target, daemon=True) for target in (protocol, diagnostics)]
        for thread in threads:
            thread.start()
        status = self.kernel.WaitForSingleObject(self.info.process, int(timeout*1000))
        if status != 0:
            self.kernel.TerminateJobObject(self.job, 124)
            self.kernel.WaitForSingleObject(self.info.process, 10000)
            errors.append(TimeoutError('Evaluation IPC deadline exceeded'))
        for thread in threads:
            thread.join(timeout=15)
            if thread.is_alive():
                errors.append(OSError('Evaluation IPC thread did not close'))
        code = U32()
        ok(self.kernel.GetExitCodeProcess(self.info.process, C.byref(code)))
        if errors:
            raise errors[0]
        if code.value != 0 or len(result) != 1:
            raise OSError('Evaluation worker failed or omitted its result')
        return result[0], bytes(stderr)

    def communicate(self, data=b"", *, timeout=60, limit=1024*1024):
        if len(data) > 2*1024*1024 or not 0 < timeout <= 300 or not 1024 <= limit <= 4*1024*1024:
            raise OSError("Invalid contained IPC bounds")
        output, errors = [bytearray(), bytearray()], []

        def read(index):
            try:
                while True:
                    buffer, count = C.create_string_buffer(65536), U32()
                    value = self.kernel.ReadFile(self.parent_handles[index+1], buffer, len(buffer), C.byref(count), None)
                    if not value:
                        if C.get_last_error() == 109:
                            break
                        raise OSError(C.get_last_error(), "Contained pipe read failed")
                    if not count.value:
                        break
                    if len(output[index]) + count.value > limit:
                        raise OSError("Contained output exceeded its limit")
                    output[index].extend(buffer.raw[:count.value])
            except Exception as error:
                errors.append(error)
                self.kernel.TerminateJobObject(self.job, 125)

        def write():
            try:
                offset = 0
                while offset < len(data):
                    chunk = data[offset:offset+65536]
                    buffer, count = C.create_string_buffer(chunk), U32()
                    ok(self.kernel.WriteFile(self.parent_handles[0], buffer, len(chunk), C.byref(count), None))
                    if not count.value:
                        raise OSError("Contained input write made no progress")
                    offset += count.value
            except Exception as error:
                errors.append(error)
                self.kernel.TerminateJobObject(self.job, 125)
            finally:
                self.kernel.CloseHandle(self.parent_handles[0])
                self.parent_handles[0] = None

        threads = [threading.Thread(target=read, args=(i,), daemon=True) for i in (0, 1)]
        threads.append(threading.Thread(target=write, daemon=True))
        for thread in threads:
            thread.start()
        status = self.kernel.WaitForSingleObject(self.info.process, int(timeout*1000))
        if status != 0:
            self.kernel.TerminateJobObject(self.job, 124)
            self.kernel.WaitForSingleObject(self.info.process, 10000)
            errors.append(TimeoutError("Contained process deadline exceeded"))
        for thread in threads:
            thread.join(timeout=10)
            if thread.is_alive():
                errors.append(OSError("Contained pipe did not close"))
        code = U32()
        ok(self.kernel.GetExitCodeProcess(self.info.process, C.byref(code)))
        if errors:
            raise errors[0]
        return code.value, bytes(output[0]), bytes(output[1])

    def close(self):
        if self.closed:
            return
        if self.info.process:
            # The process can still be suspended if token/job validation failed.
            if self.job:
                self.kernel.TerminateJobObject(self.job, 126)
            self.kernel.TerminateProcess(self.info.process, 126)
            self.kernel.WaitForSingleObject(self.info.process, 10000)
        for handle in [*self.parent_handles, self.info.thread, self.info.process, self.job]:
            if handle:
                self.kernel.CloseHandle(handle)
        self.closed = True
