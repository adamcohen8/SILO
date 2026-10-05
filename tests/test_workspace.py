import os
from pathlib import Path
import tempfile
import unittest

from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.workspace import DraftTools, TextSource, Workspace


@unittest.skipUnless(os.name == "posix", "POSIX development adapter only")
class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.reference = self.base / "reference"
        self.drafts = self.base / "drafts"
        self.reference.mkdir()
        self.drafts.mkdir()
        (self.reference / "procedure.md").write_text("Original procedure.\n")
        self.workspace = Workspace()
        self.ro = self.workspace.grant(self.reference, "read-only")
        self.rw = self.workspace.grant(self.drafts, "editable")
        self.tools = DraftTools(self.workspace)

    def tearDown(self):
        self.workspace.close()
        self.temp.cleanup()

    def proposal(self):
        source = self.workspace.open_text(self.ro.id, "procedure.md")
        return self.workspace.propose(self.rw.id, "revised.md", "Reviewed revision.\n", source)

    def test_proposal_does_not_write(self):
        proposal = self.proposal()
        self.assertIn("-Original procedure.", proposal.diff)
        self.assertIn("+Reviewed revision.", proposal.diff)
        self.assertEqual(list(self.drafts.iterdir()), [])

    def test_host_approval_saves_exact_reviewed_content_once(self):
        proposal = self.proposal()
        self.workspace.approve(proposal.id)
        self.assertEqual((self.drafts / "revised.md").read_text(), proposal.text)
        self.assertEqual((self.reference / "procedure.md").read_text(), "Original procedure.\n")
        with self.assertRaises(AccessDenied):
            self.workspace.approve(proposal.id)

    def test_read_only_destination_denied(self):
        with self.assertRaises(AccessDenied):
            self.workspace.propose(self.ro.id, "new.md", "new")
        self.assertFalse((self.reference / "new.md").exists())

    def test_existing_destination_denied(self):
        (self.drafts / "existing.md").write_text("user work")
        with self.assertRaises(AccessDenied):
            self.workspace.propose(self.rw.id, "existing.md", "replacement")
        self.assertEqual((self.drafts / "existing.md").read_text(), "user work")

    def test_destination_appearing_after_review_preserved(self):
        proposal = self.proposal()
        (self.drafts / "revised.md").write_text("concurrent user work")
        with self.assertRaises(AccessDenied):
            self.workspace.approve(proposal.id)
        self.assertEqual((self.drafts / "revised.md").read_text(), "concurrent user work")

    def test_source_change_after_review_denies_save(self):
        proposal = self.proposal()
        (self.reference / "procedure.md").write_text("New source version")
        with self.assertRaises(AccessDenied):
            self.workspace.approve(proposal.id)
        self.assertFalse((self.drafts / "revised.md").exists())

    def test_stale_open_source_denies_proposal(self):
        source = self.workspace.open_text(self.ro.id, "procedure.md")
        (self.reference / "procedure.md").write_text("Changed")
        with self.assertRaises(AccessDenied):
            self.workspace.propose(self.rw.id, "new.md", "new", source)

    def test_forged_source_text_denied(self):
        source = self.workspace.open_text(self.ro.id, "procedure.md")
        forged = TextSource(source.folder_id, source.path, "forged", source.sha256)
        with self.assertRaises(AccessDenied):
            self.workspace.propose(self.rw.id, "new.md", "new", forged)

    def test_revoking_either_folder_invalidates_proposal(self):
        for folder in (self.ro, self.rw):
            proposal = self.proposal()
            self.workspace.revoke(folder.id)
            with self.assertRaises(AccessDenied):
                self.workspace.approve(proposal.id)
            self.assertFalse((self.drafts / "revised.md").exists())
            if folder == self.ro:
                self.ro = self.workspace.grant(self.reference, "read-only")

    def test_direct_broker_permission_change_denies_save(self):
        proposal = self.proposal()
        another = self.base / "other"
        another.mkdir()
        self.workspace.broker.grant(another, "read-only")
        with self.assertRaises(AccessDenied):
            self.workspace.approve(proposal.id)

    def test_discard_and_unknown_approval_denied(self):
        proposal = self.proposal()
        self.workspace.discard(proposal.id)
        for proposal_id in (proposal.id, "invented"):
            with self.assertRaises(AccessDenied):
                self.workspace.approve(proposal_id)

    def test_agent_surface_cannot_approve_or_write(self):
        for method in ("approve", "grant", "revoke", "write_file", "create_text", "shell", "execute"):
            self.assertFalse(hasattr(self.tools, method))
        source = self.tools.read_text(self.ro.id, "procedure.md")
        result = self.tools.propose_text(self.rw.id, "new.md", "Revision", self.ro.id,
                                         "procedure.md", source["sha256"])
        self.assertEqual(result["status"], "awaiting_user_review")
        self.assertFalse((self.drafts / "new.md").exists())

    def test_agent_stale_digest_denied(self):
        source = self.tools.read_text(self.ro.id, "procedure.md")
        (self.reference / "procedure.md").write_text("Changed")
        with self.assertRaises(AccessDenied):
            self.tools.propose_text(self.rw.id, "new.md", "Revision", self.ro.id,
                                    "procedure.md", source["sha256"])

    def test_incomplete_source_reference_denied(self):
        with self.assertRaises(AccessDenied):
            self.tools.propose_text(self.rw.id, "new.md", "Revision", source_folder=self.ro.id)

    def test_pending_proposal_limit(self):
        for index in range(8):
            self.workspace.propose(self.rw.id, f"draft-{index}.txt", "draft")
        with self.assertRaises(AccessDenied):
            self.workspace.propose(self.rw.id, "ninth.txt", "draft")

    def test_newline_only_change_visible_in_diff(self):
        source = self.workspace.open_text(self.ro.id, "procedure.md")
        proposal = self.workspace.propose(self.rw.id, "new.md", source.text.rstrip("\n"), source)
        self.assertIn("No newline at end of file", proposal.diff)
        self.assertIn("-Original procedure.", proposal.diff)
        self.assertIn("+Original procedure.", proposal.diff)

    def test_directory_listing_filters_forbidden_entries(self):
        (self.reference / "nested").mkdir()
        (self.reference / "link").symlink_to(self.drafts, target_is_directory=True)
        os.link(self.reference / "procedure.md", self.reference / "hard.md")
        os.mkfifo(self.reference / "pipe")
        result = self.tools.list_files(self.ro.id)
        self.assertEqual(result["entries"], [{"name": "nested", "kind": "directory"}])

    def test_listing_is_bounded_and_nested(self):
        (self.reference / "nested").mkdir()
        for index in range(4):
            (self.reference / "nested" / f"{index}.txt").write_text("text")
        result = self.workspace.broker.list_directory(self.ro.id, "nested", limit=2)
        self.assertEqual(len(result["entries"]), 2)
        self.assertTrue(result["truncated"])
        with self.assertRaises(AccessDenied):
            self.tools.list_files(self.ro.id, "../drafts")

    def test_repeated_directory_listing_is_stable(self):
        expected = self.tools.list_files(self.ro.id)
        for _ in range(3):
            self.assertEqual(self.tools.list_files(self.ro.id), expected)

    def test_binary_input_denied(self):
        (self.reference / "binary").write_bytes(b"\xff\xfe\x00")
        with self.assertRaises(AccessDenied):
            self.workspace.open_text(self.ro.id, "binary")


if __name__ == "__main__":
    unittest.main()
