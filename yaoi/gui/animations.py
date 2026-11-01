"""Small, reusable animations. Every one respects reduce-motion."""

from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QWidget

from . import theme


def fade_in(widget: QWidget, duration: int = 240, delay: int = 0) -> None:
    if not theme.motion():
        return
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.finished.connect(lambda: widget.setGraphicsEffect(None))
    widget._fade_animation = animation  # type: ignore[attr-defined]
    widget._fade_effect = effect  # type: ignore[attr-defined]

    def start() -> None:
        widget.show()
        animation.start()

    QTimer.singleShot(delay, start)


def fade_out(widget: QWidget, duration: int = 220, on_done=None) -> None:
    if not theme.motion():
        if on_done is not None:
            on_done()
        else:
            widget.hide()
        return
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration)
    animation.setStartValue(1.0)
    animation.setEndValue(0.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    if on_done is not None:
        animation.finished.connect(on_done)
    animation.start()
    widget._fade_out_animation = animation  # type: ignore[attr-defined]


def shadow(widget: QWidget, blur: int = 26, y: int = 8, alpha: int = 70) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y)
    color = QColor(0, 0, 0, alpha)
    effect.setColor(color)
    widget.setGraphicsEffect(effect)


def animate_height(widget: QWidget, start: int, end: int, duration: int = 240) -> QPropertyAnimation | None:
    if not theme.motion():
        widget.setMaximumHeight(end)
        return None
    animation = QPropertyAnimation(widget, b"maximumHeight", widget)
    animation.setDuration(duration)
    animation.setStartValue(start)
    animation.setEndValue(end)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.start()
    widget._height_animation = animation  # type: ignore[attr-defined]
    return animation


def slide_to(widget: QWidget, x: int, y: int, duration: int = 220) -> None:
    if not theme.motion():
        widget.move(x, y)
        return
    animation = QPropertyAnimation(widget, b"pos", widget)
    animation.setDuration(duration)
    animation.setStartValue(widget.pos())
    animation.setEndValue(widget.pos().__class__(x, y))
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.start()
    widget._pos_animation = animation  # type: ignore[attr-defined]
