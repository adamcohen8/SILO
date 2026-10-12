"""Handle-based Windows broker candidate, disabled without a validation opt-in.

Initial Windows tests are recorded in docs/TARGET-SESSION-2026-10-06.md.
It must not be selected by the ordinary application or installer before full
native target acceptance is complete.
"""

from contextlib import contextmanager
from dataclasses import dataclass
import re
import secrets
import threading

from .folders import AccessDenied, Folder
from .windows_native import Info, NativeFiles


_RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9¹²³]|LPT[1-9¹²³])(?:\.|$)", re.I)


def parts(path):
    if not isinstance(path, str) or not path or len(path) > 4096:
        raise AccessDenied("A bounded relative path is required")
    result = path.split("/")
    if len(result) > 64:
        raise AccessDenied("Path nesting exceeds the limit")
    for component in result:
        if (not component or component in {".", ".."} or component[-1] in {".", " "}
                or any(ord(c) < 32 or ord(c) == 127 or c in '\\:<>"|?*' for c in component)
                or _RESERVED.match(component.split(".", 1)[0].rstrip(" "))
                or component.casefold().startswith(".local-ai-write-")):
            raise AccessDenied("Unsupported Windows path component")
        try:
            if len(component.encode("utf-16-le")) > 510:
                raise AccessDenied("Windows filename exceeds the limit")
        except UnicodeError as e:
            raise AccessDenied("Invalid Unicode filename") from e
    return result


def selected_path(path):
    path = str(path)
    if not re.match(r"^[A-Za-z]:[\\/]", path):
        raise AccessDenied("Select an absolute directory on a fixed local drive")
    components = parts(path[3:].replace("\\", "/"))
    return path[0].upper() + ":\\", components


@dataclass
class _Grant:
    folder: Folder
    handles: tuple
    info: Info
    canonical: str
    lineage: tuple
    path: str


class FolderOverlap(AccessDenied):
    """Trusted host can offer replacement of these exact existing grants."""
    def __init__(self, folder_ids):
        super().__init__('Overlapping or aliased folder grants are forbidden')
        self.folder_ids = tuple(folder_ids)


class WindowsFolderBroker:
    def __init__(self, *, validation_mode=False, max_file_bytes=8 * 1024 * 1024, native=None):
        if validation_mode is not True:
            raise RuntimeError("Windows candidate is unqualified; explicit synthetic validation mode required")
        if type(max_file_bytes) is not int or not 0 < max_file_bytes <= 8 * 1024 * 1024:
            raise ValueError("Invalid file size limit")
        self._native = native if native is not None else NativeFiles()
        self.max_file_bytes, self.revision = max_file_bytes, 0
        self._grants = {}
        self._reserved = []
        self._lock = threading.RLock()

    def _check(self, handle, *, volume=None, directory=None):
        info = self._native.info(handle)
        if not info.disk or info.reparse or info.offline or (volume is not None and info.volume != volume):
            raise AccessDenied("Only local non-reparse disk objects on the granted volume are allowed")
        if directory is not None and info.directory != directory:
            raise AccessDenied("Unexpected file type")
        if not info.directory and (info.links != 1 or info.size > self.max_file_bytes):
            raise AccessDenied("Only bounded single-link files are allowed")
        return info

    def grant(self, path, access, *, expected_identity=None):
        if access not in {"read-only", "editable"}:
            raise AccessDenied("Unknown access mode")
        drive, components = selected_path(path)
        with self._lock:
            handles = []
            try:
                handles.append(self._native.open_drive(drive))
                info = self._check(handles[-1], directory=True)
                lineage = [(info.volume, info.index)]
                if self._native.filesystem(handles[-1]).upper() != "NTFS":
                    raise AccessDenied("This candidate requires a fixed local NTFS volume")
                for component in components:
                    handles.append(self._native.open_child(handles[-1], component, directory=True))
                    info = self._check(handles[-1], volume=info.volume, directory=True)
                    lineage.append((info.volume, info.index))
                canonical = self._native.canonical(handles[-1]).rstrip("\\").casefold()
                if not re.match(r"^\\\\\?\\volume\{[0-9a-f-]{36}\}\\.+", canonical):
                    raise AccessDenied("A canonical local volume directory is required")
                if expected_identity is not None and expected_identity != (info.volume, info.index):
                    raise AccessDenied('Saved folder was replaced; select it again to grant access')
                for reserved in self._reserved:
                    if ((info.volume, info.index) in reserved.lineage
                            or (reserved.info.volume, reserved.info.index) in lineage
                            or canonical == reserved.canonical
                            or canonical.startswith(reserved.canonical + "\\")
                            or reserved.canonical.startswith(canonical + "\\")):
                        raise AccessDenied('Application private storage cannot be granted to the model')
                conflicts = []
                for grant in self._grants.values():
                    if (canonical == grant.canonical or canonical.startswith(grant.canonical + "\\")
                            or grant.canonical.startswith(canonical + "\\")
                            or (info.volume, info.index) in grant.lineage
                            or (grant.info.volume, grant.info.index) in lineage):
                        conflicts.append(grant.folder.id)
                if conflicts:
                    raise FolderOverlap(conflicts)
                folder = Folder(secrets.token_hex(16), components[-1], access)
                self._grants[folder.id] = _Grant(folder, tuple(handles), info, canonical, tuple(lineage),
                                                drive+'\\'.join(components))
                handles = []
                self.revision += 1
                return folder
            except OSError as e:
                raise AccessDenied("Folder is unavailable or forbidden") from e
            finally:
                for handle in reversed(handles):
                    self._native.close(handle)

    def reserve_tree(self, path):
        """Host-only reservation, using native identity and ancestry, including aliases."""
        with self._lock:
            temporary = WindowsFolderBroker(validation_mode=True, native=self._native,
                                            max_file_bytes=self.max_file_bytes)
            try:
                folder = temporary.grant(path, 'read-only')
                reserved = temporary._grants[folder.id]
                for grant in self._grants.values():
                    if ((grant.info.volume, grant.info.index) in reserved.lineage
                            or (reserved.info.volume, reserved.info.index) in grant.lineage):
                        raise AccessDenied('Remove existing overlapping grants before reserving storage')
                self._reserved.append(reserved)
            finally:
                temporary.close()

    def folders(self):
        with self._lock:
            return [grant.folder for grant in self._grants.values()]

    def saved_grants(self):
        """Trusted host settings only; never exposed as a document tool."""
        with self._lock:
            return [{'path': grant.path, 'access': grant.folder.access,
                     'volume': grant.info.volume, 'index': grant.info.index}
                    for grant in self._grants.values()]

    def revoke(self, folder_id):
        with self._lock:
            grant = self._grants.pop(folder_id, None)
            if grant is None:
                raise AccessDenied("Unknown folder")
            for handle in reversed(grant.handles):
                self._native.close(handle)
            self.revision += 1

    def close(self):
        with self._lock:
            for folder_id in tuple(self._grants):
                self.revoke(folder_id)
            self.revision += 1

    def _get(self, folder_id, *, write=False):
        grant = self._grants.get(folder_id)
        if grant is None:
            raise AccessDenied("Unknown or revoked folder")
        if write and grant.folder.access != "editable":
            raise AccessDenied("Folder is read-only")
        return grant

    @contextmanager
    def _directory(self, grant, components, *, create=False):
        opened = []
        current = grant.handles[-1]
        try:
            self._check(current, volume=grant.info.volume, directory=True)
            for component in components:
                try: current = self._native.open_child(current, component, directory=True)
                except FileNotFoundError:
                    if not create: raise
                    current = self._native.open_child(current, component, directory=True,create=True)
                opened.append(current)
                self._check(current, volume=grant.info.volume, directory=True)
            yield current
        finally:
            for handle in reversed(opened):
                self._native.close(handle)

    def describe_path(self, folder_id, relative_path):
        """Host mention validation using metadata only; no file contents."""
        components = parts(relative_path)
        with self._lock:
            grant = self._get(folder_id)
            child = None
            try:
                with self._directory(grant, components[:-1]) as parent:
                    child = self._native.open_child(parent, components[-1])
                    info = self._check(child, volume=grant.info.volume)
                    return 'directory' if info.directory else 'file'
            except OSError as error:
                raise AccessDenied('The referenced file or folder is unavailable or forbidden.') from error
            finally:
                if child is not None:
                    self._native.close(child)

    def read_file(self, folder_id, relative_path):
        components = parts(relative_path)
        with self._lock:
            grant = self._get(folder_id)
            handle, metadata = None, None
            try:
                with self._directory(grant, components[:-1]) as parent:
                    metadata = self._native.open_child(parent, components[-1], directory=False)
                    expected = self._check(metadata, volume=grant.info.volume, directory=False)
                    handle = self._native.open_read(metadata)
                    actual = self._check(handle, volume=grant.info.volume, directory=False)
                    if (actual.volume, actual.index) != (expected.volume, expected.index):
                        raise AccessDenied("File identity changed before reading")
                    data = self._native.read(handle, self.max_file_bytes)
                    self._check(handle, volume=grant.info.volume, directory=False)
                    if len(data) > self.max_file_bytes:
                        raise AccessDenied("File exceeds the configured size limit")
                    return data
            except OSError as e:
                raise AccessDenied("File is unavailable or forbidden") from e
            finally:
                if handle is not None:
                    self._native.close(handle)
                if metadata is not None:
                    self._native.close(metadata)

    def list_directory(self, folder_id, relative_path="", *, limit=250, strict=False):
        if type(strict) is not bool:raise AccessDenied('Invalid strict inventory selection')
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise AccessDenied("Invalid listing limit")
        components = parts(relative_path) if relative_path else []
        with self._lock:
            grant = self._get(folder_id)
            entries, truncated = [], False
            try:
                with self._directory(grant, components) as parent:
                    # Native query restarts its cursor; the broker lock serializes listings.
                    for index, name in enumerate(self._native.names(parent)):
                        if name in {'.','..'}:continue
                        if index >= 5000:
                            truncated = True
                            break
                        child = None
                        try:
                            parts(name)
                            child = self._native.open_child(parent, name)
                            info = self._check(child, volume=grant.info.volume)
                            entries.append({"name": name, "kind": "directory" if info.directory else "file"})
                            if len(entries) > limit:
                                truncated = True
                                break
                        except (OSError, AccessDenied):
                            if strict:raise AccessDenied('Strict inventory contains a forbidden entry') from None
                            continue
                        finally:
                            if child is not None:
                                self._native.close(child)
            except OSError as e:
                raise AccessDenied("Directory is unavailable or forbidden") from e
            entries.sort(key=lambda entry: (entry["kind"] != "directory", entry["name"].casefold()))
            return {"entries": entries[:limit], "truncated": truncated}

    def _absent(self, parent, name):
        handle = None
        try:
            handle = self._native.open_child(parent, name)
        except FileNotFoundError:
            return
        finally:
            if handle is not None:
                self._native.close(handle)
        raise AccessDenied("Choose a new filename; existing destinations are preserved")

    def apply_reviewed_change(self,folder_id,path,before,after,*,journal=None):
        from .reviewed_mutation import windows_change
        return windows_change(self,folder_id,path,before,after,journal=journal)

    def reconcile_reviewed_artifacts(self,folder_id,path,before,after,artifacts):
        from .reviewed_mutation import windows_reconcile
        return windows_reconcile(self,folder_id,path,before,after,artifacts)

    def validate_create(self, folder_id, relative_path):
        components = parts(relative_path)
        with self._lock:
            grant = self._get(folder_id, write=True)
            try:
                with self._directory(grant, components[:-1]) as parent:
                    self._absent(parent, components[-1])
            except OSError as e:
                raise AccessDenied("Destination is unavailable or forbidden") from e

    def write_file(self, folder_id, relative_path, content):
        components = parts(relative_path)
        if not isinstance(content, bytes) or len(content) > self.max_file_bytes:
            raise AccessDenied("Invalid content or file too large")
        with self._lock:
            grant = self._get(folder_id, write=True)
            handle, published = None, False
            try:
                with self._directory(grant, components[:-1]) as parent:
                    self._absent(parent, components[-1])
                    handle = self._native.open_child(parent, ".local-ai-write-" + secrets.token_hex(16),
                                                     directory=False, create=True)
                    self._check(handle, volume=grant.info.volume, directory=False)
                    self._native.write(handle, content)
                    self._check(handle, volume=grant.info.volume, directory=False)
                    self._native.publish(handle, parent, components[-1])
                    published = True
            except OSError as e:
                raise AccessDenied("New file could not be published; existing destinations are preserved") from e
            finally:
                if handle is not None:
                    try:
                        if not published:
                            self._native.discard(handle)
                    finally:
                        self._native.close(handle)
