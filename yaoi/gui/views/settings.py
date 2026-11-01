"""Settings room: every control applies immediately and writes atomically."""

from __future__ import annotations

import time
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..bridge import Tasks
from ..widgets.common import SegmentedControl, ToggleSwitch
from ... import config
from ...sources import keys as keylib
from ...sources.yaoi import BASE
from ...app_context import source_from_settings


class Section(QFrame):
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setProperty("card", "true")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(22, 18, 22, 20)
        self.body.setSpacing(12)
        eyebrow = QLabel(title.upper())
        eyebrow.setProperty("role", "eyebrow")
        self.body.addWidget(eyebrow)
        if subtitle:
            hint = QLabel(subtitle)
            hint.setProperty("role", "small")
            hint.setWordWrap(True)
            self.body.addWidget(hint)


class SettingsView(QWidget):
    changed = pyqtSignal()
    status_message = pyqtSignal(str, str)

    def __init__(self, settings: dict, tasks: Tasks, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.settings = settings
        self.tasks = tasks
        self._building = True
        self._build()
        self._building = False

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("Transparent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(30, 24, 30, 30)
        layout.setSpacing(16)
        eyebrow = QLabel("SETTINGS")
        eyebrow.setProperty("role", "eyebrow")
        layout.addWidget(eyebrow)
        title = QLabel("Tune the room.")
        title.setProperty("role", "display")
        layout.addWidget(title)
        subtitle = QLabel(
            "Changes apply immediately and save themselves. Paths stay inside the project folder."
        )
        subtitle.setProperty("role", "muted")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        layout.addSpacing(4)

        layout.addWidget(self._appearance())
        layout.addWidget(self._downloads())
        layout.addWidget(self._folders())
        layout.addWidget(self._network())
        layout.addWidget(self._keys())
        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ---------------------------------------------------------- sections

    def _appearance(self) -> Section:
        section = Section("Appearance", "The room, the motion, and the size of the type.")
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)
        theme_label = QLabel("Theme")
        theme_label.setProperty("role", "muted")
        grid.addWidget(theme_label, 0, 0)
        self.theme = SegmentedControl(["Ink", "Paper"])
        self.theme.set_current(0 if self.settings["ui"]["theme"] == "ink" else 1)
        self.theme.changed.connect(self._theme_changed)
        grid.addWidget(self.theme, 0, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        motion_label = QLabel("Reduce motion")
        motion_label.setProperty("role", "muted")
        grid.addWidget(motion_label, 1, 0)
        motion_row = QHBoxLayout()
        self.motion = ToggleSwitch()
        self.motion.setChecked(bool(self.settings["ui"]["reduce_motion"]))
        self.motion.toggled.connect(self._motion_changed)
        motion_row.addWidget(self.motion)
        motion_hint = QLabel("disables fades and lifts")
        motion_hint.setProperty("role", "small")
        motion_row.addWidget(motion_hint)
        motion_row.addStretch(1)
        grid.addLayout(motion_row, 1, 1)
        scale_label = QLabel("Font scale")
        scale_label.setProperty("role", "muted")
        grid.addWidget(scale_label, 2, 0)
        scale_row = QHBoxLayout()
        self.scale = QSlider(Qt.Orientation.Horizontal)
        self.scale.setRange(90, 120)
        self.scale.setValue(int(self.settings["ui"].get("font_scale", 100)))
        self.scale.setFixedWidth(220)
        self.scale_value = QLabel(f"{self.scale.value()}%")
        self.scale_value.setProperty("role", "small")
        self.scale.valueChanged.connect(lambda value: self.scale_value.setText(f"{value}%"))
        self.scale.sliderReleased.connect(self._scale_changed)
        scale_row.addWidget(self.scale)
        scale_row.addWidget(self.scale_value)
        scale_row.addStretch(1)
        grid.addLayout(scale_row, 2, 1)
        section.body.addLayout(grid)
        return section

    def _downloads(self) -> Section:
        section = Section("Downloads", "Two pools, one brake. The defaults are kind to the site.")
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)
        format_label = QLabel("Format")
        format_label.setProperty("role", "muted")
        grid.addWidget(format_label, 0, 0)
        self.format = QComboBox()
        self.format.addItems(["cbz", "pdf", "images"])
        self.format.setCurrentText(str(self.settings["download"].get("format", "cbz")))
        self.format.currentTextChanged.connect(self._format_changed)
        grid.addWidget(self.format, 0, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        keep_label = QLabel("Keep images")
        keep_label.setProperty("role", "muted")
        grid.addWidget(keep_label, 1, 0)
        keep_row = QHBoxLayout()
        self.keep = ToggleSwitch()
        self.keep.setChecked(bool(self.settings["download"].get("keep_images", False)))
        self.keep.toggled.connect(self._keep_changed)
        keep_row.addWidget(self.keep)
        keep_hint = QLabel("after PDF or CBZ export")
        keep_hint.setProperty("role", "small")
        keep_row.addWidget(keep_hint)
        keep_row.addStretch(1)
        grid.addLayout(keep_row, 1, 1)
        self.chapters = self._slider_row(grid, 2, "Chapter workers", 1, 8, int(self.settings["download"]["chapters_workers"]))
        self.images = self._slider_row(grid, 3, "Image workers", 1, 10, int(self.settings["download"]["images_workers"]))
        self.concurrency = QLabel("")
        self.concurrency.setProperty("role", "small")
        grid.addWidget(self.concurrency, 4, 1)
        section.body.addLayout(grid)
        self._worker_changed(0)
        return section

    def _slider_row(self, grid: QGridLayout, row: int, label: str, low: int, high: int, value: int) -> QSlider:
        widget_label = QLabel(label)
        widget_label.setProperty("role", "muted")
        grid.addWidget(widget_label, row, 0)
        holder = QHBoxLayout()
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(low, high)
        slider.setValue(value)
        slider.setFixedWidth(220)
        value_label = QLabel(str(value))
        value_label.setProperty("role", "small")
        value_label.setFixedWidth(24)
        slider.valueChanged.connect(lambda v, l=value_label: l.setText(str(v)))
        slider.valueChanged.connect(self._worker_changed)
        holder.addWidget(slider)
        holder.addWidget(value_label)
        holder.addStretch(1)
        grid.addLayout(holder, row, 1)
        return slider

    def _folders(self) -> Section:
        section = Section("Folders", "Everything stays beside the project. Relative paths resolve there.")
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        self.path_fields: dict[str, QLineEdit] = {}
        for row, (name, label) in enumerate(
            [
                ("downloads", "Downloads"),
                ("library", "Library"),
                ("cache", "Cache"),
                ("logs", "Logs"),
            ]
        ):
            widget_label = QLabel(label)
            widget_label.setProperty("role", "muted")
            grid.addWidget(widget_label, row, 0)
            field = QLineEdit(str(self.settings["paths"].get(name, name)))
            field.setCursorPosition(0)
            field.editingFinished.connect(lambda key=name, f=field: self._path_changed(key, f))
            self.path_fields[name] = field
            grid.addWidget(field, row, 1)
            browse = QPushButton("Browse")
            browse.setProperty("variant", "ghost")
            browse.clicked.connect(lambda _=False, key=name, f=field: self._browse(key, f))
            grid.addWidget(browse, row, 2)
        grid.setColumnStretch(1, 1)
        section.body.addLayout(grid)
        root = QLabel(f"project root  Â·  {config.ROOT}")
        root.setProperty("role", "mono")
        section.body.addWidget(root)
        return section

    def _network(self) -> Section:
        section = Section("Network", "Timeouts, retries, and how long listings stay warm.")
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)
        self.timeout = self._spin_row(grid, 0, "Timeout (s)", 5, 120, int(self.settings["network"]["timeout"]))
        self.retries = self._spin_row(grid, 1, "Retries", 0, 10, int(self.settings["network"]["retries"]))
        ttl_hours = max(0, int(self.settings["network"]["cache_ttl"]) // 3600)
        self.ttl = self._spin_row(grid, 2, "Listing TTL (h)", 0, 168, ttl_hours)
        clear = QPushButton("Clear cache")
        clear.setProperty("variant", "ghost")
        clear.clicked.connect(self._clear_cache)
        grid.addWidget(clear, 3, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        section.body.addLayout(grid)
        return section

    def _spin_row(self, grid: QGridLayout, row: int, label: str, low: int, high: int, value: int) -> QSpinBox:
        widget_label = QLabel(label)
        widget_label.setProperty("role", "muted")
        grid.addWidget(widget_label, row, 0)
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setValue(value)
        spin.setFixedWidth(90)
        spin.valueChanged.connect(self._network_changed)
        grid.addWidget(spin, row, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        return spin

    def _keys(self) -> Section:
        section = Section("Reader keys", "Signed requests and the sealed page payload.")
        store = keylib.KeyStore(config.ROOT / "keys.json")
        info = store.load()
        self.key_info = info
        self.sign_label = QLabel(f"sign  {info.sign_fp}")
        self.sign_label.setProperty("role", "mono")
        self.seal_label = QLabel(f"seal  {info.seal_fp}")
        self.seal_label.setProperty("role", "mono")
        section.body.addWidget(self.sign_label)
        section.body.addWidget(self.seal_label)
        self.verified = QLabel(
            "not verified this install"
            if not info.verified_at
            else time.strftime("%Y-%m-%d %H:%M", time.localtime(info.verified_at))
        )
        self.verified.setProperty("role", "small")
        section.body.addWidget(self.verified)
        self.refresh_keys = QPushButton("Refresh keys")
        self.refresh_keys.setProperty("variant", "ghost")
        self.refresh_keys.clicked.connect(self._refresh_keys)
        section.body.addWidget(self.refresh_keys, alignment=Qt.AlignmentFlag.AlignLeft)
        return section

    # ---------------------------------------------------------- writers

    def _commit(self) -> None:
        if not self._building:
            self.changed.emit()

    def _theme_changed(self, index: int) -> None:
        self.settings["ui"]["theme"] = "ink" if index == 0 else "paper"
        self._commit()

    def _motion_changed(self, checked: bool) -> None:
        self.settings["ui"]["reduce_motion"] = bool(checked)
        self._commit()

    def _scale_changed(self) -> None:
        self.settings["ui"]["font_scale"] = int(self.scale.value())
        self._commit()

    def _format_changed(self, value: str) -> None:
        self.settings["download"]["format"] = value
        self._commit()

    def _keep_changed(self, checked: bool) -> None:
        self.settings["download"]["keep_images"] = bool(checked)
        self._commit()

    def _worker_changed(self, _value) -> None:
        if not hasattr(self, "chapters") or not hasattr(self, "images"):
            return
        self.settings["download"]["chapters_workers"] = int(self.chapters.value())
        self.settings["download"]["images_workers"] = int(self.images.value())
        product = self.chapters.value() * self.images.value()
        if product > 48:
            self.concurrency.setText(f"{product} possible requests in flight â€” that is a lot.")
            self.concurrency.setStyleSheet(f"color: {theme.tokens()['warn']};")
        else:
            self.concurrency.setText(f"{product} possible requests in flight")
            self.concurrency.setStyleSheet("")
        self._commit()

    def _path_changed(self, key: str, field: QLineEdit) -> None:
        value = field.text().strip() or key
        self.settings["paths"][key] = value
        self._commit()

    def _browse(self, key: str, field: QLineEdit) -> None:
        current = str(config.resolve_path(field.text() or key, config.ROOT))
        chosen = QFileDialog.getExistingDirectory(self, f"Choose {key} folder", current)
        if chosen:
            field.setText(chosen)
            self._path_changed(key, field)

    def _network_changed(self) -> None:
        if not hasattr(self, "timeout"):
            return
        self.settings["network"]["timeout"] = int(self.timeout.value())
        self.settings["network"]["retries"] = int(self.retries.value())
        self.settings["network"]["cache_ttl"] = int(self.ttl.value()) * 3600
        self._commit()

    def _clear_cache(self) -> None:
        cache = config.paths(self.settings)["cache"]
        removed = 0
        if cache.exists():
            for path in cache.iterdir():
                if path.is_file():
                    try:
                        path.unlink()
                        removed += 1
                    except OSError:
                        pass
        self.status_message.emit(f"Cleared {removed} cache entries.", "ok")

    def _refresh_keys(self) -> None:
        self.refresh_keys.setEnabled(False)
        self.refresh_keys.setText("Checkingâ€¦")
        self.status_message.emit("Recovering reader keysâ€¦", "info")

        def work():
            source = source_from_settings(self.settings)
            return keylib.refresh(source.client, source.store, BASE, save=True)

        self.tasks.run(work, self._keys_ready, self._keys_failed)

    def _keys_ready(self, info) -> None:
        self.key_info = info
        self.sign_label.setText(f"sign  {info.sign_fp}")
        self.seal_label.setText(f"seal  {info.seal_fp}")
        self.verified.setText(time.strftime("%Y-%m-%d %H:%M", time.localtime(info.verified_at)))
        self.refresh_keys.setEnabled(True)
        self.refresh_keys.setText("Refresh keys")
        self.status_message.emit("Reader keys verified and saved.", "ok")

    def _keys_failed(self, message: str) -> None:
        self.refresh_keys.setEnabled(True)
        self.refresh_keys.setText("Refresh keys")
        self.status_message.emit(f"Key refresh failed: {message}", "fail")

    def reload(self) -> None:
        """Public hook for a theme reapply; controls already own their values."""
        self.update()

