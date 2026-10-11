"""Desktop controls for the same host-owned project backend as the terminal."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QInputDialog, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout
from .desktop import label


class ProjectDialog(QDialog):
    def __init__(self,host):
        super().__init__(host)
        self.host=host; self.backend=host.project_backend
        self.setWindowTitle('Local projects'); self.resize(680,480)
        layout=QVBoxLayout(self)
        layout.addWidget(label('Saved projects retain encrypted conversation and selected folder identities locally.\nCode workspaces and pending approvals are discarded.','muted'))
        self.items=QListWidget(); layout.addWidget(self.items)
        buttons=QHBoxLayout()
        for title,action in [('New',self.create),('Open',self.open),('Close project',self.close_project),
                             ('Instructions',self.instructions),('Retention',self.retention),('Delete',self.delete)]:
            button=QPushButton(title); button.clicked.connect(action); buttons.addWidget(button)
        layout.addLayout(buttons)
        self.notice=label('','muted'); layout.addWidget(self.notice)
        self.refresh()

    def refresh(self):
        self.items.clear()
        for project in self.backend.store.listing():
            item=QListWidgetItem(project['name']+f" · {project['turns']} turns · {project['retention_days']} days"+
                                 (' · Expired' if project['expired'] else ''))
            item.setData(Qt.ItemDataRole.UserRole,project['id']); self.items.addItem(item)
        self.notice.setText('Current: '+self.backend.project.name)

    def selected(self):
        item=self.items.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def run(self,operation):
        if self.host.busy: return
        self.setEnabled(False)
        def finished(value):
            self.setEnabled(True); self.host.project_changed(); self.refresh()
        def failed():
            self.setEnabled(True); self.notice.setText(self.host.status.text())
        self.host.run_task(lambda progress:operation(),finished,failure=failed)

    def create(self):
        name,ok=QInputDialog.getText(self,'New local project','Project name (30-day retention):')
        if ok and name.strip(): self.run(lambda:self.backend.create_project(name.strip()))

    def open(self):
        identifier=self.selected()
        if identifier: self.run(lambda:self.backend.open_project(identifier))

    def close_project(self): self.run(self.backend.close_project)

    def instructions(self):
        if self.backend.record is None: return
        text,ok=QInputDialog.getMultiLineText(self,'Project task instructions','Instructions for this project:',self.backend.record['instructions'])
        if ok: self.run(lambda:self.backend.set_instructions(text))

    def retention(self):
        identifier=self.selected() or (self.backend.project.id if self.backend.record else None)
        if identifier is None:return
        record=self.backend.store.load(identifier,allow_expired=True)
        days,ok=QInputDialog.getInt(self,'Retention','Days since last use:',record['retention_days'],1,365)
        if ok:self.run(lambda:self.backend.set_retention(days) if self.backend.record and self.backend.project.id==identifier
                       else self.backend.store.renew(identifier,days))

    def delete(self):
        identifier=self.selected()
        if identifier and QMessageBox.question(self,'Delete saved project',
                'Delete this project’s retained conversation, instructions and grants? User files stay in their folders.') == QMessageBox.StandardButton.Yes:
            self.run(lambda:self.backend.delete_project(identifier))
