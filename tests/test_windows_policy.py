import ctypes
from dataclasses import dataclass
import struct
import unittest

from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.windows_folders import WindowsFolderBroker, parts
from local_ai_appliance.windows_native import (FileInformation, Info, IoStatus, ObjectAttributes,
                                               RenameInformation, UnicodeString, directory_names)
from local_ai_appliance.workspace import Workspace


@dataclass
class Node:
    index: int
    directory: bool
    name: str
    parent: object = None
    data: bytes = b""
    reparse: bool = False
    links: int = 1
    volume: int = 7
    disk: bool = True
    offline: bool = False


class FakeNative:
    """Inert native contract fixture, not an emulation of Windows semantics."""
    def __init__(self):
        self.nodes = {}
        self.handles = {}
        self.next_handle = 100
        self.next_index = 1
        self.calls = []
        self.fs = "NTFS"
        self.on_publish = None
        self.fail_write = False
        self.deleted = set()
        self.root = self.add(None, "", directory=True)
        self.reference = self.add(self.root, "reference", directory=True)
        self.drafts = self.add(self.root, "drafts", directory=True)
        self.source = self.add(self.reference, "source.txt", data=b"original\n")

    def add(self, parent, name, *, directory=False, data=b""):
        node = Node(self.next_index, directory, name, parent, data)
        self.next_index += 1
        self.nodes[(parent.index if parent else None, name.casefold())] = node
        return node

    def handle(self, node):
        self.next_handle += 1
        self.handles[self.next_handle] = node
        return self.next_handle

    def close(self, handle):
        node = self.handles.pop(handle)
        if node.index in self.deleted:
            self.nodes.pop((node.parent.index, node.name.casefold()), None)

    def open_drive(self, drive):
        self.calls.append(("drive", drive))
        return self.handle(self.root)

    def open_child(self, parent, name, *, directory=None, read=False, create=False):
        self.calls.append(("child", parent, name, directory, read, create))
        node = self.handles[parent]
        if name == ".":
            return self.handle(node)
        key = (node.index, name.casefold())
        if create:
            if key in self.nodes:
                raise FileExistsError()
            child = self.add(node, name)
        else:
            child = self.nodes.get(key)
            if child is None:
                raise FileNotFoundError()
        if child.reparse or (directory is not None and child.directory != directory):
            raise OSError("Fixture denied native open")
        return self.handle(child)

    def info(self, handle):
        node = self.handles[handle]
        return Info(node.volume, node.index, len(node.data), node.links, node.directory,
                    node.reparse, node.disk, node.offline)

    def open_read(self, metadata):
        self.calls.append(("read_handle", metadata))
        return self.handle(self.handles[metadata])

    def filesystem(self, handle):
        return self.fs

    def canonical(self, handle):
        names, node = [], self.handles[handle]
        while node.parent:
            names.insert(0, node.name)
            node = node.parent
        return "\\\\?\\Volume{12345678-1234-1234-1234-123456789abc}\\" + "\\".join(names)

    def read(self, handle, limit):
        return self.handles[handle].data[:limit + 1]

    def write(self, handle, data):
        self.handles[handle].data = data
        if self.fail_write:
            raise OSError("Fixture write failure")

    def publish(self, handle, parent, name):
        if self.on_publish:
            self.on_publish()
        node, destination = self.handles[handle], self.handles[parent]
        key = (destination.index, name.casefold())
        if key in self.nodes:
            raise FileExistsError()
        self.nodes.pop((node.parent.index, node.name.casefold()))
        node.parent, node.name = destination, name
        self.nodes[key] = node

    def discard(self, handle):
        self.deleted.add(self.handles[handle].index)

    def names(self, handle):
        parent = self.handles[handle]
        yield "."
        yield ".."
        yield from [n.name for (pid, _), n in self.nodes.items() if pid == parent.index]


class WindowsPolicyTests(unittest.TestCase):
    def setUp(self):
        self.native = FakeNative()
        self.broker = WindowsFolderBroker(validation_mode=True, native=self.native, max_file_bytes=1024)

    def tearDown(self):
        self.broker.close()
        self.assertEqual(self.native.handles, {})

    def grant(self):
        self.ro = self.broker.grant("C:\\reference", "read-only")
        self.rw = self.broker.grant("C:\\drafts", "editable")

    def test_candidate_requires_explicit_validation_opt_in(self):
        with self.assertRaises(RuntimeError):
            WindowsFolderBroker(native=self.native)
        self.assertEqual(self.broker.folders(), [])

    def test_windows_path_forms_fail_before_native_access(self):
        for value in ("C:\\", "C:reference", "/reference", "\\\\server\\share", "\\\\?\\C:\\reference",
                      "\\\\.\\C:\\reference", "C:\\reference\\..\\drafts", "C:\\NUL", "C:\\reference."):
            with self.subTest(value=value), self.assertRaises(AccessDenied):
                self.broker.grant(value, "read-only")
        self.assertEqual(self.native.calls, [])

    def test_components_reject_devices_streams_wildcards_aliases_and_controls(self):
        for value in ("../x", "/x", "x//y", "x\\y", "file:stream", "file.", "file ", "NUL.txt",
                      "con", "CON .txt", "CONIN$", "COM¹.txt", "lpt9.log", "x*y", "x?y", "a\0b", "x/.",
                      ".LOCAL-AI-WRITE-temp", "a" * 256, "\ud800"):
            with self.subTest(value=value), self.assertRaises(AccessDenied):
                parts(value)
        self.assertEqual(parts("nested/unicode-文.txt"), ["nested", "unicode-文.txt"])

    def test_read_and_reviewed_creation_through_controller(self):
        self.grant()
        workspace = Workspace(self.broker)
        source = workspace.open_text(self.ro.id, "source.txt")
        proposal = workspace.propose(self.rw.id, "new.txt", "revision", source)
        self.assertNotIn((self.native.drafts.index, "new.txt"), self.native.nodes)
        workspace.approve(proposal.id)
        self.assertEqual(self.native.nodes[(self.native.drafts.index, "new.txt")].data, b"revision")
        self.assertEqual(self.native.source.data, b"original\n")

    def test_read_only_and_revocation_are_enforced(self):
        self.grant()
        with self.assertRaises(AccessDenied):
            self.broker.write_file(self.ro.id, "new.txt", b"bad")
        self.broker.revoke(self.ro.id)
        with self.assertRaises(AccessDenied):
            self.broker.read_file(self.ro.id, "source.txt")

    def test_overlap_and_case_aliases_denied_without_handle_leaks(self):
        self.native.add(self.native.reference, "child", directory=True)
        self.broker.grant("C:\\reference", "read-only")
        before = len(self.native.handles)
        for path in ("C:\\REFERENCE", "C:\\reference\\child"):
            with self.assertRaises(AccessDenied):
                self.broker.grant(path, "editable")
            self.assertEqual(len(self.native.handles), before)

    def test_short_alias_lineage_overlap_denied(self):
        child = self.native.add(self.native.reference, "child", directory=True)
        self.native.nodes[(self.native.root.index, "refere~1")] = self.native.reference
        self.broker.grant("C:\\reference\\child", "read-only")
        with self.assertRaises(AccessDenied):
            self.broker.grant("C:\\REFERE~1", "editable")

    def test_non_ntfs_and_reparse_grants_denied(self):
        self.native.fs = "FAT32"
        with self.assertRaises(AccessDenied):
            self.broker.grant("C:\\reference", "read-only")
        self.native.fs = "NTFS"
        self.native.reference.reparse = True
        with self.assertRaises(AccessDenied):
            self.broker.grant("C:\\reference", "read-only")

    def test_hardlink_reparse_cross_volume_device_and_size_denied(self):
        self.grant()
        for key, value in (("links", 2), ("reparse", True), ("offline", True), ("volume", 9), ("disk", False),
                           ("data", b"x" * 1025)):
            original = getattr(self.native.source, key)
            self.native.calls.clear()
            setattr(self.native.source, key, value)
            with self.subTest(key=key), self.assertRaises(AccessDenied):
                self.broker.read_file(self.ro.id, "source.txt")
            self.assertFalse(any(call[0] == "read_handle" for call in self.native.calls))
            setattr(self.native.source, key, original)

    def test_nested_reads_use_handle_relative_single_components(self):
        self.grant()
        nested = self.native.add(self.native.reference, "nested", directory=True)
        self.native.add(nested, "file.txt", data=b"nested")
        self.assertEqual(self.broker.read_file(self.ro.id, "nested/file.txt"), b"nested")
        for call in self.native.calls:
            if call[0] == "child":
                self.assertNotIn("/", call[2])
                self.assertNotIn("\\", call[2])

    def test_listing_filters_forbidden_names_and_objects_and_is_repeatable(self):
        self.grant()
        self.native.add(self.native.reference, "NUL")
        self.native.add(self.native.reference, "link").reparse = True
        self.native.add(self.native.reference, "hard").links = 2
        self.native.add(self.native.reference, "directory", directory=True)
        expected = {"entries": [{"name": "directory", "kind": "directory"},
                                {"name": "source.txt", "kind": "file"}], "truncated": False}
        self.assertEqual(self.broker.list_directory(self.ro.id), expected)
        self.assertEqual(self.broker.list_directory(self.ro.id), expected)
        self.assertTrue(self.broker.list_directory(self.ro.id, limit=1)["truncated"])

    def test_destination_race_preserves_concurrent_file_and_discards_temp(self):
        self.grant()
        self.native.on_publish = lambda: self.native.add(self.native.drafts, "new.txt", data=b"user work")
        with self.assertRaises(AccessDenied):
            self.broker.write_file(self.rw.id, "new.txt", b"agent draft")
        self.assertEqual(self.native.nodes[(self.native.drafts.index, "new.txt")].data, b"user work")
        self.assertFalse(any(n.name.startswith(".local-ai-write-") for n in self.native.nodes.values()))

    def test_write_failure_discards_owned_temp(self):
        self.grant()
        self.native.fail_write = True
        with self.assertRaises(AccessDenied):
            self.broker.write_file(self.rw.id, "new.txt", b"partial")
        self.assertFalse(any(n.parent is self.native.drafts for n in self.native.nodes.values()))

    def test_failed_nested_open_closes_acquired_handles(self):
        self.grant()
        self.native.add(self.native.reference, "nested", directory=True)
        before = len(self.native.handles)
        with self.assertRaises(AccessDenied):
            self.broker.read_file(self.ro.id, "nested/missing/file.txt")
        self.assertEqual(len(self.native.handles), before)


class NativeRecordTests(unittest.TestCase):
    def test_windows_64bit_abi_layouts(self):
        if ctypes.sizeof(ctypes.c_void_p) != 8:
            self.skipTest("64-bit ABI layout check")
        self.assertEqual(ctypes.sizeof(UnicodeString), 16)
        self.assertEqual(ctypes.sizeof(ObjectAttributes), 48)
        self.assertEqual(ctypes.sizeof(IoStatus), 16)
        self.assertEqual(ctypes.sizeof(FileInformation), 52)
        self.assertEqual(RenameInformation.FileName.offset, 20)

    def test_valid_directory_records(self):
        name = "guide.txt".encode("utf-16-le")
        data = struct.pack("<III", 0, 1, len(name)) + name
        self.assertEqual(list(directory_names(data)), ["guide.txt"])

    def test_invalid_native_directory_records_fail(self):
        for data in (b"short", struct.pack("<III", 0, 1, 5) + b"12345",
                     struct.pack("<III", 1, 1, 2) + b"a\0", struct.pack("<III", 0, 1, 2000)):
            with self.assertRaises(OSError):
                list(directory_names(data))
