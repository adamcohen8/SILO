"""In-memory draft review. Source files are never overwritten.

Only the trusted host can approve a stored proposal. The model receives the
DraftTools facade, which cannot grant access, approve a write, or execute code.
"""

from dataclasses import dataclass
import difflib
import hashlib
from pathlib import Path
import secrets
import threading

from .folders import AccessDenied, Folder, FolderBroker
from .documents import parse_document


@dataclass(frozen=True)
class TextSource:
    folder_id: str
    path: str
    text: str
    sha256: str
    format: str = "text"


@dataclass(frozen=True)
class Proposal:
    id: str
    destination_folder: str
    destination_path: str
    text: str
    source: TextSource | None
    permission_revision: int
    diff: str


class Workspace:
    def __init__(self, broker: FolderBroker | None = None, *, windows_parser_validation=False):
        self.broker = broker if broker is not None else FolderBroker(max_file_bytes=1024 * 1024)
        self._pending: dict[str, Proposal] = {}
        self._lock = threading.RLock()
        self._windows_parser_validation = windows_parser_validation

    def grant(self, path: Path | str, access: str) -> Folder:
        with self._lock:
            folder = self.broker.grant(path, access)
            self._pending.clear()
            return folder

    def revoke(self, folder_id: str) -> None:
        with self._lock:
            self.broker.revoke(folder_id)
            self._pending.clear()

    def open_text(self, folder_id: str, relative_path: str) -> TextSource:
        with self._lock:
            data = self.broker.read_file(folder_id, relative_path)
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError as e:
                raise AccessDenied("Use read_document for PDF/DOCX; read_text requires UTF-8") from e
            return TextSource(folder_id, relative_path, text, hashlib.sha256(data).hexdigest())

    def open_document(self, folder_id, relative_path):
        with self._lock:
            data = self.broker.read_file(folder_id, relative_path)
            return parse_document(folder_id, relative_path, data,
                                  windows_validation=self._windows_parser_validation)

    def open_source(self, folder_id, relative_path):
        if Path(relative_path).suffix.lower() not in {".pdf", ".docx"}:
            return self.open_text(folder_id, relative_path)
        document = self.open_document(folder_id, relative_path)
        return TextSource(folder_id, relative_path, "\n".join(document.units), document.sha256, document.format)

    def propose(self, destination_folder: str, destination_path: str, text: str,
                source: TextSource | None = None) -> Proposal:
        with self._lock:
            if not isinstance(text, str) or len(text.encode("utf-8")) > self.broker.max_file_bytes:
                raise AccessDenied("Draft exceeds the configured size limit")
            if len(self._pending) >= 8:
                raise AccessDenied("Review or discard existing proposals first")
            self.broker.validate_create(destination_folder, destination_path)
            if source is not None:
                # Re-read rather than trusting caller-supplied source text or digest.
                current = self.open_source(source.folder_id, source.path)
                if current.sha256 != source.sha256 or current.text != source.text:
                    raise AccessDenied("Source changed; reopen it before reviewing a revision")
                source = current
            original = source.text if source else ""
            lines = difflib.unified_diff(original.splitlines(keepends=True), text.splitlines(keepends=True),
                                         fromfile=source.path if source else "(new document)",
                                         tofile=destination_path, lineterm="\n")
            diff = "".join(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
                           for line in lines)
            proposal = Proposal(secrets.token_hex(16), destination_folder, destination_path,
                                text, source, self.broker.revision, diff)
            self._pending[proposal.id] = proposal
            return proposal

    def discard(self, proposal_id: str) -> None:
        with self._lock:
            self._pending.pop(proposal_id, None)

    def pending_proposals(self) -> tuple[Proposal, ...]:
        """Trusted host inspection; deliberately absent from the model tools."""
        with self._lock:
            return tuple(self._pending.values())

    def approve(self, proposal_id: str) -> Proposal:
        """Trusted host action, not an agent tool. Applies exactly the reviewed bytes."""
        with self._lock:
            proposal = self._pending.pop(proposal_id, None)
            if proposal is None:
                raise AccessDenied("Proposal is unavailable, invalidated, or already used")
            if proposal.permission_revision != self.broker.revision:
                raise AccessDenied("Folder permissions changed; review again")
            if proposal.source is not None:
                current = self.open_source(proposal.source.folder_id, proposal.source.path)
                if current.sha256 != proposal.source.sha256:
                    raise AccessDenied("Source changed since review; reopen and review again")
            self.broker.write_file(proposal.destination_folder, proposal.destination_path,
                                   proposal.text.encode("utf-8"))
            return proposal

    def close(self) -> None:
        with self._lock:
            self._pending.clear()
            self.broker.close()


class DraftTools:
    """Tool surface for the agent. Writes require trusted host review."""

    def __init__(self, workspace: Workspace):
        self.__workspace = workspace

    def list_folders(self) -> list[dict[str, str]]:
        return [{"id": f.id, "name": f.name, "access": f.access}
                for f in self.__workspace.broker.folders()]

    def list_files(self, folder_id: str, path: str = "") -> dict:
        return self.__workspace.broker.list_directory(folder_id, path)

    def read_text(self, folder_id: str, path: str) -> dict[str, str]:
        source = self.__workspace.open_text(folder_id, path)
        return {"text": source.text, "sha256": source.sha256}

    def propose_text(self, destination_folder: str, destination_path: str, text: str,
                     source_folder: str | None = None, source_path: str | None = None,
                     source_sha256: str | None = None) -> dict[str, str]:
        source = None
        if any(v is not None for v in (source_folder, source_path, source_sha256)):
            if not all(isinstance(v, str) and v for v in (source_folder, source_path, source_sha256)):
                raise AccessDenied("A complete source reference and digest are required")
            source = self.__workspace.open_source(source_folder, source_path)
            if source.sha256 != source_sha256:
                raise AccessDenied("Source changed since it was read")
        proposal = self.__workspace.propose(destination_folder, destination_path, text, source)
        return {"proposal_id": proposal.id, "status": "awaiting_user_review"}
