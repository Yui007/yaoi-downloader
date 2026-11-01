"""A live job card for the queue."""

from __future__ import annotations

import time
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .. import theme
from ...library import open_path
from ...models import JobEvent
from ...names import human_bytes
from .common import IconButton, SmoothBar


class JobCard(QFrame):
    def __init__(self, runner, series, groups, parent=None):
        super().__init__(parent)
        self.setProperty("card", "true")
        self.runner = runner
        self.series = series
        self.groups = groups
        self.total = len(groups)
        self.finished_count = 0
        self._chapter_bytes: dict[int, int] = {}
        self._states: dict[int, tuple[int, int]] = {}
        self._last_chapter = ""
        self._started = time.monotonic()
        self._target_path: Path | None = None
        self._build()
        runner.event.connect(self.handle)
        runner.finished.connect(self.finish)
        runner.started.connect(lambda _: self._started_clock())

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 18, 16)
        layout.setSpacing(9)
        header = QHBoxLayout()
        header.setSpacing(8)
        self.title = QLabel(self.series.title)
        self.title.setProperty("role", "h2")
        self.title.setWordWrap(True)
        header.addWidget(self.title, 1)
        self.state = QLabel("queued")
        self.state.setProperty("role", "eyebrow")
        header.addWidget(self.state)
        self.pause_button = IconButton("pause", "Pause / resume", 32)
        self.pause_button.clicked.connect(self._pause)
        header.addWidget(self.pause_button)
        self.reveal_button = IconButton("folder", "Reveal folder", 32)
        self.reveal_button.setEnabled(False)
        self.reveal_button.clicked.connect(self._reveal)
        header.addWidget(self.reveal_button)
        self.cancel_button = IconButton("x", "Cancel", 32)
        self.cancel_button.clicked.connect(self._cancel)
        header.addWidget(self.cancel_button)
        layout.addLayout(header)

        self.chapter = QLabel("waiting for a worker")
        self.chapter.setProperty("role", "muted")
        layout.addWidget(self.chapter)
        self.bar = SmoothBar(6)
        layout.addWidget(self.bar)
        footer = QHBoxLayout()
        self.meta = QLabel("0 / %d chapters  ·  0 B" % self.total)
        self.meta.setProperty("role", "small")
        footer.addWidget(self.meta, 1)
        self.speed = QLabel("")
        self.speed.setProperty("role", "small")
        footer.addWidget(self.speed)
        layout.addLayout(footer)

    def _started_clock(self) -> None:
        self._started = time.monotonic()
        self.bar.set_indeterminate(True)

    def _pause(self) -> None:
        self.runner.toggle_pause()
        paused = self.runner.job.paused.is_set()
        self.pause_button.set_name("play" if paused else "pause")
        self.state.setText("paused" if paused else "running")
        self.bar.set_indeterminate(not paused and self.finished_count < self.total)

    def _cancel(self) -> None:
        self.runner.cancel()
        self.state.setText("cancelling")
        self.pause_button.setEnabled(False)
        self.cancel_button.setEnabled(False)

    def _reveal(self) -> None:
        target = self._target_path
        if target is not None:
            open_path(target if target.is_dir() else target.parent)

    def handle(self, event: JobEvent) -> None:
        if event.kind == "job":
            self.state.setText(event.state)
            if event.state == "paused":
                self.state.setText("paused")
            elif event.state == "downloading":
                self.state.setText("running")
            if event.state in {"downloading", "paused"}:
                self.bar.set_indeterminate(event.state == "downloading")
            return
        if event.kind != "chapter":
            return
        if event.bytes:
            self._chapter_bytes[event.chapter_index] = event.bytes
        total_bytes = sum(self._chapter_bytes.values())
        self._last_chapter = event.label
        if event.state in {"fetching", "downloading", "exporting"}:
            self._states[event.chapter_index] = (event.done, event.total)
            label = {
                "fetching": "reading hashes",
                "downloading": f"{event.done} / {event.total} pages",
                "exporting": "sealing the book",
            }.get(event.state, event.state)
            self.chapter.setText(f"ch {event.chapter_index}  ·  {event.label}  ·  {label}")
            if event.speed:
                self.speed.setText(f"{human_bytes(event.speed)}/s")
            self.state.setText(event.state)
            self.bar.set_indeterminate(event.state != "downloading")
            if event.state == "downloading" and event.total:
                current = (event.done / event.total) / max(1, self.total)
                target = (self.finished_count / max(1, self.total) + current) * 100
                self.bar.set_value(target)
            self.meta.setText(
                f"{self.finished_count} / {self.total} chapters  ·  {human_bytes(total_bytes)}"
            )
        elif event.state in {"done", "failed", "cancelled"}:
            self.finished_count += 1
            if event.state == "done":
                self._target_path = Path(event.path)
                self.reveal_button.setEnabled(True)
            self.chapter.setText(f"ch {event.chapter_index}  ·  {event.label}  ·  {event.state}")
            self.state.setText(event.state)
            self.bar.set_indeterminate(False)
            self.bar.set_value(self.finished_count / max(1, self.total) * 100)
            self.meta.setText(
                f"{self.finished_count} / {self.total} chapters  ·  {human_bytes(total_bytes)}"
            )
            if event.state == "failed":
                self.chapter.setToolTip(event.message)
                self.state.setStyleSheet(f"color: {theme.tokens()['fail']};")

    def finish(self, summary, elapsed: float) -> None:
        if summary.cancelled and not summary.failed:
            self.state.setText("cancelled")
            self.bar.set_value(max(self.bar._value, 1))
            self.state.setStyleSheet(f"color: {theme.tokens()['warn']};")
        elif summary.failed:
            self.state.setText("finished with errors")
            self.bar.set_value(100)
            self.state.setStyleSheet(f"color: {theme.tokens()['fail']};")
        else:
            self.state.setText("finished")
            self.bar.set_value(100)
        self.bar.set_indeterminate(False)
        self.pause_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.meta.setText(
            f"{summary.done} / {self.total} chapters  ·  "
            f"{human_bytes(max(sum(self._chapter_bytes.values()), summary.bytes))}  ·  {elapsed:.1f}s"
        )
        self.speed.setText("")
        if summary.paths:
            self._target_path = Path(summary.paths[0])
            self.reveal_button.setEnabled(True)
