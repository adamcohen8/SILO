"""Host-enforced publication types and administrator-selected storage roots."""
from pathlib import Path
import os
import secrets

from .asset_integrity import ordinary
from .folders import AccessDenied
from .security_events import identifier

DOCUMENT_TYPES = frozenset({'.txt', '.md', '.json', '.csv', '.docx', '.xlsx', '.pptx', '.patch'})
ACTIVE_TYPES = frozenset({'.py', '.cmd', '.bat', '.ps1', '.exe', '.com', '.dll', '.msi',
                         '.html', '.htm', '.svg', '.js', '.vbs', '.lnk', '.url', '.scr'})


def publication_path(path):
    from .windows_folders import parts
    components = parts(path)
    # Bidi controls can conceal the effective filename/type in a review dialog.
    if any(c in ''.join(components) for c in '\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069'):
        raise AccessDenied('Directional-control filenames cannot be published')


def document_destination(path):
    publication_path(path)
    if Path(path).suffix.lower() not in DOCUMENT_TYPES:
        raise AccessDenied('Drafts publish TXT, Markdown, JSON, CSV, DOCX, XLSX, PPTX or inert PATCH text; active files require separate code-export policy')


class StoragePolicy:
    def __init__(self, reference_roots, draft_roots, *, excluded_roots=(), allow_code_exports=False):
        self.reference_roots = tuple(Path(p).absolute() for p in reference_roots)
        self.draft_roots = tuple(Path(p).absolute() for p in draft_roots)
        self.excluded_roots = tuple(Path(p).absolute() for p in excluded_roots)
        self.allow_code_exports = allow_code_exports is True
        for root in (*self.reference_roots, *self.draft_roots, *self.excluded_roots):
            ordinary(root, directory=True)

    @staticmethod
    def contains(root, path):
        return path == root or root in path.parents

    def directory(self, path, access):
        path = Path(path).absolute()
        ordinary(path, directory=True)
        if any(self.contains(p, path) or self.contains(path, p) for p in self.excluded_roots):
            raise AccessDenied('Synchronization, private or excluded storage cannot be granted')
        roots = self.reference_roots if access == 'read-only' else self.draft_roots
        if not any(self.contains(root, path) for root in roots):
            raise AccessDenied('Folder is outside administrator-approved storage roots')
        return path

    def backup(self, path):
        path = Path(path).absolute()
        self.directory(path.parent, 'editable')
        if path.suffix.lower() != '.silo':
            raise AccessDenied('Encrypted backups use the .silo extension')
        return path


class SecurityBroker:
    """Wrap the native broker so desktop, terminal and direct tools share policy."""
    def __init__(self, broker, policy, audit, checkpoint=lambda: None):
        self.broker, self.policy, self.audit, self.checkpoint = broker, policy, audit, checkpoint

    def __getattr__(self, name):
        return getattr(self.broker, name)

    def _call(self, event, object_value, function):
        self.checkpoint()
        operation = secrets.token_hex(16)
        metadata = {'operation_id': operation, 'object_sha256': identifier(object_value),
                    'revision': self.broker.revision}
        self.audit.emit(event, 'attempt', **metadata)
        try:
            value = function()
            self.checkpoint()
        except Exception:
            self.audit.emit(event, 'denied', **metadata)
            raise
        self.audit.emit(event, 'success', **metadata)
        return value

    def grant(self, path, access, **kwargs):
        def grant():
            self.policy.directory(path, access)
            return self.broker.grant(path, access, **kwargs)
        return self._call('grant', path, grant)

    def revoke(self, folder_id):
        return self._call('revoke', folder_id, lambda: self.broker.revoke(folder_id))

    def read_file(self, folder_id, path):
        return self._call('read', (folder_id, path), lambda: self.broker.read_file(folder_id, path))

    def list_directory(self, folder_id, path='', **kwargs):
        return self._call('list', (folder_id, path), lambda: self.broker.list_directory(folder_id, path, **kwargs))

    def validate_create(self, folder_id, path):
        publication_path(path)
        if Path(path).suffix.lower() == '.zip':
            if not self.policy.allow_code_exports:
                raise AccessDenied('Administrator policy disables code artifact exports')
        else:
            document_destination(path)
        return self.broker.validate_create(folder_id, path)

    def write_file(self, folder_id, path, content):
        def write():
            self.validate_create(folder_id, path)
            return self.broker.write_file(folder_id, path, content)
        return self._call('save', (folder_id, path), write)


def encrypted_archive(path, security, *, data=None):
    """Host-only archive I/O; held ancestor handles prevent path redirection."""
    if os.name!='nt':raise AccessDenied('Managed archive I/O requires native Windows')
    from .windows_folders import WindowsFolderBroker
    security.check()
    path=security.storage.backup(path)
    event='restore' if data is None else 'backup'
    metadata={'operation_id':secrets.token_hex(16),'object_sha256':identifier(path)}
    security.audit.emit(event,'attempt',**metadata)
    broker=WindowsFolderBroker(validation_mode=True)
    # Host-only encrypted archives have their existing 64 MiB bound. Document
    # tools retain the separate 8 MiB bound and never receive this broker.
    broker.max_file_bytes=64*1024*1024+54
    try:
        folder=broker.grant(path.parent,'read-only' if data is None else 'editable')
        value=broker.read_file(folder.id,path.name) if data is None else broker.write_file(folder.id,path.name,data)
        security.check()
    except Exception:
        security.audit.emit(event,'failed',**metadata)
        raise
    finally:broker.close()
    security.audit.emit(event,'success',**metadata)
    return value
