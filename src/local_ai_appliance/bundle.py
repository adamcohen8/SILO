"""Offline integrity prototype: no downloads, execution, or installation.

Expected manifest hashes must arrive through an independently trusted channel.
Signatures, Windows payload verification, and deployment readiness are pending.
"""

import argparse
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat

from .folders import AccessDenied
from .model import strict_json
from .windows_folders import parts


MANIFEST_NAME = "bundle-manifest.json"
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_PAYLOAD_BYTES = 128 * 1024**3
_HASH = re.compile(r"^[0-9a-f]{64}$")
_ROLES = {"application", "runtime", "model", "dependency", "parser-model", "embedding-model"}


class BundleError(ValueError):
    pass


@dataclass(frozen=True)
class Artifact:
    path: str
    role: str
    size: int
    sha256: str
    version: str
    license: str
    source: str


@dataclass(frozen=True)
class Manifest:
    bundle_id: str
    artifacts: tuple[Artifact, ...]


def parse_manifest(data: bytes) -> Manifest:
    if len(data) > MAX_MANIFEST_BYTES:
        raise BundleError("Manifest exceeds the configured limit")
    try:
        value = strict_json(data)
        if not isinstance(value, dict) or set(value) != {"format_version", "bundle_id", "target", "artifacts"}:
            raise ValueError()
        if type(value["format_version"]) is not int or value["format_version"] != 1:
            raise ValueError()
        if not isinstance(value["bundle_id"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", value["bundle_id"]):
            raise ValueError()
        if value["target"] != "windows-amd64":
            raise ValueError()
        items = value["artifacts"]
        if not isinstance(items, list) or not 3 <= len(items) <= 4096:
            raise ValueError()
        artifacts, prefixes, filenames = [], {}, set()
        for item in items:
            if not isinstance(item, dict) or set(item) != {"path", "role", "size", "sha256", "version", "license", "source"}:
                raise ValueError()
            components = parts(item["path"])
            if item["path"].casefold() == MANIFEST_NAME or item["role"] not in _ROLES:
                raise ValueError()
            if type(item["size"]) is not int or not 0 < item["size"] <= MAX_PAYLOAD_BYTES:
                raise ValueError()
            if not isinstance(item["sha256"], str) or not _HASH.fullmatch(item["sha256"]):
                raise ValueError()
            for key in ("version", "license", "source"):
                text = item[key]
                if (not isinstance(text, str) or not text.strip() or len(text) > 1024
                        or any(ord(c) < 32 or ord(c) == 127 for c in text)):
                    raise ValueError()
            folded = item["path"].casefold()
            if folded in filenames:
                raise ValueError()
            filenames.add(folded)
            for end in range(1, len(components) + 1):
                prefix = "/".join(components[:end])
                if prefixes.setdefault(prefix.casefold(), prefix) != prefix:
                    raise ValueError()
            artifacts.append(Artifact(**item))
        if not {"application", "runtime", "model"} <= {a.role for a in artifacts}:
            raise ValueError()
        for artifact in artifacts:
            components = artifact.path.split("/")
            if any("/".join(components[:end]).casefold() in filenames for end in range(1, len(components))):
                raise ValueError()
        return Manifest(value["bundle_id"], tuple(artifacts))
    except (ValueError, TypeError, KeyError, RecursionError) as e:
        raise BundleError("Manifest is malformed, incomplete, or contains unsafe/ambiguous paths") from e


def _root(path):
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise BundleError("Payload verifier is POSIX development only; Windows verification is pending")
    selected = Path(path)
    if not selected.is_absolute() or ".." in selected.parts or selected == Path(selected.anchor):
        raise BundleError("Select an absolute bundle directory without traversal")
    fd = os.open(selected.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in selected.parts[1:]:
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def _file(root, path, device):
    directories, fd = [os.dup(root)], None
    try:
        components = path.split("/")
        for component in components[:-1]:
            directories.append(os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directories[-1]))
            if os.fstat(directories[-1]).st_dev != device:
                raise BundleError("Cross-device bundle access is forbidden")
        fd = os.open(components[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directories[-1])
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_dev != device:
            raise BundleError("Bundle payload must be a regular single-link local file")
        result, fd = fd, None
        return result
    finally:
        if fd is not None:
            os.close(fd)
        for directory in reversed(directories):
            os.close(directory)


def _inventory(root, device, expected):
    seen, count = set(), 0
    directories = {"/".join(path.split("/")[:end]) for path in expected
                   for end in range(1, len(path.split("/")))}

    def visit(fd, prefix="", depth=0):
        nonlocal count
        if depth > 64:
            raise BundleError("Bundle directory depth exceeds the limit")
        with os.scandir(fd) as entries:
            for entry in entries:
                count += 1
                if count > 8192:
                    raise BundleError("Bundle inventory exceeds the limit")
                path = prefix + entry.name
                parts(path)
                info = entry.stat(follow_symlinks=False)
                if info.st_dev != device:
                    raise BundleError("Cross-device bundle content is forbidden")
                if stat.S_ISDIR(info.st_mode):
                    if path not in directories:
                        raise BundleError("Bundle contains an undeclared directory")
                    child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try:
                        if os.fstat(child).st_dev != device:
                            raise BundleError("Cross-device bundle content is forbidden")
                        visit(child, path + "/", depth + 1)
                    finally:
                        os.close(child)
                elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and path in expected:
                    seen.add(path)
                else:
                    raise BundleError("Bundle contains undeclared, linked, or unsupported content")
    visit(root)
    if seen != expected:
        raise BundleError("Bundle is missing declared payloads")


def verify_bundle(path, expected_manifest_sha256):
    if not isinstance(expected_manifest_sha256, str) or not _HASH.fullmatch(expected_manifest_sha256):
        raise BundleError("Supply a SHA-256 obtained through an independently trusted channel")
    root = None
    try:
        root = _root(path)
        device = os.fstat(root).st_dev
        with os.fdopen(_file(root, MANIFEST_NAME, device), "rb") as file:
            data = file.read(MAX_MANIFEST_BYTES + 1)
        if not hmac.compare_digest(hashlib.sha256(data).hexdigest(), expected_manifest_sha256):
            raise BundleError("Manifest does not match the independently supplied hash")
        manifest = parse_manifest(data)
        _inventory(root, device, {MANIFEST_NAME} | {a.path for a in manifest.artifacts})
        total = 0
        for artifact in manifest.artifacts:
            with os.fdopen(_file(root, artifact.path, device), "rb") as file:
                if os.fstat(file.fileno()).st_size != artifact.size:
                    raise BundleError("Payload size does not match the manifest")
                digest, size = hashlib.sha256(), 0
                while block := file.read(min(1024 * 1024, artifact.size + 1 - size)):
                    digest.update(block)
                    size += len(block)
                    if size > artifact.size:
                        raise BundleError("Payload grew while being verified")
                if size != artifact.size or not hmac.compare_digest(digest.hexdigest(), artifact.sha256):
                    raise BundleError("Payload digest does not match the manifest")
            total += artifact.size
        return {"bundle_id": manifest.bundle_id, "target": "windows-amd64",
                "manifest_sha256": expected_manifest_sha256, "verified_artifacts": len(manifest.artifacts),
                "verified_bytes": total, "payload_integrity_verified": True,
                "signature_verified": False, "deployment_ready": False}
    except (OSError, AccessDenied) as e:
        raise BundleError("Bundle content is unavailable or forbidden") from e
    finally:
        if root is not None:
            os.close(root)


def main():
    parser = argparse.ArgumentParser(description="Offline payload integrity check; does not install or grant readiness")
    parser.add_argument("bundle")
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify_bundle(args.bundle, args.manifest_sha256), indent=2))
        return 0
    except BundleError as e:
        print(json.dumps({"error": str(e), "deployment_ready": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
