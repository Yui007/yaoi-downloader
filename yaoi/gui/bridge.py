"""Thread boundaries: plain data in, Qt signals out."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap

from ..app_context import options_from_settings, source_from_settings
from ..downloader import DownloadJob
from ..models import ChapterGroup, DownloadOptions, Series
from ..sources.yaoi import YaoiSource


class _Signals(QObject):
    result = pyqtSignal(object)
    error = pyqtSignal(str)
    done = pyqtSignal()


class Worker(QRunnable):
    def __init__(self, function: Callable[..., Any], *args: Any, **kwargs: Any):
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.signals = _Signals()

    def run(self) -> None:
        try:
            self.signals.result.emit(self.function(*self.args, **self.kwargs))
        except Exception as exc:  # noqa: BLE001 - surfaced by the face
            self.signals.error.emit(str(exc))
        finally:
            self.signals.done.emit()


class Tasks(QObject):
    """A small pool for listings, detail pages, and key checks."""

    def __init__(self, parent: QObject | None = None, workers: int = 6):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(workers)
        self._active: set[Worker] = set()

    def run(
        self,
        function: Callable[..., Any],
        on_result: Callable[[Any], None],
        on_error: Callable[[str], None] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        worker = Worker(function, *args, **kwargs)
        self._active.add(worker)

        def finish() -> None:
            self._active.discard(worker)

        worker.signals.result.connect(on_result)
        if on_error is not None:
            worker.signals.error.connect(on_error)
        worker.signals.done.connect(finish)
        self.pool.start(worker)


class CoverSignals(QObject):
    ready = pyqtSignal(str, object)
    failed = pyqtSignal(str)


class _CoverTask(QRunnable):
    def __init__(self, url: str, source: YaoiSource, signals: CoverSignals):
        super().__init__()
        self.url = url
        self.source = source
        self.signals = signals

    def run(self) -> None:
        try:
            image = QImage.fromData(self.source.cover_bytes(self.url))
            if image.isNull():
                raise ValueError("empty image")
            self.signals.ready.emit(self.url, image)
        except Exception:  # noqa: BLE001 - covers are decoration
            self.signals.failed.emit(self.url)


class CoverLoader(QObject):
    ready = pyqtSignal(str, object)

    def __init__(self, settings: dict, parent: QObject | None = None):
        super().__init__(parent)
        self.settings = settings
        self.source = source_from_settings(settings)
        self.signals = CoverSignals()
        self.signals.ready.connect(self._store)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(5)
        self._cache: dict[str, QPixmap] = {}
        self._pending: set[str] = set()

    def request(self, url: str) -> QPixmap | None:
        if not url:
            return None
        cached = self._cache.get(url)
        if cached is not None:
            return cached
        if url not in self._pending:
            self._pending.add(url)
            self.pool.start(_CoverTask(url, self.source, self.signals))
        return None

    def cached(self, url: str) -> QPixmap | None:
        return self._cache.get(url)

    def _store(self, url: str, image: QImage) -> None:
        self._pending.discard(url)
        pixmap = QPixmap.fromImage(image)
        if not pixmap.isNull():
            self._cache[url] = pixmap
            if len(self._cache) > 120:
                self._cache.pop(next(iter(self._cache)))
            self.ready.emit(url, pixmap)


class JobRunner(QObject):
    event = pyqtSignal(object)
    finished = pyqtSignal(object, float)
    started = pyqtSignal(object)

    def __init__(
        self,
        settings: dict,
        series: Series,
        groups: list[ChapterGroup],
        options: DownloadOptions,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.settings = settings
        self.series = series
        self.groups = groups
        self.options = options
        self.source = source_from_settings(settings)
        self.job = DownloadJob(
            self.source,
            series,
            groups,
            options,
            client=self.source.client,
            on_event=self.event.emit,
        )
        self.started_at = 0.0

    def start(self) -> None:
        self.started_at = time.monotonic()
        self.started.emit(self)
        runner = _JobTask(self)
        QThreadPool.globalInstance().start(runner)
        self._task = runner

    def pause(self) -> None:
        self.job.pause()

    def resume(self) -> None:
        self.job.resume()

    def toggle_pause(self) -> None:
        if self.job.paused.is_set():
            self.resume()
        else:
            self.pause()

    def cancel(self) -> None:
        self.job.cancel()


class _JobTask(QRunnable):
    def __init__(self, runner: JobRunner):
        super().__init__()
        self.runner = runner

    def run(self) -> None:
        runner = self.runner
        try:
            summary = runner.job.run()
            elapsed = time.monotonic() - runner.started_at
            runner.finished.emit(summary, elapsed)
        finally:
            runner.source.client.close()
