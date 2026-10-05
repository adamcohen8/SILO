import hashlib
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from local_ai_appliance.bundle import BundleError, MANIFEST_NAME, parse_manifest, verify_bundle


def synthetic_manifest():
    artifacts = []
    for role, path in (("application", "app/app.txt"), ("runtime", "runtime/runtime.txt"),
                       ("model", "model/synthetic-model.txt")):
        data = ("Synthetic " + role).encode("utf-8")
        artifacts.append({"path": path, "role": role, "size": len(data),
                          "sha256": hashlib.sha256(data).hexdigest(), "version": "synthetic-1",
                          "license": "test-only", "source": "synthetic test bytes"})
    return {"format_version": 1, "bundle_id": "synthetic-test-1", "target": "windows-amd64", "artifacts": artifacts}


class ManifestTests(unittest.TestCase):
    def test_manifest_is_not_an_installer_or_runtime_configuration(self):
        result = parse_manifest(json.dumps(synthetic_manifest()).encode())
        self.assertEqual(result.bundle_id, "synthetic-test-1")
        self.assertEqual(len(result.artifacts), 3)

    def test_unknown_keys_versions_targets_and_incomplete_roles_denied(self):
        base = synthetic_manifest()
        variants = [base | {"command": "execute"}, base | {"format_version": True},
                    base | {"format_version": 2}, base | {"target": "other"}, base | {"bundle_id": "bad\n"},
                    base | {"artifacts": base["artifacts"][:2]}]
        for value in variants:
            with self.assertRaises(BundleError):
                parse_manifest(json.dumps(value).encode())

    def test_windows_unsafe_paths_and_manifest_self_reference_denied(self):
        for path in ("../model", "/model", "C:/model", "model:stream", "NUL.txt", "model.",
                     "model\\file", "bundle-manifest.json", "a//file"):
            value = synthetic_manifest()
            value["artifacts"][0]["path"] = path
            with self.subTest(path=path), self.assertRaises(BundleError):
                parse_manifest(json.dumps(value).encode())

    def test_duplicate_case_alias_and_file_directory_conflict_denied(self):
        for paths in (("a/file", "A/file", "b/file"), ("a/file", "A/other", "b/file"),
                      ("a", "a/child", "b/file")):
            value = synthetic_manifest()
            for item, path in zip(value["artifacts"], paths):
                item["path"] = path
            with self.assertRaises(BundleError):
                parse_manifest(json.dumps(value).encode())

    def test_payload_metadata_requires_strict_types_and_provenance(self):
        for key, value in (("size", True), ("size", 0), ("size", 129 * 1024**3),
                           ("sha256", "0" * 63), ("role", "shell"), ("license", ""),
                           ("version", None), ("source", "bad\nsource")):
            manifest = synthetic_manifest()
            manifest["artifacts"][0][key] = value
            with self.subTest(key=key), self.assertRaises(BundleError):
                parse_manifest(json.dumps(manifest).encode())

    def test_duplicate_json_and_excessive_manifest_denied(self):
        for data in (b'{"format_version":1,"format_version":1}', b"a" * (1024 * 1024 + 1)):
            with self.assertRaises(BundleError):
                parse_manifest(data)


@unittest.skipUnless(os.name == "posix", "POSIX payload verifier; Windows verifier pending")
class BundlePayloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="local-ai-bundle-synthetic-")
        self.root = Path(self.temp.name).resolve()
        self.manifest = synthetic_manifest()
        for artifact in self.manifest["artifacts"]:
            path = self.root / artifact["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("Synthetic " + artifact["role"]).encode())
        self.write_manifest()

    def tearDown(self):
        self.temp.cleanup()

    def write_manifest(self):
        data = json.dumps(self.manifest).encode()
        (self.root / MANIFEST_NAME).write_bytes(data)
        self.digest = hashlib.sha256(data).hexdigest()

    def test_valid_payload_never_grants_readiness_or_signature(self):
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Network attempted")):
            result = verify_bundle(self.root, self.digest)
        self.assertTrue(result["payload_integrity_verified"])
        self.assertFalse(result["deployment_ready"])
        self.assertFalse(result["signature_verified"])
        self.assertEqual(result["verified_artifacts"], 3)

    def test_untrusted_or_changed_manifest_denied(self):
        for digest in ("", "bad", "0" * 64):
            with self.assertRaises(BundleError):
                verify_bundle(self.root, digest)
        (self.root / MANIFEST_NAME).write_bytes(b"changed")
        with self.assertRaises(BundleError):
            verify_bundle(self.root, self.digest)

    def test_missing_size_changed_and_same_size_corruption_denied(self):
        path = self.root / self.manifest["artifacts"][0]["path"]
        original = path.read_bytes()
        for data in (b"short", b"x" * len(original)):
            path.write_bytes(data)
            with self.assertRaises(BundleError):
                verify_bundle(self.root, self.digest)
        path.unlink()
        with self.assertRaises(BundleError):
            verify_bundle(self.root, self.digest)

    def test_undeclared_files_and_empty_directories_denied(self):
        extra = self.root / "extra.txt"
        extra.write_bytes(b"extra")
        with self.assertRaises(BundleError):
            verify_bundle(self.root, self.digest)
        extra.unlink()
        (self.root / "empty").mkdir()
        with self.assertRaises(BundleError):
            verify_bundle(self.root, self.digest)

    def test_symlink_and_hardlink_payloads_denied(self):
        path = self.root / self.manifest["artifacts"][0]["path"]
        target = self.root / self.manifest["artifacts"][1]["path"]
        path.unlink()
        path.symlink_to(target)
        with self.assertRaises(BundleError):
            verify_bundle(self.root, self.digest)
        path.unlink()
        os.link(target, path)
        with self.assertRaises(BundleError):
            verify_bundle(self.root, self.digest)

    def test_symlink_ancestor_and_fifo_fail_without_hang(self):
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(BundleError):
            verify_bundle(alias, self.digest)
        alias.unlink()
        path = self.root / self.manifest["artifacts"][0]["path"]
        path.unlink()
        os.mkfifo(path)
        with self.assertRaises(BundleError):
            verify_bundle(self.root, self.digest)

    def test_windows_payload_verifier_fails_closed(self):
        with patch("local_ai_appliance.bundle.os.name", "nt"), self.assertRaises(BundleError):
            verify_bundle(self.root, self.digest)
