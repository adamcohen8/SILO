import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from local_ai_appliance.folders import AccessDenied, DocumentTools, FolderBroker


@unittest.skipUnless(os.name == "posix", "POSIX development adapter only")
class FolderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.ro = self.base / "reference"
        self.rw = self.base / "drafts"
        self.outside = self.base / "private"
        for path in (self.ro, self.rw, self.outside):
            path.mkdir()
        (self.ro / "source.txt").write_text("reference evidence")
        (self.outside / "secret.txt").write_text("not granted")
        self.broker = FolderBroker(max_file_bytes=1024)
        self.tools = DocumentTools(self.broker)

    def tearDown(self):
        self.broker.close()
        self.temp.cleanup()

    def test_starts_with_no_access(self):
        self.assertEqual(self.tools.list_folders(), [])
        with self.assertRaises(AccessDenied):
            self.tools.read_text("invented", "source.txt")

    def test_read_only(self):
        folder = self.broker.grant(self.ro, "read-only")
        self.assertEqual(self.tools.read_text(folder.id, "source.txt"), "reference evidence")
        with self.assertRaises(AccessDenied):
            self.tools.create_text(folder.id, "new.txt", "bad")
        self.assertFalse((self.ro / "new.txt").exists())

    def test_create_in_editable(self):
        folder = self.broker.grant(self.rw, "editable")
        self.tools.create_text(folder.id, "answer.txt", "draft")
        self.assertEqual((self.rw / "answer.txt").read_text(), "draft")
        self.assertEqual(self.tools.read_text(folder.id, "answer.txt"), "draft")
        self.assertEqual(list(self.rw.glob(".local-ai-write-*")), [])

    def test_existing_files_preserved(self):
        folder = self.broker.grant(self.rw, "editable")
        (self.rw / "existing.txt").write_text("original")
        with self.assertRaises(AccessDenied):
            self.tools.create_text(folder.id, "existing.txt", "replacement")
        self.assertEqual((self.rw / "existing.txt").read_text(), "original")

    def test_invalid_paths(self):
        folder = self.broker.grant(self.rw, "editable")
        for path in ("../private/secret.txt", "/absolute", "a/../../b", "", "a//b", "./file",
                     "C:/Windows/file", "a\\b", "file:stream", "a\x00b", ".local-ai-write-owned"):
            with self.subTest(path=path), self.assertRaises(AccessDenied):
                self.tools.create_text(folder.id, path, "bad")
        self.assertEqual(list(self.rw.iterdir()), [])

    def test_nested_read_and_create(self):
        folder = self.broker.grant(self.rw, "editable")
        (self.rw / "project").mkdir()
        self.tools.create_text(folder.id, "project/draft.txt", "nested")
        self.assertEqual(self.tools.read_text(folder.id, "project/draft.txt"), "nested")

    def test_symlink_file_cannot_read_or_write(self):
        folder = self.broker.grant(self.rw, "editable")
        (self.rw / "link.txt").symlink_to(self.outside / "secret.txt")
        with self.assertRaises(AccessDenied):
            self.tools.read_text(folder.id, "link.txt")
        with self.assertRaises(AccessDenied):
            self.tools.create_text(folder.id, "link.txt", "bad")
        self.assertEqual((self.outside / "secret.txt").read_text(), "not granted")

    def test_symlink_parent_cannot_escape(self):
        folder = self.broker.grant(self.rw, "editable")
        (self.rw / "escape").symlink_to(self.outside, target_is_directory=True)
        with self.assertRaises(AccessDenied):
            self.tools.read_text(folder.id, "escape/secret.txt")
        with self.assertRaises(AccessDenied):
            self.tools.create_text(folder.id, "escape/new.txt", "bad")
        self.assertFalse((self.outside / "new.txt").exists())

    def test_grant_symlink_denied(self):
        link = self.base / "link"
        link.symlink_to(self.ro, target_is_directory=True)
        with self.assertRaises(AccessDenied):
            self.broker.grant(link, "read-only")

    def test_grant_symlink_ancestor_denied(self):
        (self.base / "link").symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(AccessDenied):
            self.broker.grant(self.base / "link" / "reference", "read-only")

    def test_overlap_denied_in_both_directions(self):
        self.broker.grant(self.ro, "read-only")
        child = self.ro / "child"
        child.mkdir()
        for path in (self.ro, child, self.base):
            with self.subTest(path=path), self.assertRaises(AccessDenied):
                self.broker.grant(path, "editable")

    def test_unknown_mode_denied(self):
        with self.assertRaises(AccessDenied):
            self.broker.grant(self.ro, "admin")

    def test_root_and_relative_grants_denied(self):
        for path in (Path("/"), Path("relative"), self.base / ".." / "elsewhere"):
            with self.subTest(path=path), self.assertRaises(AccessDenied):
                self.broker.grant(path, "editable")

    def test_revocation_denies_existing_tools(self):
        folder = self.broker.grant(self.rw, "editable")
        self.tools.create_text(folder.id, "first.txt", "first")
        revision = self.broker.revision
        self.broker.revoke(folder.id)
        self.assertGreater(self.broker.revision, revision)
        for operation in (lambda: self.tools.read_text(folder.id, "first.txt"),
                          lambda: self.tools.create_text(folder.id, "second.txt", "second")):
            with self.assertRaises(AccessDenied):
                operation()
        self.assertEqual(self.tools.list_folders(), [])

    def test_hardlink_read_denied(self):
        folder = self.broker.grant(self.rw, "editable")
        os.link(self.outside / "secret.txt", self.rw / "hard.txt")
        with self.assertRaises(AccessDenied):
            self.tools.read_text(folder.id, "hard.txt")

    def test_special_file_denied_without_hang(self):
        folder = self.broker.grant(self.rw, "editable")
        os.mkfifo(self.rw / "pipe")
        with self.assertRaises(AccessDenied):
            self.tools.read_text(folder.id, "pipe")

    def test_size_limit(self):
        folder = self.broker.grant(self.rw, "editable")
        (self.rw / "large.txt").write_text("x" * 1025)
        with self.assertRaises(AccessDenied):
            self.tools.read_text(folder.id, "large.txt")
        with self.assertRaises(AccessDenied):
            self.tools.create_text(folder.id, "new.txt", "x" * 1025)
        self.assertFalse((self.rw / "new.txt").exists())

    def test_destination_race_does_not_overwrite(self):
        folder = self.broker.grant(self.rw, "editable")
        original_link = os.link

        def racing_link(*args, **kwargs):
            (self.rw / "new.txt").write_text("concurrent user edit")
            return original_link(*args, **kwargs)

        with patch("local_ai_appliance.folders.os.link", side_effect=racing_link):
            with self.assertRaises(AccessDenied):
                self.tools.create_text(folder.id, "new.txt", "model draft")
        self.assertEqual((self.rw / "new.txt").read_text(), "concurrent user edit")
        self.assertEqual(list(self.rw.glob(".local-ai-write-*")), [])

    def test_parent_swap_uses_opened_directory(self):
        folder = self.broker.grant(self.rw, "editable")
        (self.rw / "nested").mkdir()
        original_parent = self.broker._parent

        def swapping_parent(*args):
            fd = original_parent(*args)
            (self.rw / "nested").rename(self.rw / "original")
            (self.rw / "nested").symlink_to(self.outside, target_is_directory=True)
            return fd

        with patch.object(self.broker, "_parent", side_effect=swapping_parent):
            self.tools.create_text(folder.id, "nested/new.txt", "draft")
        self.assertFalse((self.outside / "new.txt").exists())
        self.assertEqual((self.rw / "original" / "new.txt").read_text(), "draft")

    def test_model_surface_has_no_permission_or_execution_tools(self):
        for name in ("grant", "revoke", "shell", "execute", "http", "write_file"):
            self.assertFalse(hasattr(self.tools, name))
        folder = self.broker.grant(self.ro, "read-only")
        entry = self.tools.list_folders()[0]
        self.assertEqual(entry["id"], folder.id)
        self.assertNotIn(str(self.ro), str(entry))


class PlatformTests(unittest.TestCase):
    def test_windows_fails_closed(self):
        with patch("local_ai_appliance.folders.os.name", "nt"):
            with self.assertRaisesRegex(RuntimeError, "Windows"):
                FolderBroker()


if __name__ == "__main__":
    unittest.main()
