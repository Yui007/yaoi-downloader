"""The 76 px icon rail."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QWidget

from .. import theme
from .common import NavButton


class BrandMark(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 46)
        self.setToolTip("yaoi downloader")

    def paintEvent(self, event) -> None:
        tokens = theme.tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tokens["accent"]))
        painter.drawRoundedRect(rect, 13, 13)
        painter.setPen(QColor("#FFFFFF"))
        font = theme.font("display", 23, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "y")
        painter.setPen(QPen(QColor("#FFFFFF"), 1.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(rect.right() - 14, rect.top() + 9, 5, 5))


class Sidebar(QFrame):
    navigate = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(78)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 18, 12, 18)
        layout.setSpacing(10)
        layout.addWidget(BrandMark(), alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(18)
        self.buttons: list[NavButton] = []
        for index, (icon, tooltip) in enumerate(
            [
                ("search", "Search  ·  Ctrl+1"),
                ("library", "Library  ·  Ctrl+2"),
                ("queue", "Queue  ·  Ctrl+3"),
                ("settings", "Settings  ·  Ctrl+4"),
            ]
        ):
            button = NavButton(icon, tooltip)
            button.clicked.connect(lambda _=False, i=index: self.navigate.emit(i))
            layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignHCenter)
            self.buttons.append(button)
        layout.addStretch(1)
        self.dot = QWidget(self)
        self.dot.setFixedSize(8, 8)
        self.dot.setToolTip("idle")
        layout.addWidget(self.dot, alignment=Qt.AlignmentFlag.AlignHCenter)

    def set_active(self, index: int) -> None:
        for position, button in enumerate(self.buttons):
            button.set_active(position == index)

    def set_dot(self, state: str) -> None:
        color = {"running": theme.tokens()["accent"], "failed": theme.tokens()["fail"]}.get(
            state, theme.tokens()["line"]
        )
        self.dot.setStyleSheet(f"background: {color}; border-radius: 4px;")
        self.dot.setToolTip(state)
