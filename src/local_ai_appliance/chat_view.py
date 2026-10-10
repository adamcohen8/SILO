"""Native, selectable plain-text chat bubbles; no HTML or external resources."""
from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLayout, QListWidget, QListWidgetItem, QPlainTextEdit, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from .desktop import label


class ChatComposer(QPlainTextEdit):
    submitted = Signal()
    mentions_requested = Signal()

    def __init__(self):
        super().__init__()
        self.catalog = None
        self._mention_span = None
        self.popup = QListWidget(self)
        self.popup.setWindowFlags(Qt.WindowType.ToolTip)
        self.popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.popup.setStyleSheet('QListWidget { background: #1e3044; color: #e5ecf5; border: 1px solid #59718d; padding: 4px; } '
                                 'QListWidget::item { padding: 7px; } QListWidget::item:selected { background: #365b82; }')
        self.popup.itemClicked.connect(self.choose_mention)
        self.textChanged.connect(self.update_mentions)
        self.cursorPositionChanged.connect(self.update_mentions)

    def set_catalog(self, catalog):
        self.catalog = catalog
        self.update_mentions()

    def active_mention(self):
        import re
        cursor = self.textCursor()
        # QTextCursor positions count UTF-16 units. Use selectedText to avoid
        # slicing at a wrong character when the message includes an emoji.
        start = cursor.position()
        cursor.setPosition(0, cursor.MoveMode.KeepAnchor)
        before = cursor.selectedText().replace('\u2029', '\n')
        match = re.search(r'(?<![\w@/\\:])([@/])("[^"\r\n]*|[^\s"<>()[\]{};,!?:]*)$', before)
        if not match:
            return None
        token = match.group(0)
        return (start-len(token.encode('utf-16-le'))//2, start, match.group(1), match.group(2).lstrip('"'))

    def update_mentions(self):
        active = self.active_mention()
        previous = self._mention_span
        self._mention_span = active
        self.popup.clear()
        if not active or not self.isEnabled():
            self.popup.hide()
            return
        if previous is None:
            # Refresh on a new trigger so files added outside the app appear.
            # Filtering an existing mention remains immediate and metadata-only.
            self.mentions_requested.emit()
        if self.catalog is None:
            self.mentions_requested.emit()
            self.popup.hide()
            return
        for mention in self.catalog.suggestions(active[2], active[3]):
            item = QListWidgetItem(mention.token)
            item.setData(Qt.ItemDataRole.UserRole, mention)
            location = self.catalog.locations.get(mention.folder_id, mention.alias)
            item.setToolTip(location+(' / '+mention.path if mention.path else ''))
            self.popup.addItem(item)
        if not self.popup.count():
            self.popup.hide()
            return
        self.popup.setCurrentRow(0)
        self.popup.resize(min(660, max(300, self.width())), min(280, self.popup.sizeHintForRow(0)*self.popup.count()+12))
        anchor = self.mapToGlobal(self.cursorRect().topLeft())
        # Open above the composer so the popup fits near the window bottom.
        self.popup.move(anchor.x(), anchor.y()-self.popup.height()-4)
        self.popup.show()

    def choose_mention(self, item):
        active = self.active_mention()
        if not item or not active:
            self.popup.hide()
            return
        mention = item.data(Qt.ItemDataRole.UserRole)
        cursor = self.textCursor()
        cursor.setPosition(active[0])
        cursor.setPosition(active[1], cursor.MoveMode.KeepAnchor)
        cursor.insertText(mention.token+' ')
        self.setTextCursor(cursor)
        self.popup.hide()
        self.setFocus()

    def focusOutEvent(self, event):
        # Allow a click on the non-focus-taking suggestion window to complete.
        QTimer.singleShot(0, lambda: self.popup.hide() if not self.hasFocus() else None)
        super().focusOutEvent(event)

    def hideEvent(self, event):
        self.popup.hide()
        super().hideEvent(event)

    def keyPressEvent(self, event):
        if self.popup.isVisible():
            if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab} and not event.modifiers():
                self.choose_mention(self.popup.currentItem())
                event.accept()
                return
            if event.key() in {Qt.Key.Key_Up, Qt.Key.Key_Down}:
                step = 1 if event.key() == Qt.Key.Key_Down else -1
                self.popup.setCurrentRow((self.popup.currentRow()+step) % self.popup.count())
                event.accept()
                return
            if event.key() == Qt.Key.Key_Escape:
                self.popup.hide()
                event.accept()
                return
        if (event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}
                and event.modifiers() in {Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ControlModifier}):
            self.submitted.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


class ChatTranscript(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setObjectName('chatTranscript')
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body = QWidget()
        self.body.setObjectName('chatBody')
        self.messages = QVBoxLayout(self.body)
        self.messages.setContentsMargins(12, 12, 12, 12)
        self.messages.setSpacing(14)
        self.messages.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.setWidget(self.body)
        self._messages = []
        self._rows = []
        self.viewport().installEventFilter(self)
        self.verticalScrollBar().rangeChanged.connect(lambda _low, _high: self._scroll_to_bottom())
        self.setStyleSheet('''
            QScrollArea#chatTranscript, QWidget#chatBody, QWidget#messageRow { background: transparent; border: none; }
            QFrame#userMessage { background: #253b52; border-radius: 10px; }
            QFrame#assistantMessage { background: #192737; border-radius: 10px; }
            QFrame#userMessage QLabel, QFrame#assistantMessage QLabel { background: transparent; border: none; }
        ''')
        self.clear()

    def set_messages(self, messages):
        self._messages = list(messages)
        self._rows = []
        messages = self._messages
        while self.messages.count():
            item = self.messages.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        if not messages:
            welcome = label('Start a conversation\n\nAsk a question, or add a folder to work with your documents.', 'muted')
            welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.messages.addWidget(welcome, 1)
        for role, text in messages:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            bubble = QFrame()
            bubble.setObjectName('userMessage' if role == 'user' else 'assistantMessage')
            layout = QVBoxLayout(bubble)
            layout.setContentsMargins(14, 10, 14, 12)
            layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
            title = label('You' if role == 'user' else 'Nemotron', 'sectionTitle')
            title.setFixedHeight(24)
            layout.addWidget(title)
            content = label(text)
            content.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
            content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            layout.addWidget(content)
            if role == 'user':
                row.addStretch(1)
                row.addWidget(bubble, 4)
            else:
                row.addWidget(bubble, 4)
                row.addStretch(1)
            wrapper = QWidget()
            wrapper.setObjectName('messageRow')
            wrapper.setLayout(row)
            self.messages.addWidget(wrapper)
            self._rows.append((wrapper, bubble, content, title))
        if messages:
            self.messages.addStretch(1)
        self._reflow()
        QTimer.singleShot(0, self._reflow)

    def eventFilter(self, watched, event):
        if watched is self.viewport() and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self._reflow)
        return super().eventFilter(watched, event)

    def _reflow(self):
        # Scroll areas don't propagate wrapped QLabel heights reliably through
        # nested row layouts. Measure at the actual bubble width explicitly.
        width = max(80, int((self.viewport().width()-24)*.8))
        height = 24
        for wrapper, bubble, content, title in self._rows:
            bubble.setFixedWidth(width)
            title.setFixedHeight(max(24, title.heightForWidth(max(1, width-28))))
            content_height = max(17, content.heightForWidth(max(1, width-28)))
            content.setFixedHeight(content_height)
            row_height = title.height()+content_height+22+bubble.layout().spacing()
            wrapper.setFixedHeight(row_height)
            height += row_height
        height += max(0, len(self._rows)-1)*self.messages.spacing()
        self.body.setMinimumHeight(height if self._rows else 0)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def set_conversation(self, turns):
        self.set_messages([(role, text) for prompt, answer in turns
                           for role, text in (('user', prompt), ('assistant', answer))])

    def add_message(self, role, text):
        self.set_messages(self._messages+[(role, text)])

    # Plain-text view operations used by the controller and diagnostic runners.
    def toPlainText(self):
        return '\n\n'.join(('You' if role == 'user' else 'Nemotron')+'\n'+text for role, text in self._messages)

    def setPlainText(self, text):
        self.set_messages([('assistant', text)] if text else [])

    def appendPlainText(self, text):
        self.add_message('assistant', text)

    def clear(self):
        self.set_messages([])

    def isReadOnly(self):
        return all(not child.textInteractionFlags() & Qt.TextInteractionFlag.TextEditable
                   for child in self.body.findChildren(QLabel))
