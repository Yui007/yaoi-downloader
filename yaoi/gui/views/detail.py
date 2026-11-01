"""Series room: hero, filters, chapter selection, and the sticky action bar."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..bridge import CoverLoader, Tasks
from ..models import ChapterModel
from ..widgets.chapters import ChapterList
from ..widgets.common import IconButton, SegmentedControl, Spinner, ToggleSwitch
from ..widgets.hero import CollapsibleText, DetailHero
from ...app_context import options_from_settings, source_from_settings
from ...errors import SelectionError
from ...filters import available_languages, available_sources, filter_chapters
from ...models import ChapterGroup, JobEvent, Series
from ...selection import parse_selection


class DetailView(QWidget):
    back_requested = pyqtSignal()
    download_requested = pyqtSignal(object, object, object)
    status_message = pyqtSignal(str, str)

    def __init__(self, settings: dict, tasks: Tasks, covers: CoverLoader, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.settings = settings
        self.tasks = tasks
        self.covers = covers
        self.series: Series | None = None
        self.raw_groups: list[ChapterGroup] = []
        self.visible_groups: list[ChapterGroup] = []
        self.model = ChapterModel(self)
        self.model.dataChanged.connect(self._model_changed)
        self._format = str(settings["download"].get("format", "cbz")).lower()
        self._current_url = ""
        self._syncing = False
        self._request_id = 0
        self._build()
        self.covers.ready.connect(self._cover_ready)
        self._selection_timer = QTimer(self)
        self._selection_timer.setSingleShot(True)
        self._selection_timer.setInterval(320)
        self._selection_timer.timeout.connect(self._parse_selection)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content = QWidget()
        self.content.setObjectName("Transparent")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.hero = DetailHero()
        self.hero.back_requested.connect(self.back_requested.emit)
        self.content_layout.addWidget(self.hero)

        body = QWidget()
        body.setObjectName("Transparent")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(30, 22, 30, 30)
        body_layout.setSpacing(16)

        self.filters = QFrame()
        self.filters.setProperty("card", "true")
        filters_layout = QVBoxLayout(self.filters)
        filters_layout.setContentsMargins(20, 18, 20, 16)
        filters_layout.setSpacing(10)
        top = QHBoxLayout()
        eyebrow = QLabel("CHAPTERS")
        eyebrow.setProperty("role", "eyebrow")
        top.addWidget(eyebrow)
        self.stats = QLabel("")
        self.stats.setProperty("role", "small")
        top.addWidget(self.stats)
        top.addStretch(1)
        self.select_all = QPushButton("Select all")
        self.select_all.setProperty("variant", "ghost")
        self.select_all.clicked.connect(self._select_all)
        top.addWidget(self.select_all)
        self.clear = QPushButton("Clear")
        self.clear.setProperty("variant", "ghost")
        self.clear.clicked.connect(self._clear)
        top.addWidget(self.clear)
        filters_layout.addLayout(top)

        row = QHBoxLayout()
        row.setSpacing(8)
        scan_label = QLabel("Scanlator")
        scan_label.setProperty("role", "small")
        row.addWidget(scan_label)
        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(150)
        self.source_combo.currentTextChanged.connect(self._apply_filters)
        row.addWidget(self.source_combo)
        lang_label = QLabel("Language")
        lang_label.setProperty("role", "small")
        row.addWidget(lang_label)
        self.language_combo = QComboBox()
        self.language_combo.setMinimumWidth(100)
        self.language_combo.currentTextChanged.connect(self._apply_filters)
        row.addWidget(self.language_combo)
        row.addSpacing(8)
        self.selection = QLineEdit()
        self.selection.setPlaceholderText("1,5,10-20 or all")
        self.selection.returnPressed.connect(self._parse_selection)
        self.selection.textEdited.connect(lambda _text: self._selection_timer.start())
        row.addWidget(self.selection, 1)
        filters_layout.addLayout(row)
        self.helper = QLabel("1–0 visible")
        self.helper.setProperty("role", "small")
        filters_layout.addWidget(self.helper)

        self.chapter_list = ChapterList()
        self.chapter_list.setModel(self.model)
        self.chapter_list.selection_changed.connect(self._selection_changed)
        filters_layout.addWidget(self.chapter_list)
        body_layout.addWidget(self.filters)

        self.synopsis = QFrame()
        self.synopsis.setProperty("card", "true")
        syn_layout = QVBoxLayout(self.synopsis)
        syn_layout.setContentsMargins(20, 16, 20, 16)
        syn_layout.setSpacing(6)
        syn_title = QLabel("SYNOPSIS")
        syn_title.setProperty("role", "eyebrow")
        syn_layout.addWidget(syn_title)
        self.synopsis_text = CollapsibleText("")
        syn_layout.addWidget(self.synopsis_text)
        self.tags = QLabel("")
        self.tags.setProperty("role", "small")
        self.tags.setWordWrap(True)
        syn_layout.addWidget(self.tags)
        body_layout.addWidget(self.synopsis)
        body_layout.addStretch(1)
        self.content_layout.addWidget(body)
        self.scroll.setWidget(self.content)
        self.stack.addWidget(self.scroll)

        self.loading = QWidget()
        loading_layout = QVBoxLayout(self.loading)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.setSpacing(12)
        loading_layout.addWidget(Spinner(42), alignment=Qt.AlignmentFlag.AlignCenter)
        loading_label = QLabel("Opening the series…")
        loading_label.setProperty("role", "muted")
        loading_layout.addWidget(loading_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(self.loading)

        self.error_holder = QWidget()
        self.error_layout = QVBoxLayout(self.error_holder)
        self.error_layout.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(self.error_holder)
        self.stack.setCurrentWidget(self.loading)

        self.action_bar = QFrame()
        self.action_bar.setObjectName("ActionBar")
        self.action_bar.setFixedHeight(76)
        action = QHBoxLayout(self.action_bar)
        action.setContentsMargins(30, 0, 30, 0)
        action.setSpacing(14)
        format_label = QLabel("FORMAT")
        format_label.setProperty("role", "eyebrow")
        action.addWidget(format_label)
        self.format_control = SegmentedControl(["Images", "PDF", "CBZ"])
        self.format_control.set_current({"images": 0, "pdf": 1, "cbz": 2}.get(self._format, 2))
        self.format_control.changed.connect(self._format_changed)
        action.addWidget(self.format_control)
        action.addSpacing(8)
        self.keep = ToggleSwitch()
        self.keep.setChecked(bool(self.settings["download"].get("keep_images", False)))
        action.addWidget(self.keep)
        keep_label = QLabel("keep images")
        keep_label.setProperty("role", "small")
        action.addWidget(keep_label)
        action.addStretch(1)
        self.workers = QLabel("")
        self.workers.setProperty("role", "small")
        action.addWidget(self.workers)
        self.download_button = QPushButton("Download")
        self.download_button.setProperty("variant", "primary")
        self.download_button.setMinimumHeight(44)
        self.download_button.setMinimumWidth(150)
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self._download)
        action.addWidget(self.download_button)
        outer.addWidget(self.action_bar)

    # ---------------------------------------------------------- opening

    def open_url(self, url: str) -> None:
        self._current_url = url.strip()
        self._request_id += 1
        request_id = self._request_id
        self.stack.setCurrentWidget(self.loading)
        self.action_bar.setEnabled(False)
        self.hero.setVisible(False)
        self.tasks.run(
            lambda: self._fetch(self._current_url),
            lambda payload, rid=request_id: self._opened(payload, rid),
            lambda message, rid=request_id: self._open_failed(message, rid),
        )

    def _fetch(self, url: str):
        source = source_from_settings(self.settings)
        series = source.series(url)
        groups = source.chapters(series)
        return series, groups

    def _opened(self, payload, request_id: int = 0) -> None:
        if request_id != self._request_id:
            return
        series, groups = payload
        self.series = series
        self.raw_groups = groups
        self.hero.setVisible(True)
        self.hero.set_series(series, groups)
        self.synopsis_text.setText(series.description or "No synopsis yet.")
        tags = "   ".join(series.tags[:16])
        if len(series.tags) > 16:
            tags += f"   +{len(series.tags) - 16}"
        self.tags.setText(tags)
        self.tags.setVisible(bool(tags))
        cached = self.covers.cached(series.cover)
        if cached is not None:
            self.hero.set_backdrop(cached)
        else:
            self.covers.request(series.cover)
        self._fill_filters(groups)
        self.action_bar.setEnabled(True)
        if self._format not in {"images", "pdf", "cbz"}:
            self._format = "cbz"
        self.format_control.set_current({"images": 0, "pdf": 1, "cbz": 2}[self._format])
        self.stack.setCurrentWidget(self.scroll)
        self.scroll.verticalScrollBar().setValue(0)

    def _open_failed(self, message: str, request_id: int = 0) -> None:
        if request_id != self._request_id:
            return
        while self.error_layout.count():
            item = self.error_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        holder = QFrame()
        holder.setProperty("card", "true")
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(10)
        back = IconButton("back", "Back", 36)
        back.clicked.connect(self.back_requested.emit)
        layout.addWidget(back, alignment=Qt.AlignmentFlag.AlignLeft)
        title = QLabel("The page would not open")
        title.setProperty("role", "h2")
        layout.addWidget(title)
        detail = QLabel(message)
        detail.setProperty("role", "muted")
        detail.setWordWrap(True)
        layout.addWidget(detail)
        retry = QPushButton("Try again")
        retry.setProperty("variant", "ghost")
        retry.clicked.connect(lambda: self.open_url(self._current_url))
        layout.addWidget(retry, alignment=Qt.AlignmentFlag.AlignLeft)
        self.error_layout.addWidget(holder)
        self.stack.setCurrentWidget(self.error_holder)
        self.action_bar.setEnabled(False)

    def _cover_ready(self, url: str, pixmap) -> None:
        if self.series is not None and url == self.series.cover:
            self.hero.set_backdrop(pixmap)

    # ---------------------------------------------------------- filters

    def _fill_filters(self, groups: list[ChapterGroup]) -> None:
        self.source_combo.blockSignals(True)
        self.language_combo.blockSignals(True)
        self.source_combo.clear()
        self.language_combo.clear()
        self.source_combo.addItem("Any")
        self.language_combo.addItem("Any")
        self.source_combo.addItems(available_sources(groups))
        self.language_combo.addItems(available_languages(groups))
        self.source_combo.blockSignals(False)
        self.language_combo.blockSignals(False)
        self.visible_groups = list(groups)
        self.model.set_groups(self.visible_groups)
        self.chapter_list.fit_to_rows()
        self.selection.blockSignals(True)
        self.selection.clear()
        self.selection.blockSignals(False)
        self._set_invalid(False)
        self._update_stats()

    def _apply_filters(self) -> None:
        source = self.source_combo.currentText()
        language = self.language_combo.currentText()
        self.visible_groups = filter_chapters(
            self.raw_groups,
            None if source in {"", "Any"} else source,
            None if language in {"", "Any"} else language,
        )
        self.model.set_groups(self.visible_groups)
        self.chapter_list.fit_to_rows()
        self.selection.clear()
        self._set_invalid(False)
        self._update_stats()

    def _select_all(self) -> None:
        self.model.select_all()
        self._sync_selection_text()
        self._update_stats()

    def _clear(self) -> None:
        self.model.clear()
        self.selection.clear()
        self._set_invalid(False)
        self._update_stats()

    def _selection_changed(self) -> None:
        self._sync_selection_text()
        self._update_stats()

    def _sync_selection_text(self) -> None:
        self._syncing = True
        self.selection.setText(self.model.selection_text())
        self._syncing = False
        self._set_invalid(False)

    def _parse_selection(self) -> None:
        if self._syncing:
            return
        text = self.selection.text().strip()
        if not text:
            self.model.clear()
            self._set_invalid(False)
            self._update_stats()
            return
        try:
            indexes = parse_selection(
                text,
                len(self.visible_groups),
                [group.label for group in self.visible_groups],
            )
            self.model.set_checked(set(indexes))
        except SelectionError as exc:
            self._set_invalid(True, exc.message)
        else:
            self._set_invalid(False)
        self._update_stats()

    def _set_invalid(self, invalid: bool, message: str = "") -> None:
        self.selection.setProperty("invalid", "true" if invalid else "false")
        self.selection.style().unpolish(self.selection)
        self.selection.style().polish(self.selection)
        if invalid:
            self.helper.setText(message or "Check that selection.")
            self.helper.setStyleSheet(f"color: {theme.tokens()['fail']};")
        else:
            self.helper.setStyleSheet("")
            self.helper.setText(f"{len(self.visible_groups)} visible  ·  type a range or tick rows")

    def _update_stats(self) -> None:
        selected = len(self.model.selected_groups())
        self.stats.setText(
            f"{len(self.visible_groups)} visible   ·   {selected} selected"
        )
        self.download_button.setEnabled(selected > 0 and self.series is not None)
        self.download_button.setText(f"Download {selected}" if selected else "Download")
        chapters_workers = int(self.settings["download"]["chapters_workers"])
        images_workers = int(self.settings["download"]["images_workers"])
        self.workers.setText(f"{chapters_workers} × {images_workers} workers")

    def _model_changed(self, *args) -> None:
        self.chapter_list.viewport().update()

    # ---------------------------------------------------------- download

    def _format_changed(self, index: int) -> None:
        self._format = {0: "images", 1: "pdf", 2: "cbz"}.get(index, "cbz")

    def _download(self) -> None:
        if self.series is None:
            return
        groups = self.model.selected_groups()
        if not groups:
            self.status_message.emit("Pick at least one chapter.", "info")
            return
        options = options_from_settings(
            self.settings,
            format=self._format,
            keep_images=self.keep.isChecked(),
        )
        self.download_requested.emit(self.series, groups, options)

    def update_event(self, event: JobEvent) -> None:
        if event.kind == "chapter":
            self.model.set_progress(
                event.chapter_index,
                event.state,
                event.done,
                event.total,
                event.speed,
                event.message,
                event.path,
            )
            self.chapter_list.viewport().update()
        elif event.kind == "summary":
            self.chapter_list.viewport().update()
