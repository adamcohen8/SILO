"""Native, text-only folder-workspace prototype. No model or network transport."""

from pathlib import Path, PurePosixPath
import html
import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QPlainTextEdit, QPushButton,
    QSplitter, QVBoxLayout, QWidget,
)

from .folders import AccessDenied
from .workspace import Proposal, TextSource, Workspace


def label(text: str, name: str = "") -> QLabel:
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setObjectName(name)
    widget.setWordWrap(True)
    return widget


def local_drop_paths(mime) -> list[str]:
    """Only explicit local folder URLs; reject remote/ambiguous URLs as a group."""
    if not mime.hasUrls() or not 1 <= len(mime.urls()) <= 16:
        return []
    paths = []
    for url in mime.urls():
        if not url.isLocalFile() or url.host() or url.hasQuery() or url.hasFragment():
            return []
        path = url.toLocalFile()
        if not path or not Path(path).is_dir():
            return []
        paths.append(path)
    return paths


class FolderZone(QFrame):
    added = Signal(str, str)
    selected = Signal(str)
    removed = Signal(str)

    def __init__(self, title: str, access: str, description: str):
        super().__init__()
        self.access = access
        self.setObjectName("folderZone")
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(label(title, "sectionTitle"))
        layout.addWidget(label(description, "muted"))
        self.empty = label("Drop folders here\nor choose Add folder", "dropHint")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty)
        self.list = QListWidget()
        self.list.setMinimumHeight(80)
        self.list.setMaximumHeight(150)
        self.list.setAcceptDrops(False)
        self.list.viewport().setAcceptDrops(False)
        self.list.currentItemChanged.connect(self._selection)
        layout.addWidget(self.list)
        buttons = QHBoxLayout()
        add = QPushButton("Add folder")
        add.clicked.connect(self._pick)
        buttons.addWidget(add)
        self.remove = QPushButton("Remove")
        self.remove.setEnabled(False)
        self.remove.clicked.connect(self._remove)
        buttons.addWidget(self.remove)
        layout.addLayout(buttons)

    def _pick(self):
        path = QFileDialog.getExistingDirectory(self, "Choose a " + self.access + " folder")
        if path:
            self.added.emit(path, self.access)

    def _selection(self, item, previous):
        self.remove.setEnabled(item is not None)
        if item is not None:
            self.selected.emit(item.data(Qt.ItemDataRole.UserRole))

    def _remove(self):
        item = self.list.currentItem()
        if item is not None:
            self.removed.emit(item.data(Qt.ItemDataRole.UserRole))

    def add(self, folder, path: str):
        item = QListWidgetItem(folder.name)
        item.setToolTip("<pre>" + html.escape(path) + "</pre>")
        item.setData(Qt.ItemDataRole.UserRole, folder.id)
        self.list.addItem(item)
        self.empty.hide()

    def remove_id(self, folder_id: str):
        for index in range(self.list.count()):
            if self.list.item(index).data(Qt.ItemDataRole.UserRole) == folder_id:
                self.list.takeItem(index)
                break
        self.empty.setVisible(self.list.count() == 0)

    def dragEnterEvent(self, event):
        if local_drop_paths(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = local_drop_paths(event.mimeData())
        if paths:
            for path in paths:
                self.added.emit(path, self.access)
            event.acceptProposedAction()


class WorkspaceWindow(QMainWindow):
    def __init__(self, workspace: Workspace | None = None):
        super().__init__()
        self.workspace = workspace if workspace is not None else Workspace()
        self.folder_id = None
        self.directory = ""
        self.source: TextSource | None = None
        self.proposal: Proposal | None = None
        self.setWindowTitle("Local AI Appliance — Folder workspace")
        self.setFont(QFont("Arial", 11))
        self.resize(1320, 920)
        self.setMinimumSize(1060, 760)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(24, 20, 24, 16)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(label("Local AI Appliance", "appTitle"))
        titles.addWidget(label("Your folders. Your permissions. Review before saving.", "muted"))
        header.addLayout(titles)
        header.addStretch()
        header.addWidget(label("DEVELOPMENT PREVIEW\nModel not connected", "badge"))
        outer.addLayout(header)
        outer.addSpacing(12)
        split = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(split, 1)

        sidebar = QWidget()
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 0, 14, 0)
        side.addWidget(label("Folder access", "paneTitle"))
        side.addWidget(label("No folders are shared until you add them.", "muted"))
        self.read_only = FolderZone("READ-ONLY", "read-only", "Read and reference. Source files stay unchanged.")
        self.editable = FolderZone("EDITABLE", "editable", "Read sources and save reviewed drafts here.")
        for zone in (self.read_only, self.editable):
            zone.added.connect(self.add_folder)
            zone.selected.connect(self.select_folder)
            zone.removed.connect(self.revoke_folder)
            side.addWidget(zone)
        side.addStretch()
        side.addWidget(label("Access lasts for this session. Removing a folder clears the open preview and pending draft.", "muted"))
        split.addWidget(sidebar)

        source_panel = QWidget()
        source_layout = QVBoxLayout(source_panel)
        source_layout.setContentsMargins(8, 0, 12, 0)
        source_layout.addWidget(label("Source document", "paneTitle"))
        navigation = QHBoxLayout()
        self.location = label("Choose an allowed folder", "muted")
        navigation.addWidget(self.location, 1)
        self.up = QPushButton("Up")
        self.up.setEnabled(False)
        self.up.clicked.connect(self.go_up)
        navigation.addWidget(self.up)
        source_layout.addLayout(navigation)
        self.files = QListWidget()
        self.files.setMaximumHeight(190)
        self.files.itemDoubleClicked.connect(self.open_entry)
        source_layout.addWidget(self.files)
        self.source_title = label("Select a UTF-8 text file", "sectionTitle")
        source_layout.addWidget(self.source_title)
        self.source_view = QPlainTextEdit()
        self.source_view.setReadOnly(True)
        self.source_view.setPlaceholderText("A source preview appears here.\n\nPDF and Word parsing will be added in the next document-ingestion stage.")
        source_layout.addWidget(self.source_view, 1)
        split.addWidget(source_panel)

        draft_panel = QWidget()
        draft_layout = QVBoxLayout(draft_panel)
        draft_layout.setContentsMargins(12, 0, 0, 0)
        draft_layout.addWidget(label("Draft & review", "paneTitle"))
        draft_layout.addWidget(label("Choose an editable folder and a new filename.", "muted"))
        self.destination = QComboBox()
        self.destination.setPlaceholderText("Add an editable folder to save drafts")
        self.destination.currentIndexChanged.connect(self.invalidate_review)
        draft_layout.addWidget(self.destination)
        self.filename = QLineEdit()
        self.filename.setPlaceholderText("New filename, e.g. procedure-revised.md")
        self.filename.textChanged.connect(self.invalidate_review)
        draft_layout.addWidget(self.filename)
        self.draft = QPlainTextEdit()
        self.draft.setPlaceholderText("Draft text or a revision here.\n\nThis prototype has no AI generation yet.")
        self.draft.textChanged.connect(self.invalidate_review)
        draft_layout.addWidget(self.draft, 3)
        self.review = QPushButton("Review changes")
        self.review.setObjectName("primary")
        self.review.clicked.connect(self.review_draft)
        draft_layout.addWidget(self.review)
        draft_layout.addWidget(label("Changes to review", "sectionTitle"))
        self.diff_view = QPlainTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setFont(QFont("Menlo", 11))
        self.diff_view.setPlaceholderText("The exact proposed changes appear here before saving.")
        draft_layout.addWidget(self.diff_view, 2)
        self.save = QPushButton("Save reviewed copy")
        self.save.setObjectName("primary")
        self.save.setEnabled(False)
        self.save.clicked.connect(self.save_reviewed)
        draft_layout.addWidget(self.save)
        draft_layout.addWidget(label("Saves a new file. Existing files are preserved.", "muted"))
        split.addWidget(draft_panel)
        split.setSizes([300, 445, 475])
        self.status = label("Ready · No folders shared", "status")
        outer.addWidget(self.status)
        self.invalidate_review()
        self.setStyleSheet(STYLE)

    def message(self, text: str, error: bool = False):
        self.status.setText(text)
        self.status.setStyleSheet("color: #f5a6a6;" if error else "color: #9cadc2;")

    def invalidate_review(self, *args):
        if self.proposal is not None:
            self.workspace.discard(self.proposal.id)
            self.proposal = None
        self.diff_view.clear()
        self.save.setEnabled(False)
        self.review.setEnabled(bool(self.destination.currentData() and self.filename.text()
                                    and self.draft.toPlainText()))

    def clear_document(self):
        self.source = None
        self.source_title.setText("Select a UTF-8 text file")
        self.source_view.clear()
        self.draft.clear()
        self.filename.clear()
        self.invalidate_review()

    def add_folder(self, path: str, access: str):
        try:
            folder = self.workspace.grant(path, access)
            zone = self.read_only if access == "read-only" else self.editable
            zone.add(folder, path)
            self.clear_document()
            self.refresh_destinations()
            self.message("Added " + folder.name + " · " + access)
        except (AccessDenied, OSError) as e:
            self.message(str(e), True)

    def refresh_destinations(self):
        previous = self.destination.currentData()
        self.destination.clear()
        for folder in self.workspace.broker.folders():
            if folder.access == "editable":
                self.destination.addItem(folder.name, folder.id)
        index = self.destination.findData(previous)
        if index >= 0:
            self.destination.setCurrentIndex(index)
        elif self.destination.count():
            self.destination.setCurrentIndex(0)
        self.invalidate_review()

    def revoke_folder(self, folder_id: str):
        try:
            self.workspace.revoke(folder_id)
            self.clear_document()
            for zone in (self.read_only, self.editable):
                zone.remove_id(folder_id)
            if self.folder_id == folder_id:
                self.folder_id = None
                self.directory = ""
                self.files.clear()
                self.location.setText("Choose an allowed folder")
                self.up.setEnabled(False)
            self.refresh_destinations()
            self.message("Folder access removed. Preview and pending draft cleared.")
        except AccessDenied as e:
            self.message(str(e), True)

    def select_folder(self, folder_id: str):
        self.folder_id = folder_id
        self.directory = ""
        self.clear_document()
        self.refresh_files()

    def refresh_files(self):
        self.files.clear()
        if self.folder_id is None:
            return
        try:
            result = self.workspace.broker.list_directory(self.folder_id, self.directory)
            folder = next(f for f in self.workspace.broker.folders() if f.id == self.folder_id)
            self.location.setText(folder.name + (" / " + self.directory if self.directory else ""))
            self.up.setEnabled(bool(self.directory))
            for entry in result["entries"]:
                item = QListWidgetItem(entry["name"] + (" /" if entry["kind"] == "directory" else ""))
                item.setData(Qt.ItemDataRole.UserRole, entry)
                self.files.addItem(item)
            if result["truncated"]:
                self.message("Directory listing limited; only a subset of entries is shown.")
        except (AccessDenied, StopIteration) as e:
            self.message(str(e), True)

    def go_up(self):
        self.directory = self.directory.rpartition("/")[0]
        self.clear_document()
        self.refresh_files()

    def open_entry(self, item):
        entry = item.data(Qt.ItemDataRole.UserRole)
        path = self.directory + "/" + entry["name"] if self.directory else entry["name"]
        self.clear_document()
        if entry["kind"] == "directory":
            self.directory = path
            self.refresh_files()
            return
        try:
            source = self.workspace.open_text(self.folder_id, path)
            self.source = source
            self.source_title.setText(path)
            self.source_view.setPlainText(source.text)
            self.draft.setPlainText(source.text)
            filename = PurePosixPath(path)
            self.filename.setText(filename.stem + "-revised" + (filename.suffix or ".txt"))
            self.message("Source opened. Draft changes are saved to a new file after review.")
        except AccessDenied as e:
            self.message(str(e), True)

    def review_draft(self):
        self.invalidate_review()
        try:
            self.proposal = self.workspace.propose(self.destination.currentData(), self.filename.text(),
                                                   self.draft.toPlainText(), self.source)
            self.diff_view.setPlainText(self.proposal.diff or "No content changes; this will create an identical copy.")
            self.save.setEnabled(True)
            self.message("Review the changes and destination, then save the new file.")
        except AccessDenied as e:
            self.message(str(e), True)

    def save_reviewed(self):
        if self.proposal is None:
            return
        try:
            saved = self.workspace.approve(self.proposal.id)
            self.invalidate_review()
            self.refresh_files()
            self.message("Saved " + saved.destination_path + " to " + self.destination.currentText())
        except AccessDenied as e:
            self.invalidate_review()
            self.message(str(e), True)

    def closeEvent(self, event):
        self.workspace.close()
        event.accept()


STYLE = """
QWidget { background: #111923; color: #e5ecf5; font-size: 13px; }
QLabel#appTitle { font-size: 25px; font-weight: 600; }
QLabel#paneTitle { font-size: 19px; font-weight: 600; padding-bottom: 10px; }
QLabel#sectionTitle { font-size: 12px; font-weight: 600; color: #c2d3e8; padding: 4px 0; }
QLabel#muted, QLabel#status { color: #9cadc2; font-size: 12px; }
QLabel#status { padding-top: 12px; }
QLabel#badge { background: #1e3044; color: #9cc6fb; padding: 10px 14px; border-radius: 8px; font-size: 11px; }
QFrame#folderZone { border: 1px solid #304155; border-radius: 10px; background: #182431; }
QFrame#folderZone QLabel { background: transparent; }
QLabel#dropHint { color: #8198b3; border: 1px dashed #405a75; border-radius: 7px; padding: 18px 8px; }
QListWidget, QPlainTextEdit, QLineEdit, QComboBox { background: #16212e; border: 1px solid #304155; border-radius: 6px; padding: 8px; }
QListWidget::item { padding: 6px; }
QListWidget::item:selected { background: #284766; color: white; }
QPushButton { background: #233448; border: 1px solid #3b526c; border-radius: 6px; padding: 9px 12px; }
QPushButton:hover { background: #304866; }
QPushButton#primary { background: #3266a6; border-color: #5083c0; font-weight: 600; }
QPushButton:disabled { background: #1b2837; color: #64788f; border-color: #2b3b4e; }
QPushButton#primary:disabled { background: #1b2837; color: #64788f; border-color: #2b3b4e; }
QSplitter::handle { background: #263548; width: 1px; }
"""


def main() -> int:
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName("Local AI Appliance")
    try:
        window = WorkspaceWindow()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
