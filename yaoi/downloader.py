"""Two pools, one global brake, and a job that always leaves resumable state."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .errors import Cancelled, ExportError
from .export import export_chapter, write_cover
from .filters import filter_chapters
from .http import HttpClient
from .models import (
    ChapterGroup,
    DownloadOptions,
    JobEvent,
    JobSummary,
    Series,
)
from .names import human_bytes, safe_name
from .sources.base import Source

Progress = Callable[[JobEvent], None]


class DownloadJob:
    def __init__(
        self,
        source: Source,
        series: Series,
        groups: list[ChapterGroup],
        options: DownloadOptions,
        client: HttpClient | None = None,
        on_event: Progress | None = None,
        cancel: threading.Event | None = None,
    ):
        self.source = source
        self.series = series
        self.groups = list(groups)
        self.options = options
        self.client = client or HttpClient(
            timeout=40,
            retries=3,
            cache_dir=options.work_dir.parent / "cache",
            cancel=cancel,
        )
        self.on_event = on_event or (lambda event: None)
        self.cancel_event = cancel or threading.Event()
        self.client.cancel = self.cancel_event
        self.paused = threading.Event()
        self._lock = threading.RLock()
        self._started = time.monotonic()
        self._bytes = 0
        self._finished = 0
        self._network = threading.Semaphore(options.global_limit)
        self.summary = JobSummary()
        self._chapter_dirs: dict[int, Path] = self._plan_dirs()

    def _plan_dirs(self) -> dict[int, Path]:
        series_dir = self.options.work_dir / safe_name(self.series.title)
        used: set[str] = set()
        out: dict[int, Path] = {}
        for group in self.groups:
            name = safe_name(group.label, 40)
            if name in used:
                name = f"{name}_{group.variant.chapter_id if group.variant else group.index}"
            used.add(name)
            out[group.index] = series_dir / name
        return out

    def emit(self, event: JobEvent) -> None:
        try:
            self.on_event(event)
        except Exception:  # noqa: BLE001 - a broken face must not break a job
            pass

    def _speed(self, byte_count: int, start: float) -> float:
        elapsed = max(0.001, time.monotonic() - start)
        return byte_count / elapsed

    def run(self) -> JobSummary:
        total_pages = sum(group.pages for group in self.groups)
        self.emit(
            JobEvent(
                kind="job",
                state="downloading",
                total=len(self.groups),
                total_bytes=total_pages,
                message=self.series.title,
            )
        )
        self._write_cover()
        try:
            with ThreadPoolExecutor(max_workers=self.options.chapters_workers) as pool:
                futures = {pool.submit(self._run_chapter, group): group for group in self.groups}
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Cancelled:
                        self._bump_cancelled(futures[future])
                    except Exception as exc:  # noqa: BLE001 - one chapter must not kill the job
                        self._bump_failed(futures[future], str(exc))
        finally:
            with self._lock:
                summary = self.summary
            state = "done" if summary.ok else (
                "cancelled" if summary.cancelled and not summary.failed else "failed"
            )
            self.emit(
                JobEvent(
                    kind="summary",
                    state=state,
                    done=summary.done,
                    total=summary.total,
                    bytes=summary.bytes,
                    message=", ".join(summary.messages[:3]),
                )
            )
        return summary

    def _write_cover(self) -> None:
        if not self.series.cover:
            return
        try:
            data = self.source.cover_bytes(self.series.cover)
            target = self.options.out_dir / safe_name(self.series.title)
            target.mkdir(parents=True, exist_ok=True)
            write_cover(self.series, data, target)
        except Exception:  # noqa: BLE001 - cover is optional
            pass

    def _run_chapter(self, group: ChapterGroup) -> None:
        if self.cancel_event.is_set():
            raise Cancelled("Cancelled.")
        variant = group.variant
        if variant is None:
            raise ExportError(f"Chapter {group.label} has no readable version.")
        self.emit(
            JobEvent(
                kind="chapter",
                chapter_index=group.index,
                label=group.label,
                state="fetching",
                total=group.pages,
                message=variant.source_name,
            )
        )
        pages = self.source.pages(group, variant)
        if len(pages) != group.pages and group.pages:
            raise ExportError(
                f"Chapter {group.label}: {len(pages)} pages returned, {group.pages} expected."
            )
        folder = self._chapter_dirs[group.index]
        folder.mkdir(parents=True, exist_ok=True)
        existing = self._existing(folder)
        done = len(existing)
        total = len(pages)
        chapter_start = time.monotonic()
        chapter_bytes = sum(path.stat().st_size for path in existing.values())
        self.emit(
            JobEvent(
                kind="chapter",
                chapter_index=group.index,
                label=group.label,
                state="downloading",
                done=done,
                total=total,
                bytes=chapter_bytes,
            )
        )
        missing = [page for page in pages if page.index not in existing or self.options.force]
        if missing:
            with ThreadPoolExecutor(max_workers=self.options.images_workers) as pool:
                futures = {pool.submit(self._fetch, page, folder): page for page in missing}
                for future in as_completed(futures):
                    if self.cancel_event.is_set():
                        for pending in futures:
                            pending.cancel()
                        raise Cancelled("Cancelled.")
                    page = futures[future]
                    try:
                        path, size, _ext = future.result()
                    except Cancelled:
                        raise
                    except Exception as exc:  # noqa: BLE001 - page failure is chapter failure
                        raise ExportError(
                            f"Chapter {group.label}, page {page.index} failed: {exc}"
                        ) from exc
                    done += 1
                    chapter_bytes += size
                    with self._lock:
                        self._bytes += size
                    self.emit(
                        JobEvent(
                            kind="chapter",
                            chapter_index=group.index,
                            label=group.label,
                            state="downloading",
                            done=done,
                            total=total,
                            bytes=chapter_bytes,
                            speed=self._speed(chapter_bytes, chapter_start),
                        )
                    )
        if self.cancel_event.is_set():
            raise Cancelled("Cancelled.")
        self.emit(
            JobEvent(
                kind="chapter",
                chapter_index=group.index,
                label=group.label,
                state="exporting",
                done=total,
                total=total,
                bytes=chapter_bytes,
            )
        )
        path = export_chapter(self.series, group, folder, self.options)
        with self._lock:
            self.summary.done += 1
            self.summary.bytes += chapter_bytes
            self.summary.paths.append(str(path))
        self._finished += 1
        self.emit(
            JobEvent(
                kind="chapter",
                chapter_index=group.index,
                label=group.label,
                state="done",
                done=total,
                total=total,
                bytes=chapter_bytes,
                path=str(path),
                speed=self._speed(chapter_bytes, chapter_start),
            )
        )

    def _fetch(self, page, folder: Path):
        while self.paused.is_set() and not self.cancel_event.is_set():
            time.sleep(0.1)
        if self.cancel_event.is_set():
            raise Cancelled("Cancelled.")
        with self._network:
            return self.client.fetch_image(page.url, folder, page.index)

    def _existing(self, folder: Path) -> dict[int, Path]:
        found: dict[int, Path] = {}
        if not folder.exists():
            return found
        for path in folder.iterdir():
            if not path.is_file() or path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"}:
                continue
            stem = path.stem
            if not stem.isdigit():
                continue
            if path.stat().st_size > 0:
                found[int(stem)] = path
        return found

    def _bump_failed(self, group: ChapterGroup, message: str) -> None:
        with self._lock:
            self.summary.failed += 1
            self.summary.messages.append(f"{group.label}: {message}")
        self.emit(
            JobEvent(
                kind="chapter",
                chapter_index=group.index,
                label=group.label,
                state="failed",
                message=message,
            )
        )

    def _bump_cancelled(self, group: ChapterGroup) -> None:
        with self._lock:
            self.summary.cancelled += 1
        self.emit(
            JobEvent(
                kind="chapter",
                chapter_index=group.index,
                label=group.label,
                state="cancelled",
            )
        )

    def pause(self) -> None:
        self.paused.set()
        self.emit(JobEvent(kind="job", state="paused", message=self.series.title))

    def resume(self) -> None:
        self.paused.clear()
        self.emit(JobEvent(kind="job", state="downloading", message=self.series.title))

    def cancel(self) -> None:
        self.cancel_event.set()
        self.paused.clear()


def prepare_groups(
    groups: list[ChapterGroup],
    source: str | None = None,
    language: str | None = None,
) -> list[ChapterGroup]:
    return filter_chapters(groups, source, language)


def summary_line(summary: JobSummary) -> str:
    return (
        f"{summary.done} done · {summary.failed} failed · "
        f"{summary.cancelled} cancelled · {human_bytes(summary.bytes)}"
    )
