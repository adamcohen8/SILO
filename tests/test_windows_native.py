"""Native acceptance candidates; only synthetic temporary files are touched."""

import ctypes as C
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.windows_folders import WindowsFolderBroker
from local_ai_appliance.workspace import Workspace


@unittest.skipUnless(os.name == "nt", "Requires native Windows; never certified by a mock")
class WindowsNativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="local-ai-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.reference, self.drafts = self.base / "reference", self.base / "drafts"
        self.reference.mkdir()
        self.drafts.mkdir()
        (self.reference / "source.txt").write_bytes(b"Synthetic original.\n")
        self.broker = WindowsFolderBroker(validation_mode=True, max_file_bytes=1024)
        self.workspace = Workspace(self.broker)
        self.addCleanup(self.workspace.close)
        self.ro = self.workspace.grant(self.reference, "read-only")
        self.rw = self.workspace.grant(self.drafts, "editable")

    def test_native_read_and_repeatable_listing(self):
        expected = [{"name": "source.txt", "kind": "file"}]
        self.assertEqual(self.broker.read_file(self.ro.id, "source.txt"), b"Synthetic original.\n")
        for _ in range(3):
            self.assertEqual(self.broker.list_directory(self.ro.id)["entries"], expected)

    def test_native_approval_creates_exact_new_copy(self):
        source = self.workspace.open_text(self.ro.id, "source.txt")
        proposal = self.workspace.propose(self.rw.id, "revised.txt", "Synthetic revision.\n", source)
        self.assertFalse((self.drafts / "revised.txt").exists())
        self.workspace.approve(proposal.id)
        self.assertEqual((self.drafts / "revised.txt").read_bytes(), b"Synthetic revision.\n")
        self.assertEqual((self.reference / "source.txt").read_bytes(), b"Synthetic original.\n")

    def test_native_read_only_and_existing_file_protection(self):
        with self.assertRaises(AccessDenied):
            self.broker.write_file(self.ro.id, "new.txt", b"bad")
        (self.drafts / "existing.txt").write_bytes(b"user work")
        with self.assertRaises(AccessDenied):
            self.broker.write_file(self.rw.id, "existing.txt", b"bad")
        self.assertEqual((self.drafts / "existing.txt").read_bytes(), b"user work")

    def test_native_hardlink_is_denied_and_hidden_from_listing(self):
        os.link(self.reference / "source.txt", self.reference / "hard.txt")
        with self.assertRaises(AccessDenied):
            self.broker.read_file(self.ro.id, "hard.txt")
        self.assertEqual(self.broker.list_directory(self.ro.id)["entries"], [])

    def test_native_symlink_and_ancestor_reparse_rejected(self):
        try:
            (self.reference / "link").symlink_to(self.drafts, target_is_directory=True)
        except OSError as e:
            self.skipTest(f"Native symlink fixture privilege unavailable: {e.winerror}; acceptance incomplete")
        (self.drafts / "secret.txt").write_bytes(b"outside read-only grant")
        with self.assertRaises(AccessDenied):
            self.broker.read_file(self.ro.id, "link/secret.txt")
        with self.assertRaises(AccessDenied):
            self.broker.grant(self.reference / "link", "editable")
        self.assertNotIn("link", [e["name"] for e in self.broker.list_directory(self.ro.id)["entries"]])

    def test_native_junction_rejected_without_a_shell_command(self):
        native = self.broker._native
        junction = self.reference / "junction"
        junction.mkdir()
        (self.drafts / "secret.txt").write_bytes(b"outside read-only grant")
        substitute = ("\\??\\" + str(self.drafts)).encode("utf-16-le")
        printable = str(self.drafts).encode("utf-16-le")
        names = substitute + b"\0\0" + printable + b"\0\0"
        payload = struct.pack("<IHHHHHH", 0xA0000003, 8 + len(names), 0,
                              0, len(substitute), len(substitute) + 2, len(printable)) + names
        control = native.kernel.DeviceIoControl
        control.restype = C.c_int32
        control.argtypes = [C.c_void_p, C.c_uint32, C.c_void_p, C.c_uint32,
                            C.c_void_p, C.c_uint32, C.POINTER(C.c_uint32), C.c_void_p]
        handle = native.kernel.CreateFileW(str(junction), 0x40000000, 7, None, 3, 0x02200000, None)
        if handle in {None, C.c_void_p(-1).value}:
            self.fail("Native junction fixture open failed; acceptance incomplete")
        try:
            data, returned = C.create_string_buffer(payload), C.c_uint32()
            if not control(handle, 0x000900A4, data, len(payload), None, 0, C.byref(returned), None):
                self.fail(f"Native junction fixture creation failed: {C.get_last_error()}; acceptance incomplete")
        finally:
            native.close(handle)
        with self.assertRaises(AccessDenied):
            self.broker.read_file(self.ro.id, "junction/secret.txt")
        with self.assertRaises(AccessDenied):
            self.broker.grant(junction, "editable")
        self.assertNotIn("junction", [e["name"] for e in self.broker.list_directory(self.ro.id)["entries"]])

    def test_native_destination_race_preserves_user_content(self):
        native = self.broker._native
        publish = native.publish
        def race(handle, parent, name):
            (self.drafts / name).write_bytes(b"concurrent user work")
            return publish(handle, parent, name)
        with patch.object(native, "publish", side_effect=race), self.assertRaises(AccessDenied):
            self.broker.write_file(self.rw.id, "race.txt", b"agent draft")
        self.assertEqual((self.drafts / "race.txt").read_bytes(), b"concurrent user work")
        self.assertEqual([p.name for p in self.drafts.iterdir()], ["race.txt"])

    def test_native_stale_source_and_revocation_invalidate_review(self):
        source = self.workspace.open_text(self.ro.id, "source.txt")
        proposal = self.workspace.propose(self.rw.id, "revised.txt", "revision", source)
        (self.reference / "source.txt").write_bytes(b"new source")
        with self.assertRaises(AccessDenied):
            self.workspace.approve(proposal.id)
        self.workspace.revoke(self.ro.id)
        with self.assertRaises(AccessDenied):
            self.broker.read_file(self.ro.id, "source.txt")

    def test_native_nested_directory_and_filename_syntax(self):
        (self.reference / "nested").mkdir()
        (self.reference / "nested" / "file.txt").write_bytes(b"nested")
        self.assertEqual(self.broker.read_file(self.ro.id, "nested/file.txt"), b"nested")
        for path in ("../drafts/file.txt", "source.txt:stream", "NUL", "source.txt.", "C:/Windows/win.ini"):
            with self.subTest(path=path), self.assertRaises(AccessDenied):
                self.broker.read_file(self.ro.id, path)

    def test_native_grant_locks_directory_against_substitution(self):
        with self.assertRaises(OSError):
            self.reference.rename(self.base / "moved-reference")
        self.assertEqual(self.broker.read_file(self.ro.id, "source.txt"), b"Synthetic original.\n")

    def test_native_case_and_overlapping_grants_rejected(self):
        with self.assertRaises(AccessDenied):
            self.broker.grant(str(self.reference).swapcase(), "editable")
        with self.assertRaises(AccessDenied):
            self.broker.grant(self.base, "editable")
