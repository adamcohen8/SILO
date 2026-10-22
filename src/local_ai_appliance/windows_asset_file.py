"""Held Windows asset reads that exclude writers/deleters while hashing.

Python's Windows st_ctime may be file creation time, not NTFS ChangeTime.
Use native held-handle metadata as well as the existing path/descriptor checks.
No permissive sharing, ordinary Python-open, or timestamp-only fallback.
"""
from contextlib import contextmanager
import ctypes as C
from functools import lru_cache
import os
from pathlib import Path

from .windows_container import BOOL, PTR, U32, WSTR, bind, native_error
from .windows_native import FileInformation


class FileBasicInfo(C.Structure):
    _fields_ = [('creation', C.c_int64), ('access', C.c_int64),
                ('write', C.c_int64), ('change', C.c_int64), ('attributes', U32)]


@lru_cache(maxsize=1)
def _kernel():
    kernel = C.WinDLL('kernel32', use_last_error=True)
    bind(kernel, 'CreateFileW', PTR, [WSTR, U32, U32, PTR, U32, U32, PTR])
    bind(kernel, 'CloseHandle', BOOL, [PTR])
    bind(kernel, 'GetFileInformationByHandle', BOOL, [PTR, C.POINTER(FileInformation)])
    bind(kernel, 'GetFileInformationByHandleEx', BOOL, [PTR, U32, PTR, U32])
    bind(kernel, 'GetFileType', U32, [PTR])
    return kernel


def snapshot(kernel, handle):
    info, basic = FileInformation(), FileBasicInfo()
    if not kernel.GetFileInformationByHandle(handle, C.byref(info)):
        raise native_error('Software held-handle identity query failed')
    if not kernel.GetFileInformationByHandleEx(handle, 0, C.byref(basic), C.sizeof(basic)):
        raise native_error('Software held-handle ChangeTime query failed')
    # Both observations must describe an ordinary, single-link disk file.
    if (kernel.GetFileType(handle) != 1 or info.Links != 1
            or (info.Attributes | basic.attributes) & 0x441410):
        raise RuntimeError('Software storage contains an unsupported native object.')
    return (info.VolumeSerial, info.IndexHigh, info.IndexLow,
            info.SizeHigh, info.SizeLow, info.Links, basic.creation,
            basic.write, basic.change, info.Attributes, basic.attributes)


@contextmanager
def locked_stream(path):
    import msvcrt  # Never imported or used on a non-Windows host.
    kernel = _kernel()
    # GENERIC_READ; FILE_SHARE_READ only; OPEN_EXISTING; sequential, no-reparse,
    # no-recall. A pre-existing writer makes this fail; no sharing-mode retry.
    handle = kernel.CreateFileW(str(Path(path).absolute()), 0x80000000, 1, None,
                                3, 0x08300000, None)
    if handle in (None, PTR(-1).value):
        raise native_error('Software verification read lease unavailable')
    transferred = False
    try:
        snapshot(kernel, handle)  # Validate before any content read.
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        transferred = True  # CRT now owns this exact native handle.
        try:
            stream = os.fdopen(fd, 'rb', buffering=0)
        except BaseException:
            os.close(fd)
            raise
        with stream:
            yield stream, lambda: snapshot(kernel, handle)
    finally:
        if not transferred:
            kernel.CloseHandle(handle)
