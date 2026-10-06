"""64-bit Windows native file primitives for the unqualified broker candidate.

No DLL is loaded when imported on another platform. All opens below a granted
root are relative to an existing directory handle and refuse reparse traversal.
"""

import ctypes as C
from dataclasses import dataclass
import os
import struct


U32, I32, U16, U8, HANDLE = C.c_uint32, C.c_int32, C.c_uint16, C.c_uint8, C.c_void_p


class UnicodeString(C.Structure):
    _fields_ = [("Length", U16), ("MaximumLength", U16), ("Buffer", HANDLE)]


class ObjectAttributes(C.Structure):
    _fields_ = [("Length", U32), ("RootDirectory", HANDLE),
                ("ObjectName", C.POINTER(UnicodeString)), ("Attributes", U32),
                ("SecurityDescriptor", HANDLE), ("SecurityQualityOfService", HANDLE)]


class StatusValue(C.Union):
    _fields_ = [("Status", I32), ("Pointer", HANDLE)]


class IoStatus(C.Structure):
    _fields_ = [("Value", StatusValue), ("Information", C.c_size_t)]


class FileTime(C.Structure):
    _fields_ = [("Low", U32), ("High", U32)]


class FileInformation(C.Structure):
    _fields_ = [("Attributes", U32), ("Creation", FileTime), ("Access", FileTime),
                ("Write", FileTime), ("VolumeSerial", U32), ("SizeHigh", U32),
                ("SizeLow", U32), ("Links", U32), ("IndexHigh", U32), ("IndexLow", U32)]


class RenameInformation(C.Structure):
    # DWORD Flags shares the union storage with BOOLEAN ReplaceIfExists.
    _fields_ = [("Flags", U32), ("RootDirectory", HANDLE), ("FileNameLength", U32),
                ("FileName", U16 * 1)]


@dataclass(frozen=True)
class Info:
    volume: int
    index: int
    size: int
    links: int
    directory: bool
    reparse: bool
    disk: bool
    offline: bool = False


def directory_names(data: bytes):
    """Parse bounded FILE_NAMES_INFORMATION records from NtQueryDirectoryFile."""
    offset = 0
    while True:
        if len(data) - offset < 12:
            raise OSError("Invalid native directory record")
        following, _, length = struct.unpack_from("<III", data, offset)
        if length % 2 or not 0 < length <= 510 or offset + 12 + length > len(data):
            raise OSError("Invalid native directory name")
        yield data[offset + 12:offset + 12 + length].decode("utf-16-le", errors="strict")
        if following == 0:
            return
        if following < 12 + length or offset + following >= len(data):
            raise OSError("Invalid native directory offset")
        offset += following


class NativeFiles:
    def __init__(self):
        if os.name != "nt" or C.sizeof(HANDLE) != 8:
            raise RuntimeError("The Windows candidate requires a native 64-bit Windows Python")
        self.kernel = C.WinDLL("kernel32", use_last_error=True)
        self.nt = C.WinDLL("ntdll")
        self._bind(self.kernel, "CreateFileW", HANDLE,
                   [C.c_wchar_p, U32, U32, HANDLE, U32, U32, HANDLE])
        self._bind(self.kernel, "CloseHandle", I32, [HANDLE])
        self._bind(self.kernel, "ReOpenFile", HANDLE, [HANDLE, U32, U32, U32])
        self._bind(self.kernel, "GetFileInformationByHandle", I32, [HANDLE, C.POINTER(FileInformation)])
        self._bind(self.kernel, "GetFileType", U32, [HANDLE])
        self._bind(self.kernel, "GetFinalPathNameByHandleW", U32, [HANDLE, C.c_wchar_p, U32, U32])
        self._bind(self.kernel, "GetDriveTypeW", U32, [C.c_wchar_p])
        self._bind(self.kernel, "GetVolumeInformationByHandleW", I32,
                   [HANDLE, C.c_wchar_p, U32, C.POINTER(U32), C.POINTER(U32), C.POINTER(U32), C.c_wchar_p, U32])
        self._bind(self.kernel, "ReadFile", I32, [HANDLE, HANDLE, U32, C.POINTER(U32), HANDLE])
        self._bind(self.kernel, "WriteFile", I32, [HANDLE, HANDLE, U32, C.POINTER(U32), HANDLE])
        self._bind(self.kernel, "FlushFileBuffers", I32, [HANDLE])
        self._bind(self.kernel, "SetFileInformationByHandle", I32, [HANDLE, U32, HANDLE, U32])
        self._bind(self.nt, "NtCreateFile", I32, [C.POINTER(HANDLE), U32, C.POINTER(ObjectAttributes),
                   C.POINTER(IoStatus), HANDLE, U32, U32, U32, U32, HANDLE, U32])
        self._bind(self.nt, "NtQueryDirectoryFile", I32, [HANDLE, HANDLE, HANDLE, HANDLE,
                   C.POINTER(IoStatus), HANDLE, U32, U32, U8, HANDLE, U8])

    @staticmethod
    def _bind(dll, name, result, args):
        function = getattr(dll, name)
        function.restype, function.argtypes = result, args

    @staticmethod
    def _ok(result):
        if not result:
            raise OSError(C.get_last_error(), "Windows file operation failed")

    def close(self, handle):
        self._ok(self.kernel.CloseHandle(handle))

    def open_drive(self, drive):
        if self.kernel.GetDriveTypeW(drive) != 3:  # DRIVE_FIXED only.
            raise OSError("Only fixed local disks are supported by this candidate")
        handle = self.kernel.CreateFileW(drive, 0x1000A1, 3, None, 3, 0x02300000, None)
        if handle in {None, C.c_void_p(-1).value}:
            raise OSError(C.get_last_error(), "Drive directory open failed")
        return handle

    def open_child(self, parent, name, *, directory=None, read=False, create=False, delete=False, security=False):
        encoded = name.encode("utf-16-le")
        if not encoded or len(encoded) > 510 or "\\" in name or "/" in name or ":" in name:
            raise OSError("A single native filename component is required")
        buffer = C.create_string_buffer(encoded + b"\0\0")
        string = UnicodeString(len(encoded), len(encoded) + 2, C.cast(buffer, HANDLE))
        attributes = ObjectAttributes(C.sizeof(ObjectAttributes), parent, C.pointer(string),
                                      0x1040, None, None)  # CASE_INSENSITIVE | DONT_REPARSE
        status, handle = IoStatus(), HANDLE()
        access = 0x100080  # SYNCHRONIZE | FILE_READ_ATTRIBUTES
        if security:
            access |= 0x20000  # READ_CONTROL for held-handle ACL inspection.
        if directory is True or read:
            access |= 1  # FILE_LIST_DIRECTORY or FILE_READ_DATA
        if directory is True:
            access |= 0x20  # FILE_TRAVERSE
        if create:
            access |= 0x10002  # DELETE | FILE_WRITE_DATA
        if delete:
            access |= 0x10000
        options = 0x00600020  # OPEN_REPARSE_POINT | OPEN_NO_RECALL | SYNCHRONOUS_IO_NONALERT
        if directory is True:
            options |= 1  # FILE_DIRECTORY_FILE
        elif directory is False:
            options |= 0x40  # FILE_NON_DIRECTORY_FILE
        # Retained directories deny deletion/rename; reads also deny writers.
        share = 0 if create or delete else (1 if read else 3)
        result = self.nt.NtCreateFile(C.byref(handle), access, C.byref(attributes), C.byref(status),
                                     None, 0x80, share, 2 if create else 1, options, None, 0)
        if result < 0:
            if (result & 0xFFFFFFFF) in {0xC0000034, 0xC000003A}:  # NAME/PATH_NOT_FOUND
                raise FileNotFoundError("Native file is unavailable")
            raise OSError("Native relative open failed")
        if not handle.value:
            raise OSError("Native relative open returned no handle")
        return handle.value

    def open_read(self, metadata_handle):
        # Reopen the checked object while its no-delete metadata handle remains
        # held. Request no recall and deny writers/deletion for the data handle.
        handle = self.kernel.ReOpenFile(metadata_handle, 0x100081, 1, 0x00300000)
        if handle in {None, C.c_void_p(-1).value}:
            raise OSError(C.get_last_error(), "Checked file reopen failed")
        return handle

    def info(self, handle):
        info = FileInformation()
        self._ok(self.kernel.GetFileInformationByHandle(handle, C.byref(info)))
        return Info(info.VolumeSerial, (info.IndexHigh << 32) | info.IndexLow,
                    (info.SizeHigh << 32) | info.SizeLow, info.Links,
                    bool(info.Attributes & 0x10), bool(info.Attributes & 0x400),
                    self.kernel.GetFileType(handle) == 1,
                    bool(info.Attributes & (0x1000 | 0x40000 | 0x400000)))

    def filesystem(self, handle):
        name = C.create_unicode_buffer(64)
        self._ok(self.kernel.GetVolumeInformationByHandleW(handle, None, 0, None, None, None, name, 64))
        return name.value

    def canonical(self, handle):
        buffer = C.create_unicode_buffer(32768)
        length = self.kernel.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 1)  # VOLUME_NAME_GUID
        if not 0 < length < len(buffer):
            raise OSError("Canonical volume path is unavailable")
        return buffer.value

    def read(self, handle, limit):
        data = bytearray()
        while len(data) <= limit:
            wanted = min(65536, limit + 1 - len(data))
            buffer, count = C.create_string_buffer(wanted), U32()
            self._ok(self.kernel.ReadFile(handle, buffer, wanted, C.byref(count), None))
            if count.value > wanted:
                raise OSError("Invalid native read size")
            if not count.value:
                break
            data.extend(buffer.raw[:count.value])
        return bytes(data)

    def read_chunk(self, handle, wanted):
        if not 1 <= wanted <= 1024 * 1024:
            raise OSError('Invalid native streaming read size')
        buffer, count = C.create_string_buffer(wanted), U32()
        self._ok(self.kernel.ReadFile(handle, buffer, wanted, C.byref(count), None))
        if count.value > wanted: raise OSError('Invalid native read size')
        return buffer.raw[:count.value]

    def write(self, handle, data):
        offset = 0
        while offset < len(data):
            chunk = data[offset:offset + 65536]
            buffer, count = C.create_string_buffer(chunk), U32()
            self._ok(self.kernel.WriteFile(handle, buffer, len(chunk), C.byref(count), None))
            if not 0 < count.value <= len(chunk):
                raise OSError("Invalid native write size")
            offset += count.value
        self._ok(self.kernel.FlushFileBuffers(handle))

    def publish(self, handle, parent, name):
        encoded = name.encode("utf-16-le")
        size = RenameInformation.FileName.offset + len(encoded) + 2
        buffer = C.create_string_buffer(max(size, C.sizeof(RenameInformation)))
        info = RenameInformation.from_buffer(buffer)
        info.Flags, info.RootDirectory, info.FileNameLength = 0, parent, len(encoded)
        C.memmove(C.addressof(buffer) + RenameInformation.FileName.offset, encoded, len(encoded))
        # FileRenameInfo; ReplaceIfExists remains false, even in a destination race.
        self._ok(self.kernel.SetFileInformationByHandle(handle, 3, buffer, size))

    def discard(self, handle):
        delete = U8(1)
        self._ok(self.kernel.SetFileInformationByHandle(handle, 4, C.byref(delete), C.sizeof(delete)))

    def names(self, handle):
        first = True
        while True:
            buffer, status = C.create_string_buffer(65536), IoStatus()
            result = self.nt.NtQueryDirectoryFile(handle, None, None, None, C.byref(status),
                        buffer, len(buffer), 12, 0, None, int(first))  # FileNamesInformation
            first = False
            if (result & 0xFFFFFFFF) == 0x80000006:  # STATUS_NO_MORE_FILES
                return
            if result < 0 or not 0 < status.Information <= len(buffer):
                raise OSError("Native directory query failed")
            yield from directory_names(buffer.raw[:status.Information])
