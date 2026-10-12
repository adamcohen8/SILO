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


class FileIdentifier(C.Union):
    _fields_ = [("FileId", C.c_int64), ("ExtendedFileId", U8 * 16)]


class FileIdDescriptor(C.Structure):
    _fields_ = [("Size", U32), ("Type", U32), ("Id", FileIdentifier)]


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
        self._edit_reads = {}
        self.kernel = C.WinDLL("kernel32", use_last_error=True)
        self.nt = C.WinDLL("ntdll")
        self._bind(self.kernel, "CreateFileW", HANDLE,
                   [C.c_wchar_p, U32, U32, HANDLE, U32, U32, HANDLE])
        self._bind(self.kernel, "CloseHandle", I32, [HANDLE])
        self._bind(self.kernel, "OpenFileById", HANDLE,
                   [HANDLE, C.POINTER(FileIdDescriptor), U32, U32, HANDLE, U32])
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
        self._bind(self.nt, "NtSetInformationFile", I32,
                   [HANDLE, C.POINTER(IoStatus), HANDLE, U32, U32])

    @staticmethod
    def _bind(dll, name, result, args):
        function = getattr(dll, name)
        function.restype, function.argtypes = result, args

    @staticmethod
    def _ok(result):
        if not result:
            raise OSError(C.get_last_error(), "Windows file operation failed")

    def close(self, handle):
        data = self._edit_reads.pop(handle, None)
        try:
            if data is not None:
                self._ok(self.kernel.CloseHandle(data))
        finally:
            self._ok(self.kernel.CloseHandle(handle))

    def open_drive(self, drive):
        if self.kernel.GetDriveTypeW(drive) != 3:  # DRIVE_FIXED only.
            raise OSError("Only fixed local disks are supported by this candidate")
        handle = self.kernel.CreateFileW(drive, 0x1000A1, 3, None, 3, 0x02300000, None)
        if handle in {None, C.c_void_p(-1).value}:
            raise OSError(C.get_last_error(), "Drive directory open failed")
        return handle

    def open_child(self, parent, name, *, directory=None, read=False, create=False, delete=False, security=False, edit=False, edit_metadata=False):
        if edit:
            if directory is not False or create: raise OSError('Exclusive editing requires an existing regular file')
            return self.open_edit(parent,name)
        if read:
            raise OSError("Existing file data requires a checked metadata handle")
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
        if directory is True:
            access |= 1  # FILE_LIST_DIRECTORY
        if directory is True:
            access |= 0x20  # FILE_TRAVERSE
        if create:
            # Retained new directories need the same sharing as existing
            # parents for child publication. They need no DELETE authority.
            access |= 4 if directory is True else 0x10002
        if delete:
            access |= 0x10000
        # OPEN_NO_RECALL (0x00400000) is rejected by this user-mode NtCreateFile
        # path on the Windows target, even for ordinary directory metadata.
        # These opens retain no-follow/handle-relative acquisition. Existing
        # files are opened for metadata only, checked for reparse/recall status
        # by the caller, then opened for data through checked open_read below.
        # The Win32 no-recall flag remains on that data handle; neither API
        # provides an OS egress boundary against arbitrary filesystem filters.
        options = 0x00200020  # OPEN_REPARSE_POINT | SYNCHRONOUS_IO_NONALERT
        if directory is True:
            options |= 1  # FILE_DIRECTORY_FILE
        elif directory is False:
            options |= 0x40  # FILE_NON_DIRECTORY_FILE
        # Retained directories deny deletion/rename; reads also deny writers.
        # A named DELETE-only edit lease allows our by-ID data read, but
        # denies every other writer/deleter. Its paired data handle denies
        # other data reads; no named data open can recall a cloud file.
        share = (1 if delete else 7) if edit_metadata else (3 if create and directory is True else (0 if create or delete else (1 if read else 3)))
        result = self.nt.NtCreateFile(C.byref(handle), access, C.byref(attributes), C.byref(status),
                                     None, 0x80, share, 2 if create else 1, options, None, 0)
        if result < 0:
            if (result & 0xFFFFFFFF) in {0xC0000034, 0xC000003A}:  # NAME/PATH_NOT_FOUND
                raise FileNotFoundError("Native file is unavailable")
            raise OSError(f"Native relative open failed (NTSTATUS 0x{result & 0xFFFFFFFF:08X})")
        if not handle.value:
            raise OSError("Native relative open returned no handle")
        return handle.value

    def open_edit(self,parent,name):
        """Pair a named metadata/DELETE lease with a checked no-recall ID read.

        NTFS cannot rename/delete a handle opened by file ID. The named lease
        has no data access, so all content reads still use the verified ID.
        Together the two sharing modes deny foreign reads, writes and renames.
        """
        metadata=self.open_child(parent,name,directory=False,edit_metadata=True)
        handle=data=check=None
        try:
            before=self.info(metadata)
            if not before.disk or before.directory or before.reparse or before.offline or before.links!=1:
                raise OSError('Only ordinary single-link local files can be edited')
            handle=self.open_child(parent,name,directory=False,delete=True,edit_metadata=True)
            if self.info(handle)!=before:
                raise OSError('Reviewed file identity changed before exclusive editing')
            descriptor=FileIdDescriptor();descriptor.Size=C.sizeof(FileIdDescriptor);descriptor.Type=0
            descriptor.Id.FileId=before.index
            data=self.kernel.OpenFileById(handle,C.byref(descriptor),0x100081,4,None,0x00300000)
            if data in {None,C.c_void_p(-1).value}:
                data=None;raise OSError(C.get_last_error(),'Checked edit data reopen failed')
            check=self.open_child(parent,name,directory=False,edit_metadata=True)
            if self.info(data)!=before or self.info(check)!=before or self.info(handle)!=before:
                raise OSError('Reviewed file identity changed before exclusive editing')
            self._edit_reads[handle]=data
            result=handle;handle=data=None;return result
        finally:
            if check is not None:self.close(check)
            if data is not None:self.close(data)
            if handle is not None:self.close(handle)
            self.close(metadata)

    def open_read(self, metadata_handle):
        # Use the held object's volume and NTFS file ID, never a pathname.
        # ReOpenFile rejects OPEN_NO_RECALL on the target; OpenFileById accepts
        # the documented Win32 no-recall/no-follow flags. Holding metadata pins
        # the object identity while the data handle denies writers. By-ID and
        # metadata handles may still permit name changes; never reopen by path.
        before = self.info(metadata_handle)
        if (not before.disk or before.directory or before.reparse or before.offline
                or before.links != 1):
            raise OSError("Only checked local single-link files can be opened for data")
        descriptor = FileIdDescriptor()
        descriptor.Size = C.sizeof(FileIdDescriptor)
        descriptor.Type = 0  # FileIdType: 64-bit NTFS file identifier.
        descriptor.Id.FileId = before.index
        handle = self.kernel.OpenFileById(metadata_handle, C.byref(descriptor),
                                          0x100081, 1, None, 0x00300000)
        if handle in {None, C.c_void_p(-1).value}:
            raise OSError(C.get_last_error(), "Checked file reopen failed")
        try:
            if self.info(handle) != before:
                raise OSError("Checked file identity or attributes changed")
        except BaseException:
            self.close(handle)
            raise
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
        handle = self._edit_reads.get(handle, handle)
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
        handle = self._edit_reads.get(handle, handle)
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
        # Native FileRenameInformation accepts the retained parent handle.
        # The Win32 FileRenameInfo wrapper rejects this relative form on target.
        # ReplaceIfExists remains false, including in a destination race.
        status = IoStatus()
        result = self.nt.NtSetInformationFile(handle, C.byref(status), buffer, len(buffer), 10)
        if result < 0:
            raise OSError(f"Native publication failed (NTSTATUS 0x{result & 0xFFFFFFFF:08X})")

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
