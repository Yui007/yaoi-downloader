"""Ink & Paper tokens and the one QSS template."""

from __future__ import annotations

import re
from string import Template

from PyQt6.QtGui import QColor, QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication

DARK = {
    "name": "ink",
    "bg": "#0E1014",
    "surface": "#151920",
    "raised": "#1C222C",
    "line": "#2A3240",
    "text": "#E9E6DF",
    "muted": "#98A2B3",
    "accent": "#E4572E",
    "accent_hover": "#F06A42",
    "accent_soft": "#F2A07B",
    "accent_dim": "#8E3A22",
    "ok": "#6FCF97",
    "warn": "#E9B44C",
    "fail": "#E06C75",
    "glass": "rgba(21, 25, 32, 0.76)",
    "nav_active": "rgba(228, 87, 46, 0.14)",
    "shadow": "rgba(0, 0, 0, 0.38)",
    "overlay": "rgba(9, 11, 15, 0.64)",
    "input": "#1C222C",
    "scroll": "#2A3240",
    "aurora1": "rgba(228, 87, 46, 0.10)",
    "aurora2": "rgba(94, 133, 255, 0.055)",
    "placeholder": "#6E7888",
}

LIGHT = {
    "name": "paper",
    "bg": "#F6F3EC",
    "surface": "#FFFFFF",
    "raised": "#EFEAE0",
    "line": "#DCD5C7",
    "text": "#1B1D21",
    "muted": "#6B7280",
    "accent": "#C7431F",
    "accent_hover": "#B33A19",
    "accent_soft": "#D97757",
    "accent_dim": "#E8B9A6",
    "ok": "#2E8B57",
    "warn": "#A66A00",
    "fail": "#B3261E",
    "glass": "rgba(255, 255, 255, 0.80)",
    "nav_active": "rgba(199, 67, 31, 0.12)",
    "shadow": "rgba(62, 44, 24, 0.16)",
    "overlay": "rgba(40, 33, 24, 0.34)",
    "input": "#FFFFFF",
    "scroll": "#DCD5C7",
    "aurora1": "rgba(199, 67, 31, 0.08)",
    "aurora2": "rgba(74, 110, 220, 0.05)",
    "placeholder": "#9A9388",
}

_TEMPLATE = Template(
    """
    * { outline: none; }
    QMainWindow, QDialog { background: $bg; }
    QWidget { color: $text; font-family: "$body_font"; font-size: ${fs}pt; }
    QWidget#Shell, QWidget#Page, QWidget#Transparent { background: transparent; }
    QFrame#Sidebar { background: $glass; border-right: 1px solid $line; }
    QFrame#TopBar { background: transparent; border-bottom: 1px solid $line; }
    QFrame#ActionBar { background: $glass; border-top: 1px solid $line; }
    QLabel { background: transparent; }
    QLabel[role="display"] {
        font-family: "$display_font"; font-size: ${fs_display}pt; font-weight: bold; color: $text;
    }
    QLabel[role="h1"] {
        font-family: "$display_font"; font-size: ${fs_h1}pt; font-weight: bold; color: $text;
    }
    QLabel[role="h2"] { font-size: ${fs_h2}pt; font-weight: bold; color: $text; }
    QLabel[role="muted"] { color: $muted; }
    QLabel[role="small"] { color: $muted; font-size: ${fs_small}pt; }
    QLabel[role="eyebrow"] {
        color: $accent; font-size: ${fs_tiny}pt; font-weight: bold;
    }
    QLabel[role="mono"] { font-family: "$mono_font"; font-size: ${fs_small}pt; color: $muted; }
    QLabel[role="chip"] {
        background: $raised; color: $muted; border: 1px solid $line;
        border-radius: 10px; padding: 3px 9px; font-size: ${fs_tiny}pt;
    }
    QLabel[accent="true"] { color: $accent; }
    QLabel[ok="true"] { color: $ok; }
    QLabel[fail="true"] { color: $fail; }

    QFrame[card="true"] {
        background: $surface; border: 1px solid $line; border-radius: 18px;
    }
    QFrame[card="glass"] {
        background: $glass; border: 1px solid $line; border-radius: 18px;
    }
    QFrame[role="subtle"] {
        background: $raised; border: 1px solid $line; border-radius: 12px;
    }
    QFrame[role="line"] { background: $line; border: none; }

    QLineEdit, QSpinBox, QComboBox {
        background: $input; color: $text; border: 1px solid $line;
        border-radius: 10px; padding: 8px 12px; selection-background-color: $accent;
        selection-color: #FFFFFF;
    }
    QLineEdit:hover, QSpinBox:hover, QComboBox:hover { border-color: $accent_dim; }
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: $accent; }
    QLineEdit[invalid="true"] { border-color: $fail; }
    QLineEdit:disabled { color: $muted; background: $raised; }
    QLineEdit#Search {
        padding: 10px 14px 10px 38px; border-radius: 12px; background: $surface;
    }
    QLineEdit[hero="true"] {
        padding: 13px 16px 13px 44px; border-radius: 14px; background: $surface;
        font-size: ${fs_h2}pt;
    }
    QLineEdit[hero="true"]:focus { border-color: $accent; }
    QComboBox { padding-right: 28px; }
    QComboBox::drop-down { border: none; width: 24px; }
    QComboBox QAbstractItemView {
        background: $surface; border: 1px solid $line; border-radius: 10px;
        padding: 4px; selection-background-color: $nav_active; selection-color: $text;
        outline: none;
    }
    QComboBox QAbstractItemView::item { padding: 6px 10px; border-radius: 6px; }

    QPushButton {
        background: transparent; color: $text; border: 1px solid $line;
        border-radius: 10px; padding: 8px 14px; font-weight: 600;
    }
    QPushButton:hover { background: $raised; border-color: $accent_dim; }
    QPushButton:pressed { background: $nav_active; }
    QPushButton:disabled { color: $muted; border-color: $line; background: transparent; }
    QPushButton[variant="primary"] {
        background: $accent; color: #FFFFFF; border: 1px solid $accent;
        padding: 10px 20px; border-radius: 11px;
    }
    QPushButton[variant="primary"]:hover { background: $accent_hover; border-color: $accent_hover; }
    QPushButton[variant="primary"]:disabled { background: $raised; color: $muted; border-color: $line; }
    QPushButton[variant="ghost"] { border-color: transparent; color: $muted; padding: 7px 10px; }
    QPushButton[variant="ghost"]:hover { color: $text; background: $raised; }
    QPushButton[variant="danger"] { color: $fail; border-color: $line; }
    QPushButton[variant="danger"]:hover { background: rgba(224, 108, 117, 0.12); border-color: $fail; }
    QPushButton[variant="link"] {
        border: none; padding: 0; color: $accent; font-weight: 600; text-align: left;
    }
    QPushButton[variant="link"]:hover { color: $accent_hover; }

    QToolTip {
        background: $raised; color: $text; border: 1px solid $line;
        border-radius: 8px; padding: 6px 9px; font-size: ${fs_small}pt;
    }
    QMenu {
        background: $surface; border: 1px solid $line; border-radius: 10px; padding: 6px;
    }
    QMenu::item { padding: 7px 18px; border-radius: 6px; }
    QMenu::item:selected { background: $raised; }

    QScrollArea { border: none; background: transparent; }
    QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 2px; }
    QScrollBar::handle:vertical {
        background: $scroll; min-height: 32px; border-radius: 5px;
    }
    QScrollBar::handle:vertical:hover { background: $accent_dim; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
    QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px 4px; }
    QScrollBar::handle:horizontal { background: $scroll; min-width: 32px; border-radius: 5px; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

    QListView { background: transparent; border: none; outline: none; }
    QListView::item { background: transparent; }
    QListView::item:selected { background: transparent; }

    QCheckBox { color: $text; spacing: 9px; }
    QCheckBox::indicator {
        width: 18px; height: 18px; border-radius: 5px;
        border: 1px solid $line; background: $input;
    }
    QCheckBox::indicator:hover { border-color: $accent; }
    QCheckBox::indicator:checked { background: $accent; border-color: $accent; }

    QSlider::groove:horizontal { height: 4px; background: $line; border-radius: 2px; }
    QSlider::sub-page:horizontal { background: $accent; border-radius: 2px; }
    QSlider::handle:horizontal {
        background: $surface; border: 2px solid $accent; width: 14px;
        height: 14px; margin: -7px 0; border-radius: 9px;
    }
    QSlider::handle:horizontal:hover { background: $accent_soft; }

    QSpinBox::up-button, QSpinBox::down-button {
        border: none; width: 18px; background: transparent;
    }
    QToolButton { border: none; background: transparent; }
    """
)


_active = dict(DARK)
_scale = 1.0
_reduce_motion = False
_families = {"display": "Segoe UI", "body": "Segoe UI", "mono": "Consolas"}


def _pick(candidates: list[str], available: set[str], fallback: str) -> str:
    for name in candidates:
        if name in available:
            return name
    return fallback


def apply(
    app: QApplication,
    name: str = "ink",
    font_scale: int = 100,
    reduce_motion: bool = False,
) -> None:
    global _active, _scale, _reduce_motion, _families
    _active = dict(LIGHT if name == "paper" else DARK)
    _scale = max(0.9, min(1.2, font_scale / 100))
    _reduce_motion = reduce_motion
    available = set(QFontDatabase.families())
    _families = {
        "display": _pick(
            ["Fraunces", "Georgia", "Segoe UI Variable Display", "Segoe UI Variable", "Segoe UI"],
            available,
            "Segoe UI",
        ),
        "body": _pick(
            ["Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI", "Arial"],
            available,
            "Segoe UI",
        ),
        "mono": _pick(
            ["Cascadia Code", "JetBrains Mono", "Consolas", "Courier New"],
            available,
            "Consolas",
        ),
    }
    app.setStyle("Fusion")
    app.setFont(QFont(_families["body"], round(10 * _scale)))
    template = _TEMPLATE
    qss = template.substitute(
        **_active,
        display_font=_families["display"],
        body_font=_families["body"],
        mono_font=_families["mono"],
        fs=round(10 * _scale, 1),
        fs_display=round(30 * _scale, 1),
        fs_h1=round(22 * _scale, 1),
        fs_h2=round(14 * _scale, 1),
        fs_small=round(9 * _scale, 1),
        fs_tiny=round(8 * _scale, 1),
    )
    app.setStyleSheet(qss)


def tokens() -> dict:
    return _active


def qcolor(value: str, alpha: int | None = None) -> QColor:
    """QColor understands hex, not CSS rgba(); this bridges the token file."""
    match = re.match(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)", str(value))
    if match:
        red, green, blue = (int(float(match.group(i))) for i in range(1, 4))
        css_alpha = float(match.group(4)) if match.group(4) is not None else 1.0
        color = QColor(red, green, blue)
        color.setAlpha(round(css_alpha * 255))
    else:
        color = QColor(value)
    if not color.isValid():
        color = QColor("#888888")
    if alpha is not None:
        color.setAlpha(alpha)
    return color


def scale() -> float:
    return _scale


def motion() -> bool:
    return not _reduce_motion


def font(kind: str = "body", size: float = 10, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    family = _families.get(kind, _families["body"])
    result = QFont(family, max(6, round(size * _scale)))
    result.setWeight(weight)
    return result
