"""Series hero with blurred cover, cover card, and collapsible prose."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..animations import animate_height
from ...models import ChapterGroup, Series
from ...names import human_bytes, human_date
from .common import FlowLayout, IconButton, draw_icon


class CoverView(QWidget):
    def __init__(self, width: int = 156, height: int = 214, parent=None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.pixmap: QPixmap | None = None
        self.title = ""

    def set_cover(self, pixmap: QPixmap | None, title: str = "") -> None:
        self.pixmap = pixmap
        self.title = title
        self.update()

    def paintEvent(self, event) -> None:
        tokens = theme.tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        rect = QRectF(self.rect()).adjusted(5, 5, -5, -5)
        shadow = theme.qcolor(tokens["shadow"], 95)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow)
        painter.drawRoundedRect(rect.translated(0, 8), 16, 16)
        clip = QPainterPath()
        clip.addRoundedRect(rect, 14, 14)
        painter.save()
        painter.setClipPath(clip)
        if self.pixmap and not self.pixmap.isNull():
            source = self.pixmap.rect()
            target_ratio = rect.width() / rect.height()
            source_ratio = source.width() / max(1, source.height())
            if source_ratio > target_ratio:
                crop = int(source.height() * target_ratio)
                source = source.adjusted((source.width() - crop) // 2, 0, -(source.width() - crop) // 2, 0)
            else:
                crop = int(source.width() / target_ratio)
                source = source.adjusted(0, (source.height() - crop) // 2, 0, -(source.height() - crop) // 2)
            painter.drawPixmap(rect.toRect(), self.pixmap, source)
        else:
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0, QColor(tokens["raised"]))
            gradient.setColorAt(1, QColor(tokens["line"]))
            painter.fillRect(rect, gradient)
            painter.setPen(QColor(tokens["muted"]))
            painter.setFont(theme.font("display", 36, QFont.Weight.Bold))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "y")
        painter.restore()
        painter.setPen(QPen(QColor(tokens["line"]), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 14, 14)


class DetailHero(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(296)
        self._backdrop: QPixmap | None = None
        self.series: Series | None = None
        self.groups: list[ChapterGroup] = []
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(30, 22, 30, 26)
        outer.setSpacing(6)
        top = QHBoxLayout()
        self.back = IconButton("back", "Back  ·  Esc", 36)
        self.back.clicked.connect(self.back_requested.emit)
        top.addWidget(self.back)
        top.addStretch(1)
        outer.addLayout(top)
        outer.addSpacing(4)

        row = QHBoxLayout()
        row.setSpacing(24)
        self.cover = CoverView()
        row.addWidget(self.cover, alignment=Qt.AlignmentFlag.AlignTop)
        info = QVBoxLayout()
        info.setSpacing(8)
        self.eyebrow = QLabel("SERIES")
        self.eyebrow.setProperty("role", "eyebrow")
        info.addWidget(self.eyebrow)
        self.title = QLabel("")
        self.title.setProperty("role", "display")
        self.title.setWordWrap(True)
        self.title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        info.addWidget(self.title)
        self.meta = QLabel("")
        self.meta.setProperty("role", "muted")
        self.meta.setWordWrap(True)
        info.addWidget(self.meta)
        self.authors = QLabel("")
        self.authors.setProperty("role", "muted")
        self.authors.setWordWrap(True)
        info.addWidget(self.authors)
        self.genres_widget = QWidget()
        self.genres_layout = FlowLayout(self.genres_widget, spacing=6)
        info.addWidget(self.genres_widget)
        self.stats = QLabel("")
        self.stats.setProperty("role", "small")
        info.addWidget(self.stats)
        info.addStretch(1)
        row.addLayout(info, 1)
        outer.addLayout(row)
        self.meta_row = QHBoxLayout()
        self.tags = QLabel("")
        self.tags.setProperty("role", "small")
        self.tags.setWordWrap(True)
        outer.addWidget(self.tags)

    def set_series(self, series: Series, groups: list[ChapterGroup]) -> None:
        self.series = series
        self.groups = groups
        self.cover.title = series.title
        self.eyebrow.setText((series.type or "SERIES").upper())
        self.title.setText(series.title)
        bits = [series.status, series.year, series.content_rating]
        if series.score:
            bits.append("★ " + series.score)
        self.meta.setText("   ·   ".join(bit for bit in bits if bit))
        author_bits = []
        if series.authors:
            author_bits.append("story  " + ", ".join(series.authors))
        if series.artists:
            author_bits.append("art  " + ", ".join(series.artists))
        self.authors.setText("      ".join(author_bits))
        while self.genres_layout.count():
            item = self.genres_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        for genre in series.genres[:8]:
            chip = QLabel(genre)
            chip.setProperty("role", "chip")
            self.genres_layout.addWidget(chip)
        pages = sum(group.pages for group in groups)
        size = sum(group.size for group in groups)
        chapter_word = "chapter" if len(groups) == 1 else "chapters"
        self.stats.setText(
            f"{len(groups)} {chapter_word}   ·   {pages:,} pages   ·   {human_bytes(size)}"
            + (f"   ·   started {human_date_from_text(series.start_date)}" if series.start_date else "")
        )
        tags = "   ".join(series.tags[:8])
        if len(series.tags) > 8:
            tags += f"   +{len(series.tags) - 8}"
        self.tags.setText(tags)
        self.genres_widget.updateGeometry()
        self.update()

    def set_backdrop(self, pixmap: QPixmap) -> None:
        self.cover.set_cover(pixmap, self.series.title if self.series else "")
        if pixmap.isNull():
            self._backdrop = None
            self.update()
            return
        small = pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        self._backdrop = small.scaled(max(1200, self.width()), 420, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        self.update()

    def paintEvent(self, event) -> None:
        tokens = theme.tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        rect = QRectF(self.rect())
        painter.fillRect(rect, QColor(tokens["surface"]))
        if self._backdrop and not self._backdrop.isNull():
            source = self._backdrop.rect()
            target_ratio = rect.width() / max(1.0, rect.height())
            source_ratio = source.width() / max(1, source.height())
            if source_ratio > target_ratio:
                crop = int(source.height() * target_ratio)
                source = source.adjusted((source.width() - crop) // 2, 0, -(source.width() - crop) // 2, 0)
            else:
                crop = int(source.width() / target_ratio)
                source = source.adjusted(0, (source.height() - crop) // 2, 0, -(source.height() - crop) // 2)
            painter.setOpacity(0.46)
            painter.drawPixmap(rect.toRect(), self._backdrop, source)
            painter.setOpacity(1.0)
        tint = theme.qcolor(tokens["glass"])
        painter.fillRect(rect, tint)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0.0, QColor(0, 0, 0, 10))
        gradient.setColorAt(1.0, QColor(tokens["bg"]))
        painter.fillRect(rect, gradient)
        painter.setPen(QPen(QColor(tokens["line"]), 1))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())


def human_date_from_text(value: str) -> str:
    return value.strip()[:10] if value else ""


class CollapsibleText(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._expanded = False
        self._full_text = text
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.label = QLabel(text)
        self.label.setProperty("role", "muted")
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.label)
        self.more = QPushButton("Read more")
        self.more.setProperty("variant", "link")
        self.more.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more.clicked.connect(self._toggle)
        layout.addWidget(self.more, alignment=Qt.AlignmentFlag.AlignLeft)
        self._set_collapsed()

    def _set_collapsed(self) -> None:
        self.label.setMaximumHeight(58)
        self.more.setText("Read more")

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        if self._expanded:
            target = max(58, self.label.sizeHint().height() + 6)
            animate_height(self.label, 58, target, 240)
            self.more.setText("Show less")
        else:
            animate_height(self.label, self.label.height(), 58, 200)
            self.more.setText("Read more")

    def setText(self, text: str) -> None:
        self._full_text = text
        self.label.setText(text)
        self._set_collapsed()
        self.setVisible(bool(text))


class DetailBody(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("card", "true")
        self.setFrameShape(QFrame.Shape.NoFrame)
