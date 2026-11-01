"""Chapter rows: checkbox, scanlator, and a live painted progress bar."""

from __future__ import annotations

import time

from PyQt6.QtCore import QEasingCurve, QPoint, QRectF, QSize, Qt, QTimer, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QPolygon
from PyQt6.QtWidgets import QListView, QStyledItemDelegate, QStyleOptionViewItem

from .. import theme
from ..models import CHECKED_ROLE, GROUP_ROLE, PROGRESS_ROLE, ChapterModel
from ...names import human_bytes, short_date


def _color(value: str, alpha: int | None = None) -> QColor:
    return theme.qcolor(value, alpha)


class ChapterDelegate(QStyledItemDelegate):
    def __init__(self, view: "ChapterList"):
        super().__init__(view)
        self.view = view

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        return QSize(100, 68)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        tokens = theme.tokens()
        group = index.data(GROUP_ROLE)
        if group is None:
            return
        checked = bool(index.data(CHECKED_ROLE))
        progress = index.data(PROGRESS_ROLE)
        hover = self.view.hover_value if index.row() == self.view.hover_row else 0.0
        row = QRectF(option.rect).adjusted(3, 3, -3, -3)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if hover > 0.01:
            fill = _color(tokens["raised"], int(130 * hover))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(row, 11, 11)
        if checked:
            painter.setPen(QPen(_color(tokens["accent"], 90), 1))
            painter.setBrush(_color(tokens["nav_active"], 80))
            painter.drawRoundedRect(row, 11, 11)

        box = QRectF(row.left() + 15, row.center().y() - 9, 18, 18)
        if checked:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_color(tokens["accent"]))
            painter.drawRoundedRect(box, 5, 5)
            painter.setPen(QPen(QColor("#FFFFFF"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPolyline(
                QPolygon(
                    [
                        QPoint(round(box.left() + 4), round(box.top() + 9)),
                        QPoint(round(box.left() + 7), round(box.top() + 12)),
                        QPoint(round(box.left() + 14), round(box.top() + 5)),
                    ]
                )
            )
        else:
            painter.setPen(QPen(_color(tokens["line"] if hover < 0.4 else tokens["accent"]), 1.4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(box, 5, 5)

        left = row.left() + 46
        state = progress.state if progress else ""
        right_reserved = 248
        text_width = max(80, row.width() - 46 - right_reserved)
        label = group.label
        painter.setPen(QColor(tokens["text"]))
        painter.setFont(theme.font("body", 10.5, QFont.Weight.DemiBold))
        metrics = QFontMetrics(painter.font())
        label = metrics.elidedText(label, Qt.TextElideMode.ElideRight, int(text_width))
        painter.drawText(QRectF(left, row.top() + 13, text_width, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
        if group.extra:
            extra_width = 44
            chip = QRectF(left + min(text_width, metrics.horizontalAdvance(label)) + 10, row.top() + 15, 40, 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_color(tokens["raised"]))
            painter.drawRoundedRect(chip, 8, 8)
            painter.setPen(_color(tokens["warn"]))
            painter.setFont(theme.font("body", 7.5, QFont.Weight.DemiBold))
            painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, "extra")

        meta = f"{short_date(group.created_at)}   ·   {group.pages or '—'} pages   ·   {human_bytes(group.size)}"
        meta_color = tokens["muted"]
        if progress is not None and progress.state == "failed" and progress.message:
            meta = progress.message
            meta_color = tokens["fail"]
        painter.setPen(_color(meta_color))
        painter.setFont(theme.font("body", 8.5))
        meta = QFontMetrics(painter.font()).elidedText(meta, Qt.TextElideMode.ElideRight, int(text_width))
        painter.drawText(QRectF(left, row.top() + 34, text_width, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, meta)

        source_width = 224
        source_x = row.right() - right_reserved + 8
        source = group.variant.source_name if group.variant else "—"
        painter.setFont(theme.font("body", 8.5, QFont.Weight.Medium))
        source_metrics = QFontMetrics(painter.font())
        source = source_metrics.elidedText(source, Qt.TextElideMode.ElideRight, source_width)
        painter.setPen(_color(tokens["accent_soft"]))
        painter.drawText(QRectF(source_x, row.top() + 12, source_width, 17), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, source)

        if progress is not None:
            now = time.monotonic()
            value = progress.value_at(now)
            color = {
                "done": tokens["ok"],
                "failed": tokens["fail"],
                "cancelled": tokens["warn"],
                "exporting": tokens["accent_soft"],
            }.get(progress.state, tokens["accent"])
            status_text = {
                "fetching": "reading hashes",
                "downloading": f"downloading {progress.done}/{progress.total}" if progress.total else "downloading",
                "exporting": "sealing",
                "done": "done",
                "failed": "failed",
                "cancelled": "cancelled",
            }.get(progress.state, progress.state)
            if progress.speed and progress.state == "downloading":
                status_text += f"  ·  {human_bytes(progress.speed)}/s"
            painter.setFont(theme.font("body", 8.5, QFont.Weight.DemiBold))
            painter.setPen(_color(color))
            painter.drawText(
                QRectF(source_x, row.top() + 32, source_width, 17),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                status_text,
            )
            track = QRectF(row.left() + 46, row.bottom() - 9, row.width() - 46 - 18, 3)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_color(tokens["line"]))
            painter.drawRoundedRect(track, 1.5, 1.5)
            if value > 0:
                fill = QRectF(track.left(), track.top(), track.width() * value, track.height())
                painter.setBrush(_color(color))
                painter.drawRoundedRect(fill, 1.5, 1.5)
        painter.restore()


class ChapterList(QListView):
    selection_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListView.SelectionMode.NoSelection)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMouseTracking(True)
        self.setFrameShape(QListView.Shape.NoFrame)
        self.setItemDelegate(ChapterDelegate(self))
        self.hover_row = -1
        self.hover_value = 0.0
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(150)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._set_hover)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self.clicked.connect(self._toggle)
        self.setMinimumHeight(210)
        self.setMaximumHeight(470)

    def setModel(self, model) -> None:
        super().setModel(model)
        self._timer.start()

    def _tick(self) -> None:
        model = self.model()
        if model is not None and isinstance(model, ChapterModel) and model.active():
            self.viewport().update()
        elif self.hover_value > 0:
            return

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

    def _toggle(self, index) -> None:
        model = self.model()
        if index.isValid() and isinstance(model, ChapterModel):
            model.toggle(index.row())
            self.selection_changed.emit()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.hover_row >= 0:
            model = self.model()
            if isinstance(model, ChapterModel):
                model.toggle(self.hover_row)
                self.selection_changed.emit()
            return
        super().keyPressEvent(event)

    def fit_to_rows(self, minimum: int = 210, maximum: int = 470) -> None:
        model = self.model()
        rows = model.rowCount() if model is not None else 0
        self.setFixedHeight(max(minimum, min(maximum, rows * 68 + 8)))
