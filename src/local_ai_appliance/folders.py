"""Descriptor-based folder tools for the POSIX development prototype.

No network, shell, or permission-management tools are exposed to the model.
This adapter deliberately fails closed on Windows. The separate native Windows
candidate requires explicit synthetic validation until target acceptance passes.
"""

from __future__ import annotations

import errno
import os
from pathlib import Path
import secrets
import stat
import threading
from dataclasses import dataclass
from typing import Literal


class AccessDenied(ValueError):
    """The request cannot be performed within a granted capability."""


@dataclass(frozen=True)
class Folder:
    id: str
    name: str
    access: Literal["read-only", "editable"]


@dataclass
class _Grant:
    folder: Folder
    path: Path
    fd: int
    device: int


def _parts(path: str) -> list[str]:
    if not isinstance(path, str) or not path or len(path) > 4096:
        raise AccessDenied("A bounded relative file path is required")
    if any(ord(c) < 32 or ord(c) == 127 for c in path) or "\\" in path or ":" in path:
        raise AccessDenied("Unsupported path syntax")
    parts = path.split("/")
    if len(parts) > 64 or any(p in {"", ".", ".."} for p in parts):
        raise AccessDenied("Only relative paths without traversal are allowed")
    if any(p.startswith(".local-ai-write-") for p in parts):
        raise AccessDenied("Internal temporary filenames are reserved")
    return parts


class FolderBroker:
    """Host-owned permissions. Never give this object directly to a model.

    All grants are in memory. Restarting starts with zero grants. POSIX directory
    descriptors anchor access to the selected directory, rather than resolving
    user-controlled absolute paths on every request. Calls are serialized so
    revoke returns only after preceding operations finish.
    """

    def __init__(self, *, max_file_bytes: int = 8 * 1024 * 1024):
        if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
            raise RuntimeError("Qualified Windows folder adapter is unavailable; access denied")
        if max_file_bytes <= 0:
            raise ValueError("max_file_bytes must be positive")
        self._grants: dict[str, _Grant] = {}
        self._lock = threading.RLock()
        self.max_file_bytes = max_file_bytes
        self.revision = 0

    def grant(self, path: Path | str, access: str, *, expected_identity=None) -> Folder:
        """Called only by trusted host UI after an explicit user folder selection."""
        if access not in {"read-only", "editable"}:
            raise AccessDenied("Unknown access mode")
        selected = Path(path)
        if not selected.is_absolute() or ".." in selected.parts:
            raise AccessDenied("Select an absolute local directory")
        if selected == Path(selected.anchor):
            raise AccessDenied("Whole-filesystem grants are forbidden")
        with self._lock:
            for g in self._grants.values():
                if selected == g.path or selected.is_relative_to(g.path) or g.path.is_relative_to(selected):
                    raise AccessDenied("Overlapping folder grants are forbidden")
            fd = os.open(selected.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                for part in selected.parts[1:]:
                    next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    os.close(fd)
                    fd = next_fd
                info = os.fstat(fd)
                if expected_identity is not None and expected_identity != (info.st_dev, info.st_ino):
                    raise AccessDenied("Saved folder identity changed; select it again explicitly")
                if any((info.st_dev, info.st_ino) == (os.fstat(g.fd).st_dev, os.fstat(g.fd).st_ino)
                       for g in self._grants.values()):
                    raise AccessDenied("Directory already granted")
                folder = Folder(secrets.token_hex(16), selected.name, access)
                self._grants[folder.id] = _Grant(folder, selected, fd, info.st_dev)
                fd = -1
                self.revision += 1
                return folder
            except OSError as e:
                raise AccessDenied("Folder must exist without symbolic-link ancestors") from e
            finally:
                if fd >= 0:
                    os.close(fd)

    def revoke(self, folder_id: str) -> None:
        with self._lock:
            g = self._grants.pop(folder_id, None)
            if g is None:
                raise AccessDenied("Unknown folder")
            os.close(g.fd)
            self.revision += 1

    def folders(self) -> list[Folder]:
        with self._lock:
            return [g.folder for g in self._grants.values()]

    def saved_grants(self):
        """Host-only persistence metadata; never returned to model tools."""
        with self._lock:
            return [dict(path=str(g.path), access=g.folder.access,
                         volume=os.fstat(g.fd).st_dev, index=os.fstat(g.fd).st_ino)
                    for g in self._grants.values()]

    def close(self) -> None:
        with self._lock:
            for g in self._grants.values():
                os.close(g.fd)
            self._grants.clear()
            self.revision += 1

    def _get(self, folder_id: str, write: bool = False) -> _Grant:
        g = self._grants.get(folder_id)
        if g is None:
            raise AccessDenied("Unknown or revoked folder")
        if write and g.folder.access != "editable":
            raise AccessDenied("Folder is read-only")
        return g

    def _parent(self, g: _Grant, parts: list[str]) -> int:
        fd = os.dup(g.fd)
        try:
            for part in parts[:-1]:
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                if os.fstat(next_fd).st_dev != g.device:
                    os.close(next_fd)
                    raise AccessDenied("Cross-device access is forbidden")
                os.close(fd)
                fd = next_fd
            return fd
        except (OSError, AccessDenied) as e:
            os.close(fd)
            raise AccessDenied("Parent directory is unavailable or forbidden") from e

    def _check_file(self, g: _Grant, info: os.stat_result) -> None:
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_dev != g.device:
            raise AccessDenied("Only regular, single-link files on the granted device are allowed")
        if info.st_size > self.max_file_bytes:
            raise AccessDenied("File exceeds the configured size limit")

    def read_file(self, folder_id: str, relative_path: str) -> bytes:
        parts = _parts(relative_path)
        with self._lock:
            g = self._get(folder_id)
            parent = self._parent(g, parts)
            fd = -1
            try:
                # NONBLOCK prevents FIFO/device opens from hanging before type validation.
                fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                self._check_file(g, os.fstat(fd))
                with os.fdopen(fd, "rb") as file:
                    fd = -1
                    data = file.read(self.max_file_bytes + 1)
                if len(data) > self.max_file_bytes:
                    raise AccessDenied("File exceeds the configured size limit")
                return data
            except OSError as e:
                raise AccessDenied("File is unavailable or forbidden") from e
            finally:
                if fd >= 0:
                    os.close(fd)
                os.close(parent)

    def list_directory(self, folder_id: str, relative_path: str = "", *, limit: int = 250) -> dict:
        """List a bounded directory through the same descriptor-based boundary."""
        if not 1 <= limit <= 1000:
            raise AccessDenied("Invalid listing limit")
        parts = _parts(relative_path) if relative_path else []
        with self._lock:
            g = self._get(folder_id)
            parent = self._parent(g, parts + ["listing"])
            try:
                # A new open-file description avoids sharing directory offsets
                # with the capability descriptor during repeated scandir calls.
                fd = os.open(".", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            except OSError as e:
                raise AccessDenied("Directory is unavailable or forbidden") from e
            finally:
                os.close(parent)
            try:
                entries = []
                scanned = 0
                truncated = False
                with os.scandir(fd) as directory:
                    for entry in directory:
                        scanned += 1
                        if scanned > 5000:
                            truncated = True
                            break
                        try:
                            _parts(entry.name)
                            info = entry.stat(follow_symlinks=False)
                            if info.st_dev != g.device:
                                continue
                            if stat.S_ISDIR(info.st_mode):
                                kind = "directory"
                            elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                                kind = "file"
                            else:
                                continue
                            entries.append({"name": entry.name, "kind": kind})
                            if len(entries) > limit:
                                truncated = True
                                break
                        except (OSError, AccessDenied):
                            continue
                entries.sort(key=lambda e: (e["kind"] != "directory", e["name"].casefold()))
                return {"entries": entries[:limit], "truncated": truncated}
            except OSError as e:
                raise AccessDenied("Directory is unavailable or forbidden") from e
            finally:
                os.close(fd)

    def validate_create(self, folder_id: str, relative_path: str) -> None:
        """Check a proposed destination without creating or modifying anything."""
        parts = _parts(relative_path)
        with self._lock:
            g = self._get(folder_id, write=True)
            parent = self._parent(g, parts)
            try:
                try:
                    os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    return
                raise AccessDenied("Choose a new filename; existing files are preserved")
            except OSError as e:
                raise AccessDenied("Destination is unavailable or forbidden") from e
            finally:
                os.close(parent)

    def write_file(self, folder_id: str, relative_path: str, content: bytes) -> None:
        """Create a new file. Existing files cannot be overwritten by model tools.

        Atomic publication with link() refuses existing destinations even if they
        appear during the operation. Existing-file editing will require a separate
        host-owned approval and version check in a later iteration.
        """
        parts = _parts(relative_path)
        if not isinstance(content, bytes) or len(content) > self.max_file_bytes:
            raise AccessDenied("Invalid content or file too large")
        with self._lock:
            g = self._get(folder_id, write=True)
            parent = self._parent(g, parts)
            temp_name = ".local-ai-write-" + secrets.token_hex(16)
            created = False
            try:
                try:
                    os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise AccessDenied("Existing files require host-approved editing")
                fd = os.open(temp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=parent)
                created = True
                with os.fdopen(fd, "wb") as file:
                    file.write(content)
                    file.flush()
                    os.fsync(file.fileno())
                os.link(temp_name, parts[-1], src_dir_fd=parent, dst_dir_fd=parent,
                        follow_symlinks=False)
                os.unlink(temp_name, dir_fd=parent)
                created = False
                os.fsync(parent)
            except OSError as e:
                if e.errno == errno.EEXIST:
                    raise AccessDenied("Destination already exists") from e
                raise AccessDenied("Write could not be completed") from e
            finally:
                if created:
                    os.unlink(temp_name, dir_fd=parent)
                os.close(parent)


class DocumentTools:
    """The complete first model tool surface. No grant, revoke, shell, or HTTP."""

    def __init__(self, broker: FolderBroker):
        self.__broker = broker

    def list_folders(self) -> list[dict[str, str]]:
        return [{"id": f.id, "name": f.name, "access": f.access}
                for f in self.__broker.folders()]

    def read_text(self, folder_id: str, relative_path: str) -> str:
        return self.__broker.read_file(folder_id, relative_path).decode("utf-8")

    def create_text(self, folder_id: str, relative_path: str, text: str) -> dict[str, str]:
        if not isinstance(text, str):
            raise AccessDenied("Text is required")
        self.__broker.write_file(folder_id, relative_path, text.encode("utf-8"))
        return {"status": "created", "folder_id": folder_id, "path": relative_path}
