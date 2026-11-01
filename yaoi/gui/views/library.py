"""Library room: live queue and the finished shelf."""

from __future__ import annotations

import time
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..animations import fade_out
from ..models import SeriesCard
from ..widgets.common import EmptyState, IconButton, SegmentedControl, icon_pixmap
from ..widgets.job import JobCard
from ... import config
from ...library import LibrarySeries, open_path, scan_library


class CoverThumb(QWidget):
    def __init__(self, size=(54, 72), parent=None):
        super().__init__(parent)
        self.setFixedSize(*size)
        self.pixmap: QPixmap | None = None
        self.title = ""

    def set(self, pixmap: QPixmap | None, title: str = "") -> None:
        self.pixmap = pixmap
        self.title = title
        self.update()

    def paintEvent(self, event) -> None:
        tokens = theme.tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        rect = self.rect()
        path = QPainterPath()
        path.addRoundedRect(rect.x() + 1, rect.y() + 1, rect.width() - 2, rect.height() - 2, 9, 9)
        painter.setClipPath(path)
        if self.pixmap and not self.pixmap.isNull():
            source = self.pixmap.rect()
            ratio = rect.width() / max(1, rect.height())
            if source.width() / max(1, source.height()) > ratio:
                crop = int(source.height() * ratio)
                source = source.adjusted((source.width() - crop) // 2, 0, -(source.width() - crop) // 2, 0)
            else:
                crop = int(source.width() / ratio)
                source = source.adjusted(0, (source.height() - crop) // 2, 0, -(source.height() - crop) // 2)
            painter.drawPixmap(rect, self.pixmap, source)
        else:
            painter.fillRect(rect, theme.qcolor(tokens["raised"]))
            painter.setPen(theme.qcolor(tokens["muted"]))
            painter.setFont(theme.font("display", 18, QFont.Weight.Bold))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, (self.title[:1] or "y").upper())
        painter.setClipping(False)
        painter.setPen(theme.qcolor(tokens["line"]))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.x() + 1, rect.y() + 1, rect.width() - 2, rect.height() - 2, 9, 9)


class LibraryRow(QFrame):
    def __init__(self, item: LibrarySeries, parent=None):
        super().__init__(parent)
        self.item = item
        self.setProperty("card", "true")
        self.setFixedHeight(96)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 16, 12)
        layout.setSpacing(14)
        self.cover = CoverThumb()
        if item.cover is not None:
            pixmap = QPixmap(str(item.cover))
            if not pixmap.isNull():
                self.cover.set(pixmap, item.title)
        layout.addWidget(self.cover)
        info = QVBoxLayout()
        info.setSpacing(3)
        title = QLabel(item.title)
        title.setProperty("role", "h2")
        title.setWordWrap(True)
        info.addWidget(title)
        updated = time.strftime("%Y-%m-%d", time.localtime(item.updated))
        chapter_word = "chapter" if item.chapters == 1 else "chapters"
        meta = QLabel(f"{item.chapters} {chapter_word}   ·   {item.size_label}   ·   updated {updated}")
        meta.setProperty("role", "small")
        info.addWidget(meta)
        layout.addLayout(info, 1)
        reveal = QPushButton("Reveal")
        reveal.setProperty("variant", "ghost")
        reveal.clicked.connect(lambda: open_path(item.path))
        layout.addWidget(reveal)
        arrow = IconButton("arrow", "Open folder", 32)
        arrow.clicked.connect(lambda: open_path(item.path))
        layout.addWidget(arrow)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseDoubleClickEvent(self, event) -> None:
        open_path(self.item.path)
        super().mouseDoubleClickEvent(event)


class LibraryView(QWidget):
    search_requested = pyqtSignal()

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.settings = settings
        self._cards: dict[object, JobCard] = {}
        self._running = 0
        self._build()
        self.refresh_done()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(30, 24, 30, 24)
        outer.setSpacing(14)
        eyebrow = QLabel("YOUR SHELF")
        eyebrow.setProperty("role", "eyebrow")
        outer.addWidget(eyebrow)
        title = QLabel("Everything you've pulled down.")
        title.setProperty("role", "display")
        title.setWordWrap(True)
        outer.addWidget(title)
        subtitle = QLabel(
            "Active work stays honest here — pages, speed, and the exact chapter. "
            "Finished books live in the library, ready for Kavita or Komga."
        )
        subtitle.setProperty("role", "muted")
        subtitle.setWordWrap(True)
        subtitle.setMaximumWidth(740)
        outer.addWidget(subtitle)
        outer.addSpacing(4)

        row = QHBoxLayout()
        self.segments = SegmentedControl(["Active", "Done"])
        self.segments.changed.connect(self.set_tab)
        row.addWidget(self.segments)
        row.addStretch(1)
        self.count = QLabel("")
        self.count.setProperty("role", "small")
        row.addWidget(self.count)
        self.open_library = QPushButton("Open library")
        self.open_library.setProperty("variant", "ghost")
        self.open_library.clicked.connect(self._open_library)
        row.addWidget(self.open_library)
        outer.addLayout(row)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)

        self.active_scroll = QScrollArea()
        self.active_scroll.setWidgetResizable(True)
        self.active_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.active_content = QWidget()
        self.active_content.setObjectName("Transparent")
        self.active_layout = QVBoxLayout(self.active_content)
        self.active_layout.setContentsMargins(0, 4, 6, 20)
        self.active_layout.setSpacing(12)
        self.active_layout.addStretch(1)
        self.active_scroll.setWidget(self.active_content)
        self.stack.addWidget(self.active_scroll)

        self.done_scroll = QScrollArea()
        self.done_scroll.setWidgetResizable(True)
        self.done_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.done_content = QWidget()
        self.done_content.setObjectName("Transparent")
        self.done_layout = QVBoxLayout(self.done_content)
        self.done_layout.setContentsMargins(0, 4, 6, 20)
        self.done_layout.setSpacing(10)
        self.done_layout.addStretch(1)
        self.done_scroll.setWidget(self.done_content)
        self.stack.addWidget(self.done_scroll)
        self.set_tab(0)
        self._refresh_active_empty()

    def _open_library(self) -> None:
        open_path(config.paths(self.settings)["library"])

    def set_tab(self, index: int) -> None:
        self.segments.set_current(index)
        self.stack.setCurrentIndex(index)
        if index == 1:
            self.refresh_done()
        self._update_count()

    def _update_count(self) -> None:
        if self.stack.currentIndex() == 0:
            self.count.setText(f"{self._running} running" if self._running else "nothing running")
        else:
            items = scan_library(config.paths(self.settings)["library"])
            total = sum(item.chapters for item in items)
            self.count.setText(
                f"{len(items)} series  ·  {total} {'chapter' if total == 1 else 'chapters'}"
            )

    def add_job(self, runner, series, groups) -> None:
        self._clear_active_empty()
        card = JobCard(runner, series, groups)
        self._cards[runner] = card
        self.active_layout.insertWidget(0, card)
        self._running += 1
        self.set_tab(0)
        self._update_count()
        runner.finished.connect(lambda summary, elapsed: self._job_finished(runner, summary))

    def _job_finished(self, runner, summary) -> None:
        self._running = max(0, self._running - 1)
        self._update_count()
        QTimer.singleShot(1200, self.refresh_done)
        QTimer.singleShot(4200, lambda: self._remove_card(runner))

    def _remove_card(self, runner) -> None:
        card = self._cards.pop(runner, None)
        if card is None:
            return
        def done() -> None:
            card.setParent(None)
            card.deleteLater()
            self._refresh_active_empty()
        fade_out(card, 240, done)

    def _clear_active_empty(self) -> None:
        for index in reversed(range(self.active_layout.count())):
            item = self.active_layout.itemAt(index)
            widget = item.widget() if item is not None else None
            if isinstance(widget, EmptyState):
                self.active_layout.takeAt(index)
                widget.deleteLater()

    def _refresh_active_empty(self) -> None:
        if self._cards:
            self._clear_active_empty()
            return
        # leave the stretch and an empty state at the top
        while self.active_layout.count() > 1:
            item = self.active_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        state = EmptyState(
            "queue",
            "No downloads running",
            "Find a series, pick a few chapters, and the queue will keep an honest count.",
            "Find a series",
        )
        state.action.connect(self.search_requested.emit)
        self.active_layout.insertWidget(0, state)

    def refresh_done(self) -> None:
        while self.done_layout.count() > 1:
            item = self.done_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        items = scan_library(config.paths(self.settings)["library"])
        self._done_items = items
        if not items:
            state = EmptyState(
                "library",
                "Your shelf is empty",
                "Finished chapters appear here, one folder per series, ready for your reader.",
                "Search the catalogue",
            )
            state.action.connect(self.search_requested.emit)
            self.done_layout.insertWidget(0, state)
        else:
            for item in items:
                self.done_layout.insertWidget(self.done_layout.count() - 1, LibraryRow(item))
        self._update_count()

    def active_count(self) -> int:
        return self._running
