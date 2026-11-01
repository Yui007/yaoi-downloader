"""Search room: hero, segmented discovery, and the cover grid."""

from __future__ import annotations

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..animations import fade_in
from ..bridge import CoverLoader, Tasks
from ..models import SeriesGridModel
from ..widgets.common import EmptyState, SegmentedControl, Spinner, icon_pixmap
from ..widgets.grid import CoverGrid
from ...app_context import source_from_settings


class SearchView(QWidget):
    open_series = pyqtSignal(str)
    status_message = pyqtSignal(str, str)

    def __init__(self, settings: dict, tasks: Tasks, covers: CoverLoader, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.settings = settings
        self.tasks = tasks
        self.covers = covers
        self._loaded = False
        self._kind = "trending"
        self._query = ""
        self._request_id = 0
        self._build()
        self.covers.ready.connect(self._cover_ready)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(30, 24, 30, 26)
        outer.setSpacing(14)

        eyebrow = QLabel("DISCOVER")
        eyebrow.setProperty("role", "eyebrow")
        outer.addWidget(eyebrow)
        title = QLabel("Find your next obsession.")
        title.setProperty("role", "display")
        title.setWordWrap(True)
        outer.addWidget(title)
        subtitle = QLabel(
            "Paste a series URL, or drift through what everyone else is reading. "
            "The shelf remembers everything you finish."
        )
        subtitle.setProperty("role", "muted")
        subtitle.setWordWrap(True)
        subtitle.setMaximumWidth(720)
        outer.addWidget(subtitle)
        outer.addSpacing(6)

        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        self.field = QLineEdit()
        self.field.setProperty("hero", "true")
        self.field.setPlaceholderText("Search titles or paste a yaoi.me series URL…")
        self.field.setClearButtonEnabled(True)
        self.field.setMinimumHeight(50)
        self.field.returnPressed.connect(self._submit)
        icon = QIcon(icon_pixmap("search", theme.tokens()["muted"], 19))
        action = QAction(icon, "search", self.field)
        self.field.addAction(action, QLineEdit.ActionPosition.LeadingPosition)
        search_row.addWidget(self.field, 1)
        self.go = QPushButton("Search")
        self.go.setProperty("variant", "primary")
        self.go.setMinimumHeight(50)
        self.go.setMinimumWidth(110)
        self.go.clicked.connect(self._submit)
        search_row.addWidget(self.go)
        outer.addLayout(search_row)
        outer.addSpacing(6)

        row = QHBoxLayout()
        self.segments = SegmentedControl(["Trending", "Latest", "Results"])
        self.segments.changed.connect(self._segment_changed)
        row.addWidget(self.segments)
        row.addStretch(1)
        self.count = QLabel("")
        self.count.setProperty("role", "small")
        row.addWidget(self.count)
        outer.addLayout(row)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        self.model = SeriesGridModel(self)
        self.grid = CoverGrid()
        self.grid.setModel(self.model)
        self.grid.activated.connect(self.open_series.emit)
        self.stack.addWidget(self.grid)

        self.loading = QWidget()
        loading_layout = QVBoxLayout(self.loading)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.setSpacing(12)
        loading_layout.addWidget(Spinner(38), alignment=Qt.AlignmentFlag.AlignCenter)
        loading_text = QLabel("Turning the pages…")
        loading_text.setProperty("role", "muted")
        loading_layout.addWidget(loading_text, alignment=Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(self.loading)

        self.empty_holder = QWidget()
        self.empty_layout = QVBoxLayout(self.empty_holder)
        self.empty_layout.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(self.empty_holder)
        self.stack.setCurrentWidget(self.loading)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            self._load("trending")

    def focus_search(self) -> None:
        self.field.setFocus()
        self.field.selectAll()

    def search(self, text: str) -> None:
        text = text.strip()
        if not text:
            self.focus_search()
            return
        if "yaoi.me/series/" in text or text.startswith(("http://", "https://")):
            self.open_series.emit(text)
            return
        self.field.setText(text)
        self._query = text
        self.segments.set_current(2)
        self._load("search", text)

    def _submit(self) -> None:
        self.search(self.field.text())

    def _segment_changed(self, index: int) -> None:
        if index == 0:
            self._kind = "trending"
            self._load("trending")
        elif index == 1:
            self._kind = "latest"
            self._load("latest")
        else:
            if self._query:
                self._kind = "search"
                self._load("search", self._query)
            else:
                self._show_empty("search", "Search the shelf", "Type a title above, then press Enter.", "Search", self.focus_search)

    def _load(self, kind: str, query: str = "") -> None:
        self._kind = kind
        self._query = query or self._query
        self._request_id += 1
        request_id = self._request_id
        self.stack.setCurrentWidget(self.loading)
        self.count.setText("")
        self.segments.set_current({"trending": 0, "latest": 1, "search": 2}.get(kind, 0))
        limit = 30
        if kind == "trending":
            function = lambda: source_from_settings(self.settings).trending(limit)
        elif kind == "latest":
            function = lambda: source_from_settings(self.settings).latest(limit)
        else:
            function = lambda: source_from_settings(self.settings).search(query, limit)
        self.tasks.run(
            function,
            lambda cards, rid=request_id: self._loaded_cards(cards, rid),
            lambda message, rid=request_id: self._load_failed(message, rid),
        )

    def _loaded_cards(self, cards, request_id: int = 0) -> None:
        if request_id != self._request_id:
            return
        self.model.set_cards(cards)
        for card in cards:
            if card.cover:
                cached = self.covers.cached(card.cover)
                if cached is not None:
                    self.model.set_cover(card.cover, cached)
                else:
                    self.covers.request(card.cover)
        if not cards:
            self._show_empty(
                "book",
                "Nothing on that shelf",
                "No titles matched. Try a shorter query or a different spelling.",
                "Clear search",
                self._clear,
            )
            self.count.setText("0 results")
            return
        self.stack.setCurrentWidget(self.grid)
        self.grid.reveal()
        self.grid.scrollToTop()
        label = {
            "trending": "trending now",
            "latest": "fresh releases",
            "search": f"results for “{self._query}”",
        }.get(self._kind, "results")
        self.count.setText(f"{len(cards)} series  ·  {label}")
        fade_in(self.grid, 220)

    def _load_failed(self, message: str, request_id: int = 0) -> None:
        if request_id != self._request_id:
            return
        self.status_message.emit("Could not reach the catalogue.", "fail")
        self._show_empty(
            "book",
            "The shelf is out of reach",
            message,
            "Try again",
            lambda: self._load(self._kind, self._query),
        )

    def _show_empty(self, icon: str, title: str, subtitle: str, action_text: str, action) -> None:
        while self.empty_layout.count():
            item = self.empty_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        state = EmptyState(icon, title, subtitle, action_text)
        state.action.connect(action)
        self.empty_layout.addWidget(state)
        self.stack.setCurrentWidget(self.empty_holder)

    def _clear(self) -> None:
        self.field.clear()
        self._query = ""
        self.segments.set_current(0)
        self._load("trending")

    def _cover_ready(self, url: str, pixmap) -> None:
        self.model.set_cover(url, pixmap)

    def refresh(self) -> None:
        self._load(self._kind, self._query)
