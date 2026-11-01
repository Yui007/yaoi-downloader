"""Main window, shell, page transitions, and keyboard shortcuts."""

from __future__ import annotations

import math
import random
import sys

from PyQt6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPixmap,
    QRadialGradient,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .bridge import CoverLoader, JobRunner, Tasks
from .views.detail import DetailView
from .views.library import LibraryView
from .views.search import SearchView
from .views.settings import SettingsView
from .widgets.common import Toast
from .widgets.sidebar import Sidebar
from .widgets.topbar import TopBar
from .. import config
from ..models import DownloadOptions, JobEvent, Series
from ..names import human_bytes


class Shell(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Shell")
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self._noise = self._make_noise()

    @staticmethod
    def _make_noise() -> QPixmap:
        generator = random.Random(17)
        image = QPixmap(96, 96)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        for y in range(96):
            for x in range(96):
                value = generator.randrange(0, 18)
                painter.setPen(QColor(255, 255, 255, value))
                painter.drawPoint(x, y)
        painter.end()
        return image

    def _tick(self) -> None:
        if not theme.motion():
            self._timer.stop()
            return
        self._phase = (self._phase + 0.006) % 6.283
        self.update()

    def showEvent(self, event) -> None:
        if theme.motion():
            self._timer.start()
        super().showEvent(event)

    def paintEvent(self, event) -> None:
        tokens = theme.tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()
        painter.fillRect(rect, theme.qcolor(tokens["bg"]))

        width, height = max(1, rect.width()), max(1, rect.height())
        phase = self._phase
        accent_center = QPointF(
            width * (0.78 + 0.04 * math.sin(phase)),
            height * (0.10 + 0.03 * math.cos(phase)),
        )
        accent = QRadialGradient(accent_center, width * 0.48)
        accent.setColorAt(0, theme.qcolor(tokens["aurora1"]))
        accent.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillRect(QRectF(rect), accent)

        blue_center = QPointF(
            width * (0.15 + 0.04 * math.cos(phase * 1.3)),
            height * (0.82 + 0.03 * math.sin(phase)),
        )
        blue = QRadialGradient(blue_center, width * 0.42)
        blue.setColorAt(0, theme.qcolor(tokens["aurora2"]))
        blue.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillRect(QRectF(rect), blue)

        painter.setOpacity(0.30)
        for y in range(0, height, 96):
            for x in range(0, width, 96):
                painter.drawPixmap(x, y, self._noise)
        painter.setOpacity(1.0)
        vignette = QRadialGradient(QPointF(rect.center()), max(width, height) * 0.8)
        vignette.setColorAt(0.55, QColor(0, 0, 0, 0))
        vignette.setColorAt(1, QColor(0, 0, 0, 35) if tokens["name"] == "ink" else QColor(80, 60, 40, 12))
        painter.fillRect(QRectF(rect), vignette)


class FadeStack(QStackedWidget):
    def fade_to(self, widget: QWidget) -> None:
        if self.currentWidget() is widget:
            return
        self.setCurrentWidget(widget)
        if not theme.motion():
            return
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", widget)
        animation.setDuration(190)
        animation.setStartValue(0.35)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda: widget.setGraphicsEffect(None))
        animation.start()
        self._animation = animation


class MainWindow(QMainWindow):
    def __init__(self, settings: dict):
        super().__init__()
        self.settings = settings
        self.tasks = Tasks(self, 6)
        self.covers = CoverLoader(settings, self)
        self._jobs: list[JobRunner] = []
        self._failures = 0
        self._status_text = "idle"
        self._status_state = "idle"
        self._nav_index = 0
        self._return_nav = 0
        self._applied_ui = (
            settings["ui"].get("theme", "ink"),
            int(settings["ui"].get("font_scale", 100)),
            bool(settings["ui"].get("reduce_motion", False)),
        )
        self.setWindowTitle("yaoi · downloader")
        self.setMinimumSize(1120, 720)
        self.resize(1360, 860)
        self._build()
        self._wire()
        self._shortcuts()
        self._refresh_status()
        self.sidebar.set_active(0)
        self.topbar.set_title("Search")
        self.archive_timer = QTimer(self)
        self.archive_timer.setSingleShot(True)
        self.archive_timer.timeout.connect(self._save_settings)
        self.failure_timer = QTimer(self)
        self.failure_timer.setSingleShot(True)
        self.failure_timer.timeout.connect(self._clear_failures)
        self.toast = Toast(self)
        self._faded_in = False

    def _build(self) -> None:
        self.shell = Shell(self)
        root = QHBoxLayout(self.shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.sidebar = Sidebar(self.shell)
        root.addWidget(self.sidebar)
        right = QWidget(self.shell)
        right.setObjectName("Transparent")
        column = QVBoxLayout(right)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        self.topbar = TopBar(right)
        column.addWidget(self.topbar)
        self.stack = FadeStack(right)
        column.addWidget(self.stack, 1)
        root.addWidget(right, 1)
        self.setCentralWidget(self.shell)

        self.search_view = SearchView(self.settings, self.tasks, self.covers)
        self.detail_view = DetailView(self.settings, self.tasks, self.covers)
        self.library_view = LibraryView(self.settings)
        self.settings_view = SettingsView(self.settings, self.tasks)
        self.stack.addWidget(self.search_view)
        self.stack.addWidget(self.library_view)
        self.stack.addWidget(self.settings_view)
        self.stack.addWidget(self.detail_view)
        self.stack.setCurrentWidget(self.search_view)

    def _wire(self) -> None:
        self.sidebar.navigate.connect(self.navigate)
        self.topbar.search_requested.connect(self._search)
        self.topbar.status_clicked.connect(lambda: self.navigate(2))
        self.topbar.search.setText("")
        self.search_view.open_series.connect(self.open_series)
        self.search_view.status_message.connect(self.show_toast)
        self.detail_view.back_requested.connect(self._back)
        self.detail_view.download_requested.connect(self.start_job)
        self.detail_view.status_message.connect(self.show_toast)
        self.library_view.search_requested.connect(lambda: self.navigate(0))
        self.settings_view.changed.connect(self._settings_changed)
        self.settings_view.status_message.connect(self.show_toast)

    def _shortcuts(self) -> None:
        for index in range(4):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{index + 1}"), self)
            shortcut.activated.connect(lambda i=index: self.navigate(i))
        QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(self.topbar.focus_search)
        QShortcut(QKeySequence("Ctrl+,"), self).activated.connect(lambda: self.navigate(3))
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._escape)

    def _escape(self) -> None:
        if self.stack.currentWidget() is self.detail_view:
            self._back()
        elif self.topbar.search.text():
            self.topbar.search.clear()
        elif self.stack.currentWidget() is self.search_view:
            self.search_view.field.clear()

    def navigate(self, index: int) -> None:
        self._nav_index = index
        self.sidebar.set_active(index)
        if index == 0:
            self.topbar.set_title("Search")
            self.stack.fade_to(self.search_view)
            self.search_view.focus_search()
        elif index in {1, 2}:
            self.topbar.set_title("Library" if index == 1 else "Queue")
            self.library_view.set_tab(1 if index == 1 else 0)
            self.stack.fade_to(self.library_view)
        else:
            self.topbar.set_title("Settings")
            self.stack.fade_to(self.settings_view)

    def _search(self, text: str) -> None:
        if "yaoi.me/series/" in text or text.startswith(("http://", "https://")):
            self.open_series(text)
            return
        self.navigate(0)
        self.search_view.search(text)

    def open_series(self, url: str) -> None:
        self._return_nav = self._nav_index if self._nav_index in {0, 1, 2} else 0
        self.sidebar.set_active(-1)
        self.topbar.set_title("Series")
        self.stack.fade_to(self.detail_view)
        self.detail_view.open_url(url)

    def _back(self) -> None:
        self.navigate(self._return_nav if self._return_nav in {0, 1, 2} else 0)

    def start_job(self, series: Series, groups, options: DownloadOptions) -> None:
        runner = JobRunner(self.settings, series, groups, options, self)
        self._jobs.append(runner)
        self._failures = 0
        self.failure_timer.stop()
        runner.event.connect(lambda event, r=runner: self._job_event(r, event))
        runner.finished.connect(
            lambda summary, elapsed, r=runner: self._job_finished(r, summary, elapsed)
        )
        self.library_view.add_job(runner, series, groups)
        self.navigate(2)
        self.topbar.set_status(f"{len(self._jobs)} running", "running")
        self.sidebar.set_dot("running")
        self.show_toast(
            f"Queued {len(groups)} chapter{'s' if len(groups) != 1 else ''} · {options.format.upper()}",
            "info",
        )
        runner.start()

    def _job_event(self, runner: JobRunner, event: JobEvent) -> None:
        if event.kind == "chapter":
            if self.detail_view.series is not None and self.detail_view.series.url == runner.series.url:
                self.detail_view.update_event(event)
            if event.state == "failed":
                self._failures += 1
                self._refresh_status()
                if self._failures <= 2:
                    self.show_toast(event.message, "fail")
        elif event.kind == "summary":
            self.detail_view.update_event(event)
            self._refresh_status()

    def _job_finished(self, runner: JobRunner, summary, elapsed: float) -> None:
        if runner in self._jobs:
            self._jobs.remove(runner)
        self._refresh_status()
        if summary.failed:
            self.show_toast(
                f"{summary.failed} chapter{'s' if summary.failed != 1 else ''} failed — partial pages kept.",
                "fail",
            )
            self.failure_timer.start(10000)
        elif summary.cancelled:
            self.show_toast("Cancelled. Partial pages stay on disk.", "info")
        elif summary.done:
            self.show_toast(
                f"Finished {summary.done} chapter{'s' if summary.done != 1 else ''} · {human_bytes(summary.bytes)}",
                "ok",
            )
        self.library_view.refresh_done()

    def _refresh_status(self) -> None:
        running = len(self._jobs)
        if running:
            self._status_text = f"{running} running"
            self._status_state = "running"
        elif self._failures:
            self._status_text = f"{self._failures} failed"
            self._status_state = "failed"
        else:
            self._status_text = "idle"
            self._status_state = "idle"
        self.topbar.set_status(self._status_text, self._status_state)
        self.sidebar.set_dot(self._status_state)

    def _clear_failures(self) -> None:
        self._failures = 0
        self._refresh_status()

    def _settings_changed(self) -> None:
        ui = (
            self.settings["ui"].get("theme", "ink"),
            int(self.settings["ui"].get("font_scale", 100)),
            bool(self.settings["ui"].get("reduce_motion", False)),
        )
        if ui != self._applied_ui:
            self._applied_ui = ui
            theme.apply(
                QApplication.instance(),
                ui[0],
                ui[1],
                ui[2],
            )
            self.shell.update()
            if theme.motion():
                self.shell._timer.start()
            for widget in self.findChildren(QWidget):
                widget.update()
            self.sidebar.set_active(self._nav_index if self.stack.currentWidget() is not self.detail_view else -1)
            self._refresh_status()
        self.archive_timer.start(450)

    def _save_settings(self) -> None:
        try:
            config.save_settings(self.settings)
        except OSError as exc:
            self.show_toast(f"Could not save settings: {exc}", "fail")

    def show_toast(self, text: str, kind: str = "info") -> None:
        self.toast.show_message(text, kind)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "toast"):
            self.toast.reposition()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._faded_in and theme.motion():
            self._faded_in = True
            self.setWindowOpacity(0.0)
            animation = QPropertyAnimation(self, b"windowOpacity", self)
            animation.setDuration(320)
            animation.setStartValue(0.0)
            animation.setEndValue(1.0)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.start()
            self._opacity_animation = animation

    def closeEvent(self, event) -> None:
        self._save_settings()
        for runner in list(self._jobs):
            runner.cancel()
        super().closeEvent(event)


def app_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(theme.tokens()["accent"]))
    painter.drawRoundedRect(QRectF(4, 4, 56, 56), 16, 16)
    painter.setPen(QColor("#FFFFFF"))
    painter.setFont(theme.font("display", 34, QFont.Weight.Bold))
    painter.drawText(QRectF(4, 4, 56, 56), Qt.AlignmentFlag.AlignCenter, "y")
    painter.end()
    return QIcon(pixmap)


def main() -> int:
    settings = config.load_settings()
    app = QApplication(sys.argv)
    app.setApplicationName("yaoi")
    app.setOrganizationName("yaoi")
    theme.apply(
        app,
        settings["ui"].get("theme", "ink"),
        int(settings["ui"].get("font_scale", 100)),
        bool(settings["ui"].get("reduce_motion", False)),
    )
    app.setWindowIcon(app_icon())
    window = MainWindow(settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
