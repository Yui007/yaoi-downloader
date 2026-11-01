"""Cover grid: a custom delegate, hover lift, and a staggered reveal."""

from __future__ import annotations

import hashlib
import time

from PyQt6.QtCore import (
    QEasingCurve,
    QPoint,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import QListView, QStyle, QStyledItemDelegate, QStyleOptionViewItem

from .. import theme
from ..models import CARD_ROLE, COVER_ROLE, FADE_ROLE, SeriesGridModel


def _qcolor(value: str, alpha: int | None = None) -> QColor:
    return theme.qcolor(value, alpha)


class CoverDelegate(QStyledItemDelegate):
    def __init__(self, view: "CoverGrid"):
        super().__init__(view)
        self.view = view

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        return QSize(208, 322)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        tokens = theme.tokens()
        card = index.data(CARD_ROLE)
        if card is None:
            return
        pixmap = index.data(COVER_ROLE)
        fade = index.data(FADE_ROLE) or 0.0
        hover = self.view.hover_value if index.row() == self.view.hover_row else 0.0
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        base = QRectF(option.rect).adjusted(6, 6, -6, -6)
        lift = -3.5 * hover
        card_rect = base.translated(0, lift)
        painter.setOpacity(max(0.02, fade))

        shadow = QColor(tokens["shadow"])
        for step, alpha in ((8, 16), (4, 20), (1, 28)):
            shadow.setAlpha(int(alpha * (0.7 + 0.3 * hover)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shadow)
            painter.drawRoundedRect(card_rect.translated(0, step * 0.7), 16, 16)

        clip = QPainterPath()
        clip.addRoundedRect(card_rect, 16, 16)
        painter.save()
        painter.setClipPath(clip)
        painter.fillRect(card_rect, _qcolor(tokens["surface"]))

        if pixmap is not None and not pixmap.isNull():
            source = pixmap.rect()
            target_ratio = card_rect.width() / max(1.0, card_rect.height())
            source_ratio = source.width() / max(1, source.height())
            if source_ratio > target_ratio:
                crop_width = int(source.height() * target_ratio)
                source = source.adjusted((source.width() - crop_width) // 2, 0, -(source.width() - crop_width) // 2, 0)
            else:
                crop_height = int(source.width() / target_ratio)
                source = source.adjusted(0, (source.height() - crop_height) // 2, 0, -(source.height() - crop_height) // 2)
            painter.drawPixmap(card_rect.toRect(), pixmap, source)
        else:
            seed = int(hashlib.sha1(card.title.encode()).hexdigest()[:6], 16)
            hue = seed % 360
            top = QColor.fromHsl(hue, 70, 24 if tokens["name"] == "ink" else 78)
            bottom = QColor.fromHsl((hue + 32) % 360, 60, 15 if tokens["name"] == "ink" else 64)
            gradient = QLinearGradient(card_rect.topLeft(), card_rect.bottomRight())
            gradient.setColorAt(0, top)
            gradient.setColorAt(1, bottom)
            painter.fillRect(card_rect, gradient)
            painter.setPen(QColor(255, 255, 255, 90))
            painter.setFont(theme.font("display", 32, QFont.Weight.Bold))
            initials = "".join(word[0] for word in card.title.split()[:2]).upper() or "Y"
            painter.drawText(card_rect, Qt.AlignmentFlag.AlignCenter, initials)

        overlay = QLinearGradient(card_rect.left(), card_rect.bottom() - 130, card_rect.left(), card_rect.bottom())
        overlay.setColorAt(0, QColor(0, 0, 0, 0))
        overlay.setColorAt(1, QColor(0, 0, 0, 220))
        painter.fillRect(QRectF(card_rect.left(), card_rect.bottom() - 150, card_rect.width(), 150), overlay)

        badge = QRectF(card_rect.left() + 11, card_rect.top() + 11, 0, 0)
        if card.status:
            metrics = QFontMetrics(theme.font("body", 8, QFont.Weight.DemiBold))
            width = metrics.horizontalAdvance(card.status) + 24
            badge.setWidth(width)
            badge.setHeight(22)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(8, 10, 13, 155))
            painter.drawRoundedRect(badge, 11, 11)
            dot = _qcolor(tokens["ok"] if card.status.lower() == "ongoing" else tokens["muted"])
            painter.setBrush(dot)
            painter.drawEllipse(QRectF(badge.left() + 8, badge.center().y() - 2.5, 5, 5))
            painter.setPen(QColor(255, 255, 255, 220))
            painter.setFont(theme.font("body", 8, QFont.Weight.DemiBold))
            painter.drawText(badge.adjusted(17, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, card.status)

        if card.rating:
            rating_rect = QRectF(card_rect.right() - 56, card_rect.top() + 11, 45, 22)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(8, 10, 13, 155))
            painter.drawRoundedRect(rating_rect, 11, 11)
            painter.setPen(QColor(255, 255, 255, 220))
            painter.setFont(theme.font("body", 8.5, QFont.Weight.DemiBold))
            painter.drawText(rating_rect, Qt.AlignmentFlag.AlignCenter, "★ " + card.rating)

        text_left = card_rect.left() + 13
        text_width = card_rect.width() - 26
        title_rect = QRectF(text_left, card_rect.bottom() - 66, text_width, 46)
        painter.setPen(QColor(255, 255, 255, 245))
        painter.setFont(theme.font("body", 11.5, QFont.Weight.Bold))
        flags = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom) | int(Qt.TextFlag.TextWordWrap)
        painter.drawText(title_rect, flags, card.title)

        meta_rect = QRectF(text_left, card_rect.bottom() - 21, text_width, 15)
        painter.setPen(QColor(255, 255, 255, 180))
        painter.setFont(theme.font("body", 8.5, QFont.Weight.Medium))
        bits = []
        if card.chapters:
            bits.append(f"{card.chapters} ch")
        if card.languages:
            bits.append(", ".join(card.languages[:2]))
        painter.drawText(meta_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "  ·  ".join(bits))

        if hover > 0.01:
            painter.setOpacity(fade * hover)
            genre_rect = QRectF(text_left, card_rect.bottom() - 92, text_width, 18)
            painter.setPen(_qcolor(tokens["accent_soft"]))
            painter.setFont(theme.font("body", 8, QFont.Weight.DemiBold))
            painter.drawText(
                genre_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                "  ·  ".join(card.genres[:2]) or "open series",
            )
            painter.setPen(QPen(_qcolor(tokens["accent"], int(210 * hover)), 1.4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(card_rect.adjusted(0.5, 0.5, -0.5, -0.5), 16, 16)
        painter.restore()
        painter.restore()


class CoverGrid(QListView):
    activated = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setUniformItemSizes(True)
        self.setSpacing(0)
        self.setGridSize(QSize(208, 322))
        self.setSelectionMode(QListView.SelectionMode.NoSelection)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMouseTracking(True)
        self.setFrameShape(QListView.Shape.NoFrame)
        self.setItemDelegate(CoverDelegate(self))
        self.hover_row = -1
        self.hover_value = 0.0
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(170)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._set_hover)
        self._reveal_timer = QTimer(self)
        self._reveal_timer.setInterval(16)
        self._reveal_timer.timeout.connect(self._reveal_tick)
        self._reveal_until = 0.0
        self.clicked.connect(self._activate)

    def setModel(self, model) -> None:
        super().setModel(model)
        self.reveal()

    def reveal(self) -> None:
        self._reveal_until = time.monotonic() + 1.5
        self._reveal_timer.start()

    def _reveal_tick(self) -> None:
        if time.monotonic() > self._reveal_until:
            self._reveal_timer.stop()
        self.viewport().update()

    def _set_hover(self, value) -> None:
        self.hover_value = float(value)
        self.viewport().update()

    def _animate_hover(self) -> None:
        if not theme.motion():
            self.hover_value = 1.0
            return
        self._hover_anim.stop()
        self._hover_anim.setStartValue(0.0)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()

    def mouseMoveEvent(self, event) -> None:
        index = self.indexAt(event.position().toPoint())
        row = index.row() if index.isValid() else -1
        if row != self.hover_row:
            self.hover_row = row
            if row >= 0:
                self._animate_hover()
            else:
                self.hover_value = 0.0
            self.viewport().update()
        self.setCursor(Qt.CursorShape.PointingHandCursor if row >= 0 else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self.hover_row = -1
        self.hover_value = 0.0
        self.viewport().update()
        super().leaveEvent(event)

    def _activate(self, index) -> None:
        card = index.data(CARD_ROLE) if index.isValid() else None
        if card is not None:
            self.activated.emit(card.url)
