"""Private staging storage. Windows APIs are a synthetic-validation candidate."""

from contextlib import contextmanager
import ctypes as C
import hashlib
import hmac
import os
import re
import secrets
import stat

from .bundle import BundleError, _root
from .windows_folders import parts, selected_path
from .windows_native import NativeFiles, HANDLE, U32, I32


def windows_acl(native, handle):
    """Require owner/current user, protected DACL, and exactly user/SYSTEM/admins.

    This protects staging from other ordinary users; it does not sandbox a
    same-user compromised worker. All APIs require native target validation.
    """
    adv = C.WinDLL('advapi32', use_last_error=True)
    NativeFiles._bind(adv, 'GetSecurityInfo', U32, [HANDLE, U32, U32] + [C.POINTER(HANDLE)] * 5)
    NativeFiles._bind(adv, 'ConvertSecurityDescriptorToStringSecurityDescriptorW', I32,
                     [HANDLE, U32, U32, C.POINTER(HANDLE), C.POINTER(U32)])
    NativeFiles._bind(adv, 'GetSecurityDescriptorControl', I32, [HANDLE, C.POINTER(C.c_uint16), C.POINTER(U32)])
    NativeFiles._bind(adv, 'OpenProcessToken', I32, [HANDLE, U32, C.POINTER(HANDLE)])
    NativeFiles._bind(adv, 'GetTokenInformation', I32, [HANDLE, U32, HANDLE, U32, C.POINTER(U32)])
    NativeFiles._bind(adv, 'ConvertSidToStringSidW', I32, [HANDLE, C.POINTER(HANDLE)])
    NativeFiles._bind(native.kernel, 'GetCurrentProcess', HANDLE, [])
    NativeFiles._bind(native.kernel, 'LocalFree', HANDLE, [HANDLE])
    token, descriptor, text, sid_text = HANDLE(), HANDLE(), HANDLE(), HANDLE()
    try:
        native._ok(adv.OpenProcessToken(native.kernel.GetCurrentProcess(), 8, C.byref(token)))
        size = U32()
        adv.GetTokenInformation(token, 1, None, 0, C.byref(size))
        if not 0 < size.value < 65536: raise BundleError('Token metadata is unavailable')
        buffer = C.create_string_buffer(size.value)
        native._ok(adv.GetTokenInformation(token, 1, buffer, len(buffer), C.byref(size)))
        sid = HANDLE.from_buffer(buffer).value
        native._ok(adv.ConvertSidToStringSidW(sid, C.byref(sid_text)))
        current = C.wstring_at(sid_text)
        owner, group, dacl, sacl = HANDLE(), HANDLE(), HANDLE(), HANDLE()
        if adv.GetSecurityInfo(handle, 1, 5, C.byref(owner), C.byref(group), C.byref(dacl),
                               C.byref(sacl), C.byref(descriptor)) != 0:
            raise BundleError('Storage ACL is unavailable')
        control, revision = C.c_uint16(), U32()
        native._ok(adv.GetSecurityDescriptorControl(descriptor, C.byref(control), C.byref(revision)))
        native._ok(adv.ConvertSecurityDescriptorToStringSecurityDescriptorW(descriptor, 1, 5, C.byref(text), None))
        sddl = C.wstring_at(text)
        if not control.value & 0x1000 or not sddl.startswith('O:' + current + 'D:P'):
            raise BundleError('Storage must have a protected DACL owned by the current user')
        dacl_text = sddl[len('O:' + current + 'D:P'):]
        aces = re.findall(r'\(A;OICI;FA;;;([^()]+)\)', dacl_text)
        if (len(aces) != 3 or set(aces) != {current, 'SY', 'BA'} or
                ''.join(f'(A;OICI;FA;;;{sid})' for sid in aces) != dacl_text):
            raise BundleError('Storage ACL must allow exactly current user, SYSTEM, and Administrators')
    finally:
        for pointer in (text, sid_text, descriptor):
            if pointer.value: native.kernel.LocalFree(pointer)
        if token.value: native.close(token)


class Store:
    def __init__(self, path, *, windows_validation=False):
        self.native, self.handles = None, []
        try:
            if os.name == 'nt':
                if not windows_validation: raise BundleError('Windows staging is an explicit validation candidate only')
                self.native = NativeFiles()
                drive, components = selected_path(path)
                self.handles.append(self.native.open_drive(drive))
                self.device = self.native.info(self.handles[-1]).volume
                if self.native.filesystem(self.handles[-1]).upper() != 'NTFS': raise BundleError('Local NTFS is required')
                for index, name in enumerate(components):
                    self.handles.append(self.native.open_child(self.handles[-1], name, directory=True,
                                                              security=index == len(components) - 1))
                    self.check(self.handles[-1], True)
                windows_acl(self.native, self.handles[-1])
                self.root = self.handles[-1]
            else:
                self.root = _root(path); self.handles.append(self.root)
                info = os.fstat(self.root); self.device = info.st_dev
                if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
                    raise BundleError('Use a current-user-owned private directory with mode 0700')
        except BaseException:
            self.close(); raise

    def check(self, handle, directory):
        info = self.native.info(handle)
        if (info.volume != self.device or not info.disk or info.directory != directory or
                info.reparse or info.offline or (not directory and info.links != 1)):
            raise BundleError('Unsupported staging object')
        return info

    @contextmanager
    def directory(self, path=''):
        opened, parent = [], self.root
        try:
            for name in parts(path) if path else []:
                if self.native:
                    parent = self.native.open_child(parent, name, directory=True); opened.append(parent)
                    self.check(parent, True)
                else:
                    parent = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                    opened.append(parent)
                    info = os.fstat(parent)
                    if info.st_dev != self.device or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
                        raise BundleError('Staging directories must remain private and local')
            yield parent
        finally:
            for handle in reversed(opened):
                if self.native: self.native.close(handle)
                else: os.close(handle)

    def mkdir(self, path):
        components = parts(path)
        with self.directory('/'.join(components[:-1])) as parent:
            if self.native:
                handle = self.native.open_child(parent, components[-1], directory=True, create=True)
                try: self.check(handle, True)
                finally: self.native.close(handle)
            else: os.mkdir(components[-1], mode=0o700, dir_fd=parent)

    def names(self, path=''):
        with self.directory(path) as parent:
            values = list(self.native.names(parent)) if self.native else os.listdir(parent)
            values = [name for name in values if name not in {'.', '..'}]
            if len(values) > 8192: raise BundleError('Staging inventory is oversized')
            for name in values: parts(name)
            return sorted(values)

    def read(self, path, limit=1024 * 1024):
        components = parts(path)
        with self.directory('/'.join(components[:-1])) as parent:
            if self.native:
                metadata = self.native.open_child(parent, components[-1], directory=False)
                handle = None
                try:
                    info = self.check(metadata, False)
                    if info.size > limit: raise BundleError('Staging metadata is oversized')
                    handle = self.native.open_read(metadata)
                    if self.check(handle, False) != info: raise BundleError('Staging identity changed')
                    data = self.native.read(handle, limit)
                finally:
                    if handle is not None: self.native.close(handle)
                    self.native.close(metadata)
            else:
                fd = os.open(components[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                with os.fdopen(fd, 'rb') as file:
                    info = os.fstat(file.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_dev != self.device:
                        raise BundleError('Unsupported staging file')
                    data = file.read(limit + 1)
            if len(data) > limit: raise BundleError('Staging metadata is oversized')
            return data

    def write(self, path, producer):
        components = parts(path); temporary = '.stage-' + secrets.token_hex(16)
        with self.directory('/'.join(components[:-1])) as parent:
            published = False
            if self.native:
                handle = self.native.open_child(parent, temporary, directory=False, create=True)
                try:
                    self.check(handle, False)
                    producer(lambda block: self.native.write(handle, block))
                    self.native.publish(handle, parent, components[-1]); published = True
                finally:
                    try:
                        if not published: self.native.discard(handle)
                    finally: self.native.close(handle)
            else:
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
                try:
                    with os.fdopen(fd, 'wb') as file:
                        producer(file.write); file.flush(); os.fsync(file.fileno())
                    os.link(temporary, components[-1], src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                    published = True
                    os.fsync(parent)
                finally: os.unlink(temporary, dir_fd=parent)

    def verify_file(self, path, size, expected_hash):
        components = parts(path)
        with self.directory('/'.join(components[:-1])) as parent:
            metadata, handle = None, None
            try:
                if self.native:
                    metadata = self.native.open_child(parent, components[-1], directory=False)
                    before = self.check(metadata, False)
                    if before.size != size: raise BundleError('Rollback refused: staged payload size changed')
                    handle = self.native.open_read(metadata)
                    if self.check(handle, False) != before: raise BundleError('Staged identity changed')
                    read = lambda count: self.native.read_chunk(handle, count)
                else:
                    handle = os.open(components[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                    before = os.fstat(handle)
                    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or
                            before.st_dev != self.device or before.st_size != size):
                        raise BundleError('Rollback refused: staged payload identity/size changed')
                    read = lambda count: os.read(handle, count)
                digest, count = hashlib.sha256(), 0
                while block := read(min(1024 * 1024, size + 1 - count)):
                    count += len(block)
                    if count > size: raise BundleError('Rollback refused: staged payload grew')
                    digest.update(block)
                if count != size or not hmac.compare_digest(digest.hexdigest(), expected_hash):
                    raise BundleError('Rollback refused: staged payload changed')
                after = self.check(handle, False) if self.native else os.fstat(handle)
                if self.native:
                    changed = after != before
                else:
                    fingerprint = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_nlink,
                                                info.st_mtime_ns, info.st_ctime_ns)
                    changed = fingerprint(after) != fingerprint(before)
                if changed: raise BundleError('Rollback refused: staged payload changed while checked')
            finally:
                if handle is not None:
                    if self.native: self.native.close(handle)
                    else: os.close(handle)
                if metadata is not None: self.native.close(metadata)

    @contextmanager
    def lock(self, name='.installer-lock'):
        # Exclusive handle/file lock. A crash leaves a marker: do not steal it or
        # silently repair; inspect recovery state before removing it manually.
        if name not in {'.installer-lock','.schedule-runner-lock'}:
            raise BundleError('Unknown private storage lock')
        if self.native:
            handle = self.native.open_child(self.root, name, directory=False, create=True)
            try: yield
            finally:
                try: self.native.discard(handle)
                finally: self.native.close(handle)
        else:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=self.root)
            try: yield
            finally:
                os.close(fd); os.unlink(name, dir_fd=self.root)

    def remove(self, path, *, directory=False):
        components = parts(path)
        with self.directory('/'.join(components[:-1])) as parent:
            if self.native:
                handle = self.native.open_child(parent, components[-1], directory=directory, delete=True)
                try:
                    self.check(handle, directory); self.native.discard(handle)
                finally: self.native.close(handle)
            elif directory: os.rmdir(components[-1], dir_fd=parent)
            else: os.unlink(components[-1], dir_fd=parent)

    def close(self):
        for handle in reversed(self.handles):
            if self.native: self.native.close(handle)
            else: os.close(handle)
        self.handles = []

    def __enter__(self): return self
    def __exit__(self, *_): self.close()
