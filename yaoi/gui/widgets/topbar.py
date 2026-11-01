"""Top bar: context, search, and the one global status pill."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit

from .. import theme
from .common import StatusPill, icon_pixmap


class TopBar(QFrame):
    search_requested = pyqtSignal(str)
    status_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(76)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(30, 0, 30, 0)
        layout.setSpacing(18)

        self.context = QLabel("Search")
        self.context.setProperty("role", "h2")
        layout.addWidget(self.context)
        hint = QLabel("Find your next obsession")
        hint.setProperty("role", "small")
        layout.addWidget(hint)
        layout.addStretch(1)

        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText("Search titles or paste a series URL…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(360)
        self.search.setMinimumHeight(40)
        icon = QIcon(icon_pixmap("search", theme.tokens()["muted"], 18))
        action = QAction(icon, "search", self.search)
        self.search.addAction(action, QLineEdit.ActionPosition.LeadingPosition)
        self.search.returnPressed.connect(self._submit)
        layout.addWidget(self.search)

        self.status = StatusPill()
        self.status.set_state("idle", "idle")
        self.status.clicked.connect(self.status_clicked.emit)
        layout.addWidget(self.status)

    def _submit(self) -> None:
        text = self.search.text().strip()
        if text:
            self.search_requested.emit(text)

    def set_title(self, title: str) -> None:
        self.context.setText(title)

    def focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def set_search(self, text: str) -> None:
        self.search.setText(text)

    def set_status(self, text: str, state: str) -> None:
        self.status.set_state(text, state)
