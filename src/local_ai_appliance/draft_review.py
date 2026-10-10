"""Trusted desktop review surface. The worker cannot approve or select a save."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout
from .desktop import label


class DraftReview(QDialog):
    def __init__(self, host, proposal):
        super().__init__(host)
        self.host, self.workspace = host, host.workspace
        self.source = proposal.source
        self.reviewed = None
        self.working = False
        self.setWindowTitle('Review and save a new copy')
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(760, 720)
        layout = QVBoxLayout(self)
        layout.addWidget(label('Review the destination, exact draft text and changes before saving.', 'sectionTitle'))
        self.destination = QComboBox()
        self.locations = {}
        for zone in (getattr(host, 'read_zone', None), getattr(host, 'edit_zone', None)):
            if zone is None:
                continue
            for index in range(zone.list.count()):
                item = zone.list.item(index)
                self.locations[item.data(Qt.ItemDataRole.UserRole)] = item.data(Qt.ItemDataRole.UserRole+1)
        folders = self.workspace.broker.folders()
        folder_names = {folder.id: folder.name for folder in folders}
        names = [f.name for f in folders if f.access == 'editable']
        for folder in folders:
            if folder.access == 'editable':
                title = folder.name+' (editable)'
                if names.count(folder.name) > 1:
                    title += ' - '+self.locations.get(folder.id, folder.name)
                self.destination.addItem(title, folder.id)
                self.destination.setItemData(self.destination.count()-1, self.locations.get(folder.id, folder.name), Qt.ItemDataRole.ToolTipRole)
        self.destination.setCurrentIndex(self.destination.findData(proposal.destination_folder))
        layout.addWidget(self.destination)
        self.filename = QLineEdit(proposal.destination_path)
        layout.addWidget(self.filename)
        self.destination_notice = label('', 'muted')
        layout.addWidget(self.destination_notice)
        source = ('Source: '+self.locations.get(self.source.folder_id, folder_names.get(self.source.folder_id, 'Unavailable source folder'))+
                  ' / '+self.source.path+' · SHA-256 '+self.source.sha256
                  if self.source else 'New document; no revision source.')
        self.source_notice = label(source, 'muted')
        layout.addWidget(self.source_notice)
        self.text = QPlainTextEdit()
        self.text.setPlainText(proposal.text)
        layout.addWidget(self.text, 2)
        self.diff = QPlainTextEdit()
        self.diff.setReadOnly(True)
        self.diff.setPlaceholderText('Click Review changes to verify the destination and source.')
        layout.addWidget(self.diff, 1)
        self.notice = label('Unsaved. Existing files will be preserved.', 'muted')
        layout.addWidget(self.notice)
        buttons = QHBoxLayout()
        self.review_button = QPushButton('Review changes')
        self.save_button = QPushButton('Save reviewed copy')
        self.save_button.setEnabled(False)
        self.cancel_button = QPushButton('Discard draft')
        for button in (self.review_button, self.save_button, self.cancel_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.review_button.clicked.connect(self.review)
        self.save_button.clicked.connect(self.save)
        self.cancel_button.clicked.connect(self.reject)
        for signal in (self.destination.currentIndexChanged, self.filename.textChanged, self.text.textChanged):
            signal.connect(self.invalidate)
        # A model proposal is never itself a completed human review.
        self.workspace.discard(proposal.id)
        self.show_destination()

    def show_destination(self):
        folder = self.destination.currentData()
        self.destination_notice.setText('New file: '+self.locations.get(folder, self.destination.currentText())+
                                        ' / '+self.filename.text())

    def invalidate(self, *args):
        if self.reviewed:
            self.workspace.discard(self.reviewed.id)
        self.reviewed = None
        self.save_button.setEnabled(False)
        self.diff.clear()
        self.notice.setText('Unsaved. Review changes before saving.')
        self.show_destination()

    def controls(self, working):
        self.working = working
        for widget in (self.destination, self.filename, self.text, self.review_button, self.cancel_button):
            widget.setEnabled(not working)
        self.save_button.setEnabled(not working and self.reviewed is not None)

    def review(self):
        if self.working or self.host.busy or self.host.closing:
            return
        self.invalidate()
        folder, path, text = self.destination.currentData(), self.filename.text(), self.text.toPlainText()
        self.controls(True)
        def complete(proposal):
            self.reviewed = proposal
            self.diff.setPlainText(proposal.diff or 'No text changes; a new identical copy will be created.')
            self.notice.setText('Reviewed. Click Save reviewed copy to approve these exact bytes.')
            self.controls(False)
        def failed():
            self.invalidate()
            self.notice.setText(self.host.status.text())
            self.controls(False)
        self.host.run_task(lambda progress: self.workspace.propose(folder, path, text, self.source),
                           complete, failure=failed)

    def save(self):
        if not self.reviewed or self.working or self.host.busy or self.host.closing:
            return
        identifier = self.reviewed.id
        self.controls(True)
        def complete(proposal):
            self.reviewed = None
            self.host.status.setText('Saved new copy: '+proposal.destination_path)
            self.host.refresh_files()
            self.host.invalidate_mentions()
            self.controls(False)
            self.accept()
        def failed():
            self.invalidate()
            message = self.host.status.text()
            self.notice.setText(message+(' Request a fresh draft from the current source.'
                                        if 'Source changed' in message else ' Review again before saving.'))
            self.controls(False)
        self.host.run_task(lambda progress: self.workspace.approve(identifier), complete, failure=failed)

    def reject(self):
        if self.working:
            return
        self.invalidate()
        super().reject()

    def closeEvent(self, event):
        if self.working:
            event.ignore()
        else:
            self.invalidate()
            event.accept()
