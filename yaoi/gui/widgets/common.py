"""Reusable painted widgets: icons, rail, segmented control, toast, states."""

from __future__ import annotations

import math

from PyQt6.QtCore import (
    QEasingCurve,
    QMargins,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygon,
)
from PyQt6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QWidgetItem,
)

from .. import theme


# ---------------------------------------------------------------- icons

def draw_icon(painter: QPainter, name: str, rect: QRectF, color: str, width: float = 1.7) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

    def p(px: float, py: float) -> QPoint:
        return QPoint(round(x + px / 24 * w), round(y + py / 24 * h))

    def xy(px: float, py: float) -> tuple[int, int]:
        point = p(px, py)
        return point.x(), point.y()

    if name == "search":
        painter.drawEllipse(QRectF(x + w * 0.16, y + h * 0.16, w * 0.48, h * 0.48))
        painter.drawLine(p(15.8, 15.8), p(20.5, 20.5))
    elif name == "library":
        painter.drawRoundedRect(QRectF(x + w * 0.14, y + h * 0.18, w * 0.18, h * 0.64), 1.5, 1.5)
        painter.drawRoundedRect(QRectF(x + w * 0.40, y + h * 0.18, w * 0.18, h * 0.64), 1.5, 1.5)
        painter.drawRoundedRect(QRectF(x + w * 0.66, y + h * 0.18, w * 0.18, h * 0.64), 1.5, 1.5)
    elif name == "queue":
        painter.drawLine(p(12, 3.5), p(12, 14))
        painter.drawPolyline(QPolygon([p(7.5, 10), p(12, 14.5), p(16.5, 10)]))
        painter.drawPolyline(QPolygon([p(4, 17), p(4, 20), p(20, 20), p(20, 17)]))
    elif name == "settings":
        painter.drawEllipse(QRectF(x + w * 0.37, y + h * 0.37, w * 0.26, h * 0.26))
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            painter.drawLine(
                p(12 + math.cos(rad) * 6.2, 12 + math.sin(rad) * 6.2),
                p(12 + math.cos(rad) * 9.2, 12 + math.sin(rad) * 9.2),
            )
    elif name == "back":
        painter.drawLine(p(19, 12), p(5, 12))
        painter.drawPolyline(QPolygon([p(11, 6), p(5, 12), p(11, 18)]))
    elif name == "sun":
        painter.drawEllipse(QRectF(x + w * 0.34, y + h * 0.34, w * 0.32, h * 0.32))
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            painter.drawLine(
                p(12 + math.cos(rad) * 7.4, 12 + math.sin(rad) * 7.4),
                p(12 + math.cos(rad) * 10.2, 12 + math.sin(rad) * 10.2),
            )
    elif name == "moon":
        path = QPainterPath()
        path.moveTo(*xy(15.5, 4.5))
        path.cubicTo(*xy(8.5, 6), *xy(8.5, 18), *xy(15.5, 19.5))
        path.cubicTo(*xy(11, 17), *xy(11, 7), *xy(15.5, 4.5))
        painter.drawPath(path)
    elif name == "play":
        painter.setBrush(QColor(color))
        painter.drawPolygon(QPolygon([p(8, 5), p(19, 12), p(8, 19)]))
    elif name == "pause":
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(QRectF(x + w * 0.33, y + h * 0.27, w * 0.11, h * 0.46), 1.4, 1.4)
        painter.drawRoundedRect(QRectF(x + w * 0.56, y + h * 0.27, w * 0.11, h * 0.46), 1.4, 1.4)
    elif name == "x":
        painter.drawLine(p(6, 6), p(18, 18))
        painter.drawLine(p(18, 6), p(6, 18))
    elif name == "folder":
        path = QPainterPath()
        path.moveTo(*xy(3, 7))
        path.lineTo(*xy(9, 7))
        path.lineTo(*xy(11, 9))
        path.lineTo(*xy(21, 9))
        path.lineTo(*xy(21, 19))
        path.lineTo(*xy(3, 19))
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "download":
        painter.drawLine(p(12, 4), p(12, 15))
        painter.drawPolyline(QPolygon([p(7, 10.5), p(12, 15.5), p(17, 10.5)]))
        painter.drawLine(p(5, 20), p(19, 20))
    elif name == "refresh":
        painter.drawArc(QRectF(x + w * 0.2, y + h * 0.2, w * 0.6, h * 0.6), 35 * 16, 280 * 16)
        painter.drawPolyline(QPolygon([p(18.4, 4.4), p(19.2, 8.2), p(15.4, 9.0)]))
    elif name == "check":
        painter.drawPolyline(QPolygon([p(5, 12.5), p(10, 17.5), p(19.5, 6.5)]))
    elif name == "chevron":
        painter.drawPolyline(QPolygon([p(7, 9.5), p(12, 14.5), p(17, 9.5)]))
    elif name == "arrow":
        painter.drawLine(p(4, 12), p(19, 12))
        painter.drawPolyline(QPolygon([p(13, 6), p(19, 12), p(13, 18)]))
    elif name == "book":
        path = QPainterPath()
        path.moveTo(*xy(4, 6))
        path.cubicTo(*xy(8, 4), *xy(11, 5), *xy(12, 7))
        path.cubicTo(*xy(13, 5), *xy(16, 4), *xy(20, 6))
        path.lineTo(*xy(20, 19))
        path.cubicTo(*xy(16, 17), *xy(13, 18), *xy(12, 20))
        path.cubicTo(*xy(11, 18), *xy(8, 17), *xy(4, 19))
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(p(12, 7), p(12, 20))
    elif name == "heart":
        path = QPainterPath()
        path.moveTo(*xy(12, 20))
        path.cubicTo(*xy(4, 14), *xy(4, 8), *xy(8, 6))
        path.cubicTo(*xy(10, 5), *xy(12, 7), *xy(12, 9))
        path.cubicTo(*xy(12, 7), *xy(14, 5), *xy(16, 6))
        path.cubicTo(*xy(20, 8), *xy(20, 14), *xy(12, 20))
        painter.drawPath(path)
    painter.restore()


def icon_pixmap(name: str, color: str, size: int = 20, width: float = 1.7) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    draw_icon(painter, name, QRectF(0, 0, size, size), color, width)
    painter.end()
    return pixmap


# ---------------------------------------------------------------- buttons

class IconButton(QAbstractButton):
    def __init__(self, name: str, tooltip: str = "", size: int = 34, parent=None):
        super().__init__(parent)
        self.name = name
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip or name)
        self._hover = 0.0
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(150)
        self._hover_anim.valueChanged.connect(self._set_hover)
        self._active = False

    def _set_hover(self, value) -> None:
        self._hover = float(value)
        self.update()

    def _animate_hover(self, target: float) -> None:
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(target)
        self._hover_anim.start()

    def enterEvent(self, event) -> None:
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate_hover(0.0)
        super().leaveEvent(event)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.update()

    def set_name(self, name: str) -> None:
        self.name = name
        self.update()

    def paintEvent(self, event) -> None:
        tokens = theme.tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        if self._hover > 0.01 or self._active:
            color = QColor(tokens["raised"])
            color.setAlpha(int(150 * (1.0 if self._active else self._hover)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(rect, 10, 10)
        color = tokens["accent"] if self._active else (
            tokens["text"] if self._hover > 0.4 else tokens["muted"]
        )
        margin = self.width() * 0.27
        draw_icon(painter, self.name, QRectF(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin), color, 1.7)


class NavButton(IconButton):
    def __init__(self, name: str, tooltip: str, parent=None):
        super().__init__(name, tooltip, 48, parent)
        self.setCheckable(False)

    def paintEvent(self, event) -> None:
        tokens = theme.tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        if self._active:
            fill = QColor(tokens["nav_active"])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, 14, 14)
            bar = QRectF(rect.left() - 1, rect.center().y() - 10, 3, 20)
            painter.setBrush(QColor(tokens["accent"]))
            painter.drawRoundedRect(bar, 1.5, 1.5)
        elif self._hover > 0.01:
            fill = QColor(tokens["raised"])
            fill.setAlpha(int(170 * self._hover))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, 14, 14)
        color = tokens["accent"] if self._active else (
            tokens["text"] if self._hover > 0.4 else tokens["muted"]
        )
        margin = 14
        draw_icon(painter, self.name, QRectF(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin), color, 1.75)


# ---------------------------------------------------------------- segmented

class SegmentedControl(QWidget):
    changed = pyqtSignal(int)

    def __init__(self, labels: list[str], parent=None):
        super().__init__(parent)
        self.labels = list(labels)
        self._current = 0
        self._indicator = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(190)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._set_indicator)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(38)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        metrics = QFontMetrics(theme.font("body", 10, weight=600))
        width = sum(metrics.horizontalAdvance(label) + 34 for label in self.labels) + 8
        self.setMinimumWidth(width)

    def _set_indicator(self, value) -> None:
        self._indicator = float(value)
        self.update()

    def current(self) -> int:
        return self._current

    def set_current(self, index: int, emit: bool = False) -> None:
        if not self.labels:
            return
        index = max(0, min(len(self.labels) - 1, index))
        if index == self._current:
            return
        self._current = index
        self._anim.stop()
        self._anim.setStartValue(self._indicator)
        self._anim.setEndValue(float(index))
        self._anim.start()
        if emit:
            self.changed.emit(index)
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(self.minimumWidth(), 38)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            width = max(1, self.width() - 8)
            index = int((event.position().x() - 4) / (width / max(1, len(self.labels))))
            self.set_current(index, emit=True)
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        tokens = theme.tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        outer = QRectF(self.rect()).adjusted(0, 1, 0, -1)
        painter.setPen(QPen(QColor(tokens["line"]), 1))
        painter.setBrush(QColor(tokens["raised"]))
        painter.drawRoundedRect(outer, 11, 11)
        segment = (outer.width() - 8) / max(1, len(self.labels))
        pill = QRectF(outer.left() + 4 + self._indicator * segment, outer.top() + 4, segment, outer.height() - 8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tokens["surface"]))
        painter.drawRoundedRect(pill, 8, 8)
        painter.setFont(theme.font("body", 9.5, weight=600))
        for index, label in enumerate(self.labels):
            rect = QRectF(outer.left() + 4 + index * segment, outer.top(), segment, outer.height())
            active = abs(self._indicator - index) < 0.5
            painter.setPen(QColor(tokens["accent"] if active else tokens["muted"]))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)


# ---------------------------------------------------------------- toggle

class ToggleSwitch(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(46, 26)
        self._offset = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._set_offset)
        self.toggled.connect(self._animate)

    def _set_offset(self, value) -> None:
        self._offset = float(value)
        self.update()

    def _animate(self, checked: bool) -> None:
        if not theme.motion():
            self._set_offset(1.0 if checked else 0.0)
            return
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def hitButton(self, pos) -> bool:
        return self.rect().contains(pos)

    def paintEvent(self, event) -> None:
        tokens = theme.tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        track = QRectF(1, 3, self.width() - 2, self.height() - 6)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tokens["accent"] if self.isChecked() else tokens["line"]))
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        radius = track.height() / 2 - 3
        x = track.left() + 3 + self._offset * (track.width() - radius * 2 - 6)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(x, track.center().y() - radius, radius * 2, radius * 2))


# ---------------------------------------------------------------- status

class StatusPill(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.text = "idle"
        self.state = "idle"
        self._phase = 0.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(30)
        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._tick)
        self._set_width()

    def set_state(self, text: str, state: str = "idle") -> None:
        self.text = text
        self.state = state
        self._set_width()
        if state == "running" and theme.motion():
            self._timer.start()
        else:
            self._timer.stop()
            self._phase = 0.0
        self.update()

    def _set_width(self) -> None:
        metrics = QFontMetrics(theme.font("body", 9.5, weight=600))
        self.setFixedWidth(metrics.horizontalAdvance(self.text) + 34)

    def _tick(self) -> None:
        self._phase = (self._phase + 0.14) % (math.pi * 2)
        self.update()

    def paintEvent(self, event) -> None:
        tokens = theme.tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0, 1, 0, -1)
        painter.setPen(QPen(QColor(tokens["line"]), 1))
        painter.setBrush(QColor(tokens["surface"]))
        painter.drawRoundedRect(rect, 15, 15)
        color = {"running": tokens["accent"], "failed": tokens["fail"], "ok": tokens["ok"]}.get(
            self.state, tokens["muted"]
        )
        dot = QColor(color)
        if self.state == "running":
            dot.setAlpha(165 + int(90 * (0.5 + 0.5 * math.sin(self._phase))))
        radius = 3.2 if self.state != "running" else 3.2 + 0.5 * math.sin(self._phase)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot)
        painter.drawEllipse(QRectF(rect.left() + 12, rect.center().y() - radius, radius * 2, radius * 2))
        painter.setFont(theme.font("body", 9.5, weight=600))
        painter.setPen(QColor(tokens["text"]))
        painter.drawText(rect.adjusted(24, 0, -10, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text)


# ---------------------------------------------------------------- spinner

class Spinner(QWidget):
    def __init__(self, size: int = 34, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def _tick(self) -> None:
        self._angle = (self._angle + 7) % 360
        self.update()

    def showEvent(self, event) -> None:
        if theme.motion():
            self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event) -> None:
        tokens = theme.tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        margin = 5
        arc = QRectF(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin)
        painter.setPen(QPen(QColor(tokens["line"]), 2.4))
        painter.drawArc(arc, 0, 360 * 16)
        painter.setPen(QPen(QColor(tokens["accent"]), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(arc, -self._angle * 16, -100 * 16)


# ---------------------------------------------------------------- progress

class SmoothBar(QWidget):
    def __init__(self, height: int = 6, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)
        self._value = 0.0
        self._target = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(280)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._set_value)
        self._indeterminate = False
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)

    def _set_value(self, value) -> None:
        self._value = float(value)
        self.update()

    def set_value(self, value: float, animate: bool = True) -> None:
        value = max(0.0, min(100.0, value))
        self._target = value
        if not animate or not theme.motion():
            self._anim.stop()
            self._set_value(value)
            return
        self._anim.stop()
        self._anim.setStartValue(self._value)
        self._anim.setEndValue(value)
        self._anim.start()

    def set_indeterminate(self, value: bool) -> None:
        self._indeterminate = value
        if value and theme.motion():
            self._timer.start()
        else:
            self._timer.stop()
            self.update()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.035) % 1.0
        self.update()

    def paintEvent(self, event) -> None:
        tokens = theme.tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        track = QRectF(self.rect())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tokens["line"]))
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        if self._indeterminate:
            width = track.width() * 0.28
            x = track.left() + (track.width() - width) * self._phase
            fill = QRectF(x, track.top(), width, track.height())
        else:
            fill = QRectF(track.left(), track.top(), track.width() * self._value / 100.0, track.height())
        if fill.width() > 0:
            gradient = QLinearGradient(fill.topLeft(), fill.topRight())
            gradient.setColorAt(0, QColor(tokens["accent"]))
            gradient.setColorAt(1, QColor(tokens["accent_soft"]))
            painter.setBrush(gradient)
            painter.drawRoundedRect(fill, fill.height() / 2, fill.height() / 2)


# ---------------------------------------------------------------- states

class Glyph(QWidget):
    def __init__(self, icon: str, size: int = 76, parent=None):
        super().__init__(parent)
        self.icon = icon
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:
        tokens = theme.tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setPen(QPen(QColor(tokens["line"]), 1))
        painter.setBrush(QColor(tokens["raised"]))
        painter.drawEllipse(rect)
        margin = self.width() * 0.28
        draw_icon(painter, self.icon, QRectF(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin), tokens["accent"], 1.5)


class EmptyState(QWidget):
    action = pyqtSignal()

    def __init__(self, icon: str, title: str, subtitle: str, action_text: str = "", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 44, 24, 44)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(Glyph(icon), alignment=Qt.AlignmentFlag.AlignCenter)
        title_label = QLabel(title)
        title_label.setProperty("role", "h2")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        subtitle_label = QLabel(subtitle)
        subtitle_label.setProperty("role", "muted")
        subtitle_label.setWordWrap(True)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setMaximumWidth(420)
        layout.addWidget(subtitle_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.button = None
        if action_text:
            self.button = QPushButton(action_text)
            self.button.setProperty("variant", "ghost")
            self.button.clicked.connect(self.action.emit)
            layout.addWidget(self.button, alignment=Qt.AlignmentFlag.AlignCenter)


# ---------------------------------------------------------------- toast

class Toast(QFrame):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setVisible(False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 18, 10)
        layout.setSpacing(9)
        self.dot = QLabel("â—")
        self.dot.setStyleSheet("font-size: 8pt;")
        self.label = QLabel()
        self.label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.dot)
        layout.addWidget(self.label)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._hide)
        self._effect = None
        self._anim = None

    def show_message(self, text: str, kind: str = "info", duration: int = 2600) -> None:
        tokens = theme.tokens()
        color = {"info": tokens["accent"], "ok": tokens["ok"], "fail": tokens["fail"]}.get(kind, tokens["accent"])
        self.dot.setStyleSheet(f"color: {color}; font-size: 8pt;")
        self.label.setText(text)
        self.setStyleSheet(
            f"QFrame {{ background: {tokens['surface']}; border: 1px solid {tokens['line']};"
            f" border-radius: 12px; }} QLabel {{ color: {tokens['text']}; }}"
        )
        self.adjustSize()
        self.setFixedHeight(46)
        self.adjustSize()
        parent = self.parentWidget()
        if parent is None:
            return
        x = parent.width() // 2 - self.width() // 2
        y = parent.height() - 76
        self.move(x, y + 14)
        self.show()
        self.raise_()
        if theme.motion():
            self._effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(self._effect)
            fade = QPropertyAnimation(self._effect, b"opacity", self)
            fade.setDuration(180)
            fade.setStartValue(0.0)
            fade.setEndValue(1.0)
            fade.start()
            self._anim = QPropertyAnimation(self, b"pos", self)
            self._anim.setDuration(220)
            self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._anim.setStartValue(QPoint(x, y + 14))
            self._anim.setEndValue(QPoint(x, y))
            self._anim.start()
        else:
            self.move(x, y)
        self._timer.start(duration)

    def _hide(self) -> None:
        if not theme.motion():
            self.hide()
            return
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        fade = QPropertyAnimation(effect, b"opacity", self)
        fade.setDuration(180)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.finished.connect(self.hide)
        fade.start()
        self._anim = fade

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent and self.isVisible():
            self.move(parent.width() // 2 - self.width() // 2, parent.height() - 76)


# ---------------------------------------------------------------- flow

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin: int = 0, spacing: int = 6):
        super().__init__(parent)
        self._items: list[QWidgetItem] = []
        self._spacing = spacing
        self.setContentsMargins(QMargins(margin, margin, margin, margin))

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _do_layout(self, rect: QRect, test: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x = effective.x()
        y = effective.y()
        line = 0
        for item in self._items:
            widget = item.widget()
            if widget is None or widget.isHidden():
                continue
            space = self._spacing
            next_x = x + item.sizeHint().width() + space
            if next_x - space > effective.right() and line > 0:
                x = effective.x()
                y = y + line + space
                next_x = x + item.sizeHint().width() + space
                line = 0
            if not test:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line = max(line, item.sizeHint().height())
        return y + line - rect.y() + margins.bottom()

