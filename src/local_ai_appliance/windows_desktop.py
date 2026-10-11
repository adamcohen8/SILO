"""Text-only native interface for the prepared Windows local evaluation."""
from pathlib import Path, PurePosixPath
import os
import subprocess

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QListWidget, QListWidgetItem,
    QFrame, QLayout, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSplitter, QVBoxLayout, QWidget,
)

from .desktop import FolderZone, STYLE, label
from .folders import AccessDenied
from .windows_folders import FolderOverlap
from .windows_session import Cancelled, WindowsSession
from .chat_view import ChatComposer, ChatTranscript
from .folder_settings import FolderSettings
from .mentions import MentionCatalog
from .draft_review import DraftReview, ArtifactReview


class Task(QThread):
    completed = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, operation, parent):
        super().__init__(parent)
        self.operation = operation

    def run(self):
        try:
            self.completed.emit(self.operation(self.progress.emit))
        except Cancelled:
            self.failed.emit('Request cancelled. Restart the model to continue.')
        except (AccessDenied, RuntimeError) as error:
            self.failed.emit(str(error))
        except Exception:
            # Parser/worker details can contain source text. No tracebacks in UI.
            self.failed.emit('The local operation failed. Check the selected folders and try again.')


def editor(placeholder='', readonly=False):
    result = QPlainTextEdit()
    result.setPlaceholderText(placeholder)
    result.setReadOnly(readonly)
    return result


def configure_fonts(app):
    # Explicit system fonts also make the Qt offscreen verification readable.
    fonts = Path(os.environ.get('SystemRoot', r'C:\Windows'))/'Fonts'
    for name in ('segoeui.ttf', 'consola.ttf'):
        QFontDatabase.addApplicationFont(str(fonts/name))
    app.setFont(QFont('Segoe UI', 10))


class WindowsAssistantWindow(QMainWindow):
    def __init__(self, root, session=None, *, autostart=True, folder_settings=None, required_policy_key_sha256=None,evaluation=False):
        super().__init__()
        self.root = Path(root).resolve()
        self.required_policy_key_sha256=required_policy_key_sha256
        self.evaluation=evaluation
        self.session = session or WindowsSession(self.root,evaluation=evaluation)
        self.folder_settings = (FolderSettings(self.session.state/'folders.json')
                                if folder_settings is None and session is None else folder_settings)
        self.workspace = self.session.workspace
        self.host_backend = self.project_backend = self.project_vault = None
        self.busy = self.closing = self.cleaned = False
        self.jobs = set()
        self.folder_id = None
        self.directory = ''
        self.last_result = None
        self.review_dialog = None
        self.folder_notice = None
        self.chat_generation = 0
        self.mention_generation = 0
        self.mention_job = None
        self.setWindowTitle('SILO — Windows evaluation')
        self.setWindowIcon(QIcon(str(self.root/'assets/branding/silo.ico')))
        self.resize(1280, 900)
        self.setMinimumSize(980, 740)
        self.setStyleSheet(STYLE + '\nQPlainTextEdit { font-size: 13px; }')
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(24, 20, 24, 16)
        heading = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(label('SILO', 'appTitle'))
        titles.addWidget(label('Local intelligence. Contained by design.', 'muted'))
        heading.addLayout(titles, 1)
        heading.addWidget(label('LOCAL EVALUATION\nPublic or synthetic documents only', 'badge'))
        outer.addLayout(heading)
        toolbar = QHBoxLayout()
        self.status = label('Preparing the local model…', 'muted')
        toolbar.addWidget(self.status, 1)
        self.agents_button = QPushButton('Open AGENTS.md')
        self.agents_button.setToolTip('Edit assistant instructions in Notepad. Save, then restart the model to apply changes.')
        self.agents_button.clicked.connect(self.open_agents)
        toolbar.addWidget(self.agents_button)
        self.clear_chat_button = QPushButton('Clear chat')
        self.clear_chat_button.clicked.connect(self.clear_chat)
        toolbar.addWidget(self.clear_chat_button)
        self.projects_button = QPushButton('Projects')
        self.projects_button.clicked.connect(self.open_projects)
        self.projects_button.setEnabled(False)
        toolbar.addWidget(self.projects_button)
        self.demo_button = QPushButton('Load sample folders')
        self.demo_button.clicked.connect(self.load_samples)
        toolbar.addWidget(self.demo_button)
        self.restart_button = QPushButton('Restart model')
        self.restart_button.setToolTip('Reload AGENTS.md and the model. Clears the current chat; restores saved folders.')
        self.restart_button.clicked.connect(self.restart)
        toolbar.addWidget(self.restart_button)
        self.cancel_button = QPushButton('Cancel request')
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.setEnabled(False)
        toolbar.addWidget(self.cancel_button)
        outer.addLayout(toolbar)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left, middle = QWidget(), QWidget()
        a, b = QVBoxLayout(left), QVBoxLayout(middle)
        for layout in (a, b):
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(10)
        a.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.read_zone = FolderZone('Reference folders', 'read-only', 'Read and cite. Source files stay unchanged.')
        self.edit_zone = FolderZone('Draft folders', 'editable', 'Read here and save reviewed new copies.')
        for zone in (self.read_zone, self.edit_zone):
            zone.added.connect(self.grant)
            zone.removed.connect(self.revoke)
            zone.selected.connect(self.select_folder)
            zone.list.setMaximumHeight(75)
            a.addWidget(zone)
        self.browser_title = label('Select a granted folder', 'sectionTitle')
        a.addWidget(self.browser_title)
        self.files = QListWidget()
        self.files.setMinimumHeight(140)
        self.files.itemDoubleClicked.connect(self.open_entry)
        a.addWidget(self.files, 1)
        a.addWidget(label('UTF-8 text, PDF and DOCX · up to 1 MiB per file\nImage-only PDFs need OCR, which is unavailable.', 'muted'))
        chat = QFrame()
        chat.setObjectName('chatPanel')
        chat.setStyleSheet('QFrame#chatPanel { background: #16212e; border: 1px solid #304155; border-radius: 10px; }')
        chat_layout = QVBoxLayout(chat)
        chat_layout.setContentsMargins(10, 10, 10, 10)
        chat_layout.setSpacing(8)
        self.answer = ChatTranscript()
        chat_layout.addWidget(self.answer, 1)
        self.prompt = ChatComposer()
        self.prompt.setObjectName('chatComposer')
        self.prompt.setPlaceholderText('Message Nemotron…  / folders · @ files')
        self.prompt.setMinimumHeight(64)
        self.prompt.setMaximumHeight(90)
        self.prompt.submitted.connect(self.ask)
        self.prompt.mentions_requested.connect(self.request_mentions)
        self.question_button = QPushButton('Sample question')
        self.question_button.clicked.connect(lambda: self.prompt.setPlainText(
            'Read capacity.txt in Reference. What is the approved capacity? Cite the exact supporting line.'))
        self.draft_example = QPushButton('Sample draft')
        self.draft_example.clicked.connect(lambda: self.prompt.setPlainText(
            'Read capacity.txt in Reference. Propose a new capacity-summary.md in Drafts. '
            'Summarize the approved capacity in one sentence. Use capacity.txt as the source for the proposal. '
            'Do not save anything. Cite the supporting line in your answer.'))
        self.ask_button = QPushButton('Send')
        self.ask_button.setObjectName('primary')
        self.ask_button.clicked.connect(self.ask)
        examples = QHBoxLayout()
        examples.addWidget(self.question_button)
        examples.addWidget(self.draft_example)
        examples.addStretch(1)
        chat_layout.addLayout(examples)
        composer = QHBoxLayout()
        composer.addWidget(self.prompt, 1)
        composer.addWidget(self.ask_button)
        chat_layout.addLayout(composer)
        chat_layout.addWidget(label('/ folders · @ files · Enter to send · Shift+Enter for a new line', 'muted'))
        b.addWidget(chat, 1)
        self.sources_toggle = QPushButton('Sources')
        self.sources_toggle.setCheckable(True)
        self.sources_toggle.hide()
        b.addWidget(self.sources_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        self.sources_panel = QWidget()
        source_layout = QVBoxLayout(self.sources_panel)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.addWidget(label('Sources used · select to inspect the actual excerpt', 'sectionTitle'))
        self.citations = QListWidget()
        self.citations.setMaximumHeight(80)
        self.citations.currentItemChanged.connect(self.show_citation)
        source_layout.addWidget(self.citations)
        self.citation_title = label('No source selected', 'muted')
        source_layout.addWidget(self.citation_title)
        self.excerpt = editor('Source text is shown as plain text.', True)
        self.excerpt.setMaximumHeight(120)
        source_layout.addWidget(self.excerpt)
        b.addWidget(self.sources_panel)
        self.sources_panel.hide()
        self.sources_toggle.toggled.connect(self.sources_panel.setVisible)
        self.drafts_panel = QWidget()
        draft_layout = QHBoxLayout(self.drafts_panel)
        self.drafts = QListWidget()
        self.drafts.setMaximumHeight(75)
        draft_layout.addWidget(self.drafts, 1)
        self.review_draft_button = QPushButton('Review draft…')
        self.review_draft_button.clicked.connect(self.open_draft_review)
        draft_layout.addWidget(self.review_draft_button)
        b.addWidget(self.drafts_panel)
        self.drafts_panel.hide()
        sidebar = QScrollArea()
        sidebar.setObjectName('folderSidebar')
        sidebar.setStyleSheet('QScrollArea#folderSidebar { border: none; }')
        sidebar.setWidgetResizable(True)
        sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar.setWidget(left)
        for widget in (sidebar, middle):
            splitter.addWidget(widget)
        splitter.setSizes([340, 940])
        self.splitter = splitter
        outer.addWidget(splitter, 1)
        self.setCentralWidget(container)
        shortcut = QShortcut(QKeySequence('Ctrl+Return'), self)
        shortcut.activated.connect(self.ask)
        self.shortcut = shortcut
        self.controls()
        if autostart:
            QTimer.singleShot(0, self.start_model)

    def controls(self):
        ready = bool(self.workspace and not self.session.closed)
        free = not self.busy and not self.closing
        state = 'Ready' if self.session.ready else ('Starting' if self.busy else 'Model stopped')
        self.setWindowTitle('SILO — '+state+' · Windows evaluation')
        for widget in (self.read_zone, self.edit_zone, self.files, self.demo_button):
            widget.setEnabled(ready and free)
        self.prompt.setEnabled(free)
        if not free:
            self.prompt.popup.hide()
        for widget in (self.question_button, self.draft_example):
            widget.setEnabled(free)
        self.ask_button.setEnabled(ready and free and self.session.ready)
        self.restart_button.setEnabled(free)
        self.agents_button.setEnabled(not self.closing)
        self.clear_chat_button.setEnabled(free)
        self.projects_button.setEnabled(free and self.project_backend is not None)
        self.review_draft_button.setEnabled(ready and free and self.drafts.count() > 0)

    def open_agents(self):
        path = (self.session.state if getattr(self.session, 'installation', None) else self.root)/'AGENTS.md'
        if not path.is_file():
            self.status.setText('AGENTS.md is missing from the application folder. Restore it before restarting.')
            return
        try:
            notepad = Path(os.environ.get('SystemRoot', r'C:\Windows'))/'System32/notepad.exe'
            subprocess.Popen([str(notepad), str(path)], cwd=str(self.root))
        except OSError:
            self.status.setText('Could not open Notepad. Open AGENTS.md in a text editor from the application folder.')
            return
        self.status.setText('AGENTS.md opened in Notepad. Save, then restart the model to apply changes (clears chat).')

    def run_task(self, operation, done, *, cancellable=False, failure=None, closing_ok=False):
        if self.busy:
            return
        self.busy = True
        self.controls()
        self.cancel_button.setEnabled(cancellable)
        task = Task(operation, self)
        self.jobs.add(task)
        task.progress.connect(self.status.setText, Qt.ConnectionType.QueuedConnection)
        def success(value):
            self.busy = False
            self.cancel_button.setEnabled(False)
            if not self.closing or closing_ok:
                done(value)
                self.controls()
            elif not self.cleaned:
                QTimer.singleShot(0, self.shutdown)
        def error(message):
            self.busy = False
            self.cancel_button.setEnabled(False)
            self.status.setText(message)
            if failure:
                failure()
            self.controls()
            if self.closing and not self.cleaned:
                QTimer.singleShot(0, self.shutdown)
        task.completed.connect(success, Qt.ConnectionType.QueuedConnection)
        task.failed.connect(error, Qt.ConnectionType.QueuedConnection)
        def release():
            self.jobs.discard(task)
            task.deleteLater()
            if self.closing and self.cleaned and not self.jobs:
                self.close()
        task.finished.connect(release, Qt.ConnectionType.QueuedConnection)
        task.start()

    def prepare_host(self):
        if self.required_policy_key_sha256 and not getattr(self.session,'installation',None):
            raise AccessDenied('Organization policy requires the standalone installation')
        if self.project_vault is None and getattr(self.session, 'installation', None):
            from .project_store import LocalVault, project_data_directory
            from .model_management import ModelManager
            self.project_vault = LocalVault(project_data_directory(self.session.state), windows_validation=True)
            self.session.model_manager = ModelManager(self.root, self.project_vault,
                model_cache=project_data_directory(self.session.state,name='models'),
                required_key_sha256=self.required_policy_key_sha256,policy_store=self.session.security.store)

    def start_model(self):
        def operation(progress):
            self.prepare_host()
            self.session.start(progress)
        self.run_task(operation, self.model_ready, cancellable=True)

    def open_projects(self):
        if self.busy or self.project_backend is None: return
        from .project_dialog import ProjectDialog
        dialog = ProjectDialog(self)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.project_dialog = dialog
        dialog.open()

    def project_changed(self):
        self.chat_generation += 1
        self.clear_content()
        self.answer.set_conversation(self.session.conversation.display())
        for zone in (self.read_zone,self.edit_zone): zone.list.clear(); zone.empty.show()
        for folder,grant in zip(self.workspace.broker.folders(),self.workspace.broker.saved_grants(),strict=True):
            (self.read_zone if folder.access=='read-only' else self.edit_zone).add(folder,grant['path'])
        self.folder_id = None; self.files.clear(); self.invalidate_mentions()
        self.status.setText('Ready · '+self.project_backend.project.name)


    def model_ready(self, value):
        self.workspace = self.session.workspace
        profile=getattr(self.session,'model_profile',None)
        model=profile['id'] if profile else 'Local evaluation model'
        self.status.setText('Ready · '+model+' · inference stays on this computer')
        from .backend import WindowsSessionAdapter
        from .contracts import Project
        self.host_backend = WindowsSessionAdapter(Project('windows-evaluation','Unsaved session'),self.session)
        if self.project_vault is not None:
            from .project_store import ProjectSession,ProjectStore
            security=getattr(self.session,'security',None)
            self.project_backend = ProjectSession(self.host_backend,ProjectStore(self.project_vault,
                maximum_retention_days=security.settings['maximum_retention_days'] if security else 365,
                audit=security.audit if security else None))
            self.projects_button.setEnabled(True)
            active=self.project_vault.get('active-project')
            if active:
                try:
                    self.project_backend.open_project(active['id']); self.project_changed()
                except (AccessDenied,OSError): self.status.setText('Saved project could not resume; open or delete it explicitly.')
                self.invalidate_mentions(); return
        self.restore_folders()
        self.invalidate_mentions()

    def invalidate_mentions(self):
        self.mention_generation += 1
        self.prompt.set_catalog(None)

    def request_mentions(self):
        if self.mention_job or not self.workspace or self.closing:
            return
        workspace, generation = self.workspace, self.mention_generation
        job = Task(lambda progress: MentionCatalog(workspace.broker), self)
        self.mention_job = job
        self.jobs.add(job)
        def completed(catalog):
            if not self.closing and workspace is self.workspace and generation == self.mention_generation:
                self.prompt.set_catalog(catalog)
        def failed(message):
            if not self.closing and generation == self.mention_generation:
                self.status.setText('Folder/file suggestions could not be loaded. Try selecting the folder again.')
        def release():
            self.jobs.discard(job)
            self.mention_job = None
            job.deleteLater()
            if self.closing and self.cleaned and not self.jobs:
                self.close()
            elif not self.closing and generation != self.mention_generation and self.prompt.active_mention():
                QTimer.singleShot(0, self.request_mentions)
        job.completed.connect(completed, Qt.ConnectionType.QueuedConnection)
        job.failed.connect(failed, Qt.ConnectionType.QueuedConnection)
        job.finished.connect(release, Qt.ConnectionType.QueuedConnection)
        job.start()

    def save_folders(self):
        if self.project_backend and self.project_backend.record:
            self.project_backend.persist(); return
        if not self.folder_settings:
            return True
        try:
            self.folder_settings.save(self.workspace.broker.saved_grants())
            return True
        except (OSError, ValueError, AccessDenied):
            self.status.setText('Folder access changed for this session, but settings could not be saved for the next launch.')
            return False

    def restore_folders(self):
        if not self.folder_settings:
            return
        try:
            entries = self.folder_settings.load()
        except (OSError, RuntimeError):
            self.status.setText('Ready. Saved folder settings could not be loaded; add the folders again.')
            return
        restored, skipped = 0, 0
        for entry in entries:
            try:
                folder = self.workspace.broker.grant(entry['path'], entry['access'],
                    expected_identity=(entry['volume'], entry['index']))
                zone = self.read_zone if folder.access == 'read-only' else self.edit_zone
                zone.add(folder, entry['path'])
                restored += 1
            except (AccessDenied, OSError):
                skipped += 1
        # Failed restoration never grants replacement or overlapping folders.
        # Unavailable selections are omitted; the user can explicitly re-add.
        if entries:
            self.session.clear_chat()
            self.status.setText(f'Ready · {restored} saved folders restored'+
                (f' · {skipped} unavailable or changed; add those folders again.' if skipped else ''))
            self.save_folders()

    def restart(self):
        if self.busy:
            return
        self.clear_chat()
        for zone in (self.read_zone, self.edit_zone):
            zone.list.clear()
            zone.empty.show()
        self.status.setText('Restarting the local model…')
        def operation(progress):
            if self.project_backend: self.project_backend.persist()
            self.session.close()
            self.session = WindowsSession(self.root,evaluation=self.evaluation)
            self.host_backend = self.project_backend = None
            if self.project_vault:
                from .model_management import ModelManager
                from .project_store import project_data_directory
                self.session.model_manager = ModelManager(self.root,self.project_vault,
                    model_cache=project_data_directory(self.session.state,name='models'),
                    required_key_sha256=self.required_policy_key_sha256,policy_store=self.session.security.store)
            self.session.start(progress)
        self.workspace = None
        self.invalidate_mentions()
        self.run_task(operation, self.model_ready, cancellable=True)

    def cancel(self):
        self.status.setText('Cancelling the request and stopping its local model…')
        self.cancel_button.setEnabled(False)
        self.session.cancel()
        self.chat_generation += 1
        self.clear_content()

    def clear_chat(self):
        if self.busy or self.closing:
            return
        (self.project_backend or self.host_backend or self.session).clear_chat()
        self.chat_generation += 1
        self.clear_content()
        self.prompt.clear()
        self.status.setText('Chat cleared. Ready for a new conversation.')

    def clear_content(self):
        self.clear_drafts()
        self.last_result = None
        self.answer.clear()
        self.clear_sources()

    def clear_sources(self):
        self.excerpt.clear()
        self.citations.clear()
        self.citation_title.setText('No source selected')
        self.sources_toggle.setChecked(False)
        self.sources_toggle.hide()
        self.sources_panel.hide()

    def grant(self, path, access):
        if self.busy or self.closing or not self.workspace:
            return
        try:
            if self.project_backend or self.host_backend:
                from .contracts import WorkspaceKind
                folder = (self.project_backend or self.host_backend).grant(path,WorkspaceKind.REFERENCE if access=='read-only' else WorkspaceKind.DRAFT)
            else:
                folder = self.workspace.grant(path, access)
            # Broker may upgrade an existing grant. Display it exactly once.
            for zone in (self.read_zone, self.edit_zone):
                zone.remove_id(folder.id)
            (self.read_zone if access == 'read-only' else self.edit_zone).add(folder, path)
            self.session.clear_chat()
            self.chat_generation += 1
            self.clear_content()
            self.status.setText('Folder access updated and chat cleared. Ask using the selected folders.')
            self.invalidate_mentions()
            self.save_folders()
        except FolderOverlap as error:
            self.confirm_folder_replacement(path, access, error.folder_ids)
        except (AccessDenied, OSError) as error:
            self.status.setText(str(error))
            self.show_folder_error(str(error))
        self.controls()

    def show_folder_error(self, message):
        notice = QMessageBox(self)
        notice.setWindowTitle('Folder could not be added')
        notice.setTextFormat(Qt.TextFormat.PlainText)
        notice.setText(message)
        notice.setInformativeText('Choose a local folder on an NTFS drive. Network paths, links, '
                                  'cloud placeholders and whole-drive access are unavailable in this evaluation.')
        notice.setIcon(QMessageBox.Icon.Warning)
        notice.setStandardButtons(QMessageBox.StandardButton.Ok)
        self.folder_notice = notice
        notice.open()

    def confirm_folder_replacement(self, path, access, folder_ids):
        revision = self.workspace.broker.revision
        folders = {f.id: f for f in self.workspace.broker.folders()}
        locations = {}
        for zone in (self.read_zone, self.edit_zone):
            for index in range(zone.list.count()):
                item = zone.list.item(index)
                locations[item.data(Qt.ItemDataRole.UserRole)] = item.data(Qt.ItemDataRole.UserRole+1)
        details = '\n'.join(f'{locations.get(i) or folders[i].name} ({folders[i].access})' for i in folder_ids)
        self.status.setText('Folder not added: it overlaps existing access. Choose whether to replace those grants.')
        notice = QMessageBox(self)
        notice.setWindowTitle('Replace overlapping folder access?')
        notice.setTextFormat(Qt.TextFormat.PlainText)
        notice.setText('The selected folder overlaps folders that are already granted.')
        notice.setInformativeText(details+'\n\nReplace those grants with '+access+' access to:\n'+path+
                                  '\n\nPrevious answers and pending drafts will be cleared.')
        notice.setIcon(QMessageBox.Icon.Question)
        replace = notice.addButton('Replace folder access', QMessageBox.ButtonRole.AcceptRole)
        cancel = notice.addButton(QMessageBox.StandardButton.Cancel)
        notice.setDefaultButton(cancel)
        self.folder_notice = notice
        def chosen(button):
            if button != replace or self.closing or self.busy:
                return
            if self.workspace.broker.revision != revision:
                self.status.setText('Folder permissions changed. Select the folder again.')
                return
            for identifier in folder_ids:
                self.revoke(identifier)
            # The fresh native acquisition rechecks the selected folder after
            # explicit removal. No path-based or overlapping-grant fallback.
            self.grant(path, access)
        notice.buttonClicked.connect(chosen)
        notice.open()

    def revoke(self, folder_id):
        if self.busy or not self.workspace:
            return
        if self.project_backend or self.host_backend:
            (self.project_backend or self.host_backend).revoke(folder_id)
        else:
            self.workspace.revoke(folder_id)
            self.session.clear_chat()
        self.chat_generation += 1
        for zone in (self.read_zone, self.edit_zone):
            zone.remove_id(folder_id)
        self.folder_id = None
        self.files.clear()
        self.clear_content()
        self.browser_title.setText('Select a granted folder')
        self.status.setText('Folder access removed. Previous answers and drafts cleared.')
        self.invalidate_mentions()
        self.save_folders()
        self.controls()

    def select_folder(self, folder_id):
        if self.busy or not self.workspace:
            return
        self.folder_id, self.directory = folder_id, ''
        self.refresh_files()

    def refresh_files(self):
        self.files.clear()
        if not self.folder_id or not self.workspace:
            return
        try:
            folders = {f.id: f for f in self.workspace.broker.folders()}
            self.browser_title.setText(folders[self.folder_id].name + (' / '+self.directory if self.directory else ''))
            if self.directory:
                item = QListWidgetItem('← Parent folder')
                item.setData(Qt.ItemDataRole.UserRole, ('parent', self.directory))
                self.files.addItem(item)
            value = self.workspace.broker.list_directory(self.folder_id, self.directory)
            for entry in value['entries']:
                item = QListWidgetItem(('▸ ' if entry['kind'] == 'directory' else '')+entry['name'])
                path = str(PurePosixPath(self.directory)/entry['name'])
                item.setData(Qt.ItemDataRole.UserRole, (entry['kind'], path))
                self.files.addItem(item)
        except (AccessDenied, OSError, KeyError) as error:
            self.status.setText(str(error))

    def open_entry(self, item):
        if self.busy:
            return
        kind, path = item.data(Qt.ItemDataRole.UserRole)
        if kind in ('parent', 'directory'):
            self.directory = str(PurePosixPath(path).parent) if kind == 'parent' else path
            if self.directory == '.':
                self.directory = ''
            self.refresh_files()
            return
        folders = {f.id: f for f in self.workspace.broker.folders()}
        folder = folders[self.folder_id]
        self.prompt.setPlainText(f'Summarize {path} in {folder.name}. Cite the supporting source locators, including sheet/row metadata for tables.')
        self.prompt.setFocus()
        self.status.setText('Message prepared for the selected file. Click Send.')

    def load_samples(self):
        if self.busy:
            return
        sample = (self.session.state if getattr(self.session, 'installation', None) else self.root/'artifacts/windows-ui')/'samples'
        reference, drafts = sample/'Reference', sample/'Drafts'
        reference.mkdir(parents=True, exist_ok=True)
        drafts.mkdir(parents=True, exist_ok=True)
        path = reference/'capacity.txt'
        if not path.exists():
            path.write_text('Fictional storage approval note.\nThe approved capacity is 37 crates.\n'
                            'Use this public fixture to test document questions and reviewed drafts.\n', encoding='utf-8')
        self.grant(str(reference), 'read-only')
        self.grant(str(drafts), 'editable')
        self.prompt.setPlainText('Read capacity.txt in Reference. What is the approved capacity? Cite the exact supporting line.')
        self.status.setText('Sample folders granted. Click Send, or try Sample draft.')

    def ask(self):
        if self.busy or not self.session.ready:
            return
        prompt = self.prompt.toPlainText().strip()
        if not prompt:
            self.status.setText('Enter a question or request a draft first.')
            return
        # Pending writes never carry over as authority in a conversation.
        for proposal in self.workspace.pending_proposals():
            self.workspace.discard(proposal.id)
        self.clear_drafts()
        self.clear_sources()
        self.last_result = None
        self.answer.set_conversation(self.session.conversation.display())
        self.answer.add_message('user', prompt)
        self.answer.add_message('assistant', 'Thinking…')
        generation = self.chat_generation
        self.status.setText('Working locally…')
        def finished(result):
            if generation == self.chat_generation:
                self.show_answer(result)
                self.prompt.clear()
        def failed():
            if generation != self.chat_generation or self.closing:
                return
            self.last_result = None
            self.answer.set_conversation(self.session.conversation.display())
            self.answer.add_message('user', prompt)
            self.answer.add_message('assistant', self.status.text()+
                '\n\nThis request was not added to chat memory. You can edit it and try again.')
        self.run_task(lambda progress: (self.project_backend or self.host_backend or self.session).ask(prompt), finished, cancellable=True, failure=failed)

    def show_answer(self, result):
        self.last_result = result
        self.clear_sources()
        if result.conversation:
            self.answer.set_conversation(result.conversation)
        else:
            self.answer.setPlainText(result.answer)
        for source in result.citations:
            item = QListWidgetItem(source.path+' · '+source.locator+' '+source.reference)
            item.setData(Qt.ItemDataRole.UserRole, source)
            self.citations.addItem(item)
        if self.citations.count():
            self.citations.setCurrentRow(0)
            self.sources_toggle.setText(f'Sources ({self.citations.count()})')
            self.sources_toggle.show()
        if result.proposals:
            draft_text = '\n\n'.join('Draft: '+p.destination_path+' (not saved)\n'+p.text for p in result.proposals)
            if not result.conversation:
                self.answer.appendPlainText('\n'+draft_text)
            for proposal in result.proposals:
                item = QListWidgetItem(proposal.destination_path+' (unsaved)')
                item.setData(Qt.ItemDataRole.UserRole, proposal.id)
                self.drafts.addItem(item)
            self.drafts.setCurrentRow(0)
            self.drafts_panel.show()
        self.status.setText(f'Finished locally · {result.model_calls} model calls · {result.tool_calls} document tool calls')
        if result.history_reset:
            self.status.setText('Previous chat cleared because folder permissions or a source changed.')
        elif result.history_trimmed:
            self.status.setText('Finished locally. Older chat turns were removed to fit the context limit.')

    def clear_drafts(self):
        if self.review_dialog:
            self.review_dialog.invalidate()
            if not self.review_dialog.working:
                self.review_dialog.reject()
        self.drafts.clear()
        self.drafts_panel.hide()

    def open_draft_review(self):
        if self.busy or self.closing or not self.workspace:
            return
        item = self.drafts.currentItem()
        if not item:
            return
        identifier = item.data(Qt.ItemDataRole.UserRole)
        proposal = next((p for p in self.workspace.pending_proposals() if p.id == identifier), None)
        if proposal is None:
            self.status.setText('This draft is no longer available. Request a fresh draft.')
            return
        dialog = ArtifactReview(self, proposal) if proposal.data is not None else DraftReview(self, proposal)
        self.review_dialog = dialog
        def finished(code):
            self.review_dialog = None
            for index in range(self.drafts.count()-1, -1, -1):
                if self.drafts.item(index).data(Qt.ItemDataRole.UserRole) == identifier:
                    self.drafts.takeItem(index)
            self.drafts_panel.setVisible(self.drafts.count() > 0)
            self.controls()
            dialog.deleteLater()
        dialog.finished.connect(finished)
        dialog.open()

    def show_citation(self, item, previous):
        if item:
            source = item.data(Qt.ItemDataRole.UserRole)
            self.citation_title.setText(source.path+' · '+source.locator+' · SHA-256 '+source.sha256[:12])
            self.excerpt.setPlainText(source.text)

    def shutdown(self):
        if self.busy or self.cleaned:
            return
        self.status.setText('Stopping the local model and removing temporary permissions…')
        def done(value):
            self.cleaned = True
            self.controls()
        def failure():
            # Do not silently hide a cleanup error by closing the window.
            self.closing = False
            self.cleaned = False
        def operation(progress):
            if self.project_backend:return self.project_backend.close()
            try:return (self.host_backend or self.session).close()
            finally:
                if self.project_vault:self.project_vault.close()
        self.run_task(operation, done, failure=failure, closing_ok=True)

    def closeEvent(self, event):
        if self.cleaned and not self.jobs:
            event.accept()
            return
        event.ignore()
        if not self.closing:
            self.closing = True
            if self.busy: self.session.cancel()
            self.controls()
        if not self.busy:
            QTimer.singleShot(0, self.shutdown)


def main(root, *, required_policy_key_sha256=None,evaluation=False):
    from PySide6.QtWidgets import QMessageBox
    app = QApplication.instance() or QApplication([])
    app.setApplicationName('SILO')
    app.setWindowIcon(QIcon(str(Path(root)/'assets/branding/silo.ico')))
    configure_fonts(app)
    try:
        window = WindowsAssistantWindow(root,required_policy_key_sha256=required_policy_key_sha256,evaluation=evaluation)
    except RuntimeError as error:
        QMessageBox.information(None, 'SILO', str(error))
        return 1
    window.show()
    return app.exec()
