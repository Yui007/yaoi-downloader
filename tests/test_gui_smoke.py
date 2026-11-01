from __future__ import annotations

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication

from yaoi import config
from yaoi.gui import theme
from yaoi.gui.app import MainWindow
from yaoi.gui.widgets.common import draw_icon


def test_theme_qcolor_parses_rgba():
    color = theme.qcolor("rgba(10, 20, 30, 0.5)")
    assert color.isValid()
    assert color.red() == 10
    assert 120 <= color.alpha() <= 135


def test_icons_paint_without_error(qapp):
    pixmap = QPixmap(48, 48)
    pixmap.fill()
    from PyQt6.QtGui import QPainter

    painter = QPainter(pixmap)
    for name in ["folder", "moon", "search", "library", "queue", "settings", "pause", "x", "book"]:
        draw_icon(painter, name, QRectF(pixmap.rect()), "#E4572E")
    painter.end()
    assert not pixmap.isNull()


def test_main_window_builds_and_navigates(qtbot):
    app = QApplication.instance()
    settings = config.load_settings()
    theme.apply(app, "ink", 100, False)
    window = MainWindow(settings)
    qtbot.addWidget(window)
    window.navigate(1)
    assert window.stack.currentWidget() is window.library_view
    window.navigate(3)
    assert window.stack.currentWidget() is window.settings_view
    window.navigate(0)
    assert window.stack.currentWidget() is window.search_view
    assert window.topbar.status.text == "idle"
