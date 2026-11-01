from __future__ import annotations

import json
import threading
from pathlib import Path

from PIL import Image

from yaoi.downloader import DownloadJob
from yaoi.models import ChapterGroup, DownloadOptions, PageRef, Series, Variant


class FakeClient:
    def __init__(self):
        self.cancel = threading.Event()
        self.bytes = 0
        self.calls = 0

    def fetch_image(self, url, folder: Path, index: int):
        self.calls += 1
        path = folder / f"{index:03d}.png"
        Image.new("RGB", (32, 48), (index * 20, 50, 80)).save(path)
        size = path.stat().st_size
        self.bytes += size
        return path, size, ".png"


class FakeSource:
    def __init__(self):
        self.client = FakeClient()

    def cover_bytes(self, url: str, ttl: int = 0) -> bytes:
        return b""

    def pages(self, group, variant):
        return [
            PageRef(index, f"h{index}", f"https://example/{index}")
            for index in range(1, group.pages + 1)
        ]


def series_group(pages: int = 3):
    series = Series(
        source="yaoi",
        url="https://yaoi.me/series/1/test",
        title="Test Series",
        authors=("A",),
        genres=("Drama",),
        description="Summary",
    )
    group = ChapterGroup(
        index=1,
        label="1",
        variants=(Variant("1", "Scarlet", "c1", pages, 100, "en"),),
    )
    return series, group


def options(tmp: Path):
    return DownloadOptions(
        format="cbz",
        keep_images=False,
        chapters_workers=1,
        images_workers=2,
        out_dir=tmp / "library",
        work_dir=tmp / "downloads",
    )


def test_download_job_export(tmp_path):
    series, group = series_group(3)
    source = FakeSource()
    events = []
    job = DownloadJob(
        source,
        series,
        [group],
        options(tmp_path),
        client=source.client,
        on_event=events.append,
    )
    summary = job.run()
    assert summary.done == 1
    assert summary.failed == 0
    assert source.client.calls == 3
    assert list((tmp_path / "library" / "Test Series").glob("*.cbz"))
    assert events[0].kind == "job"
    assert events[-1].kind == "summary"


def test_download_job_resume_skips_existing(tmp_path):
    series, group = series_group(3)
    source = FakeSource()
    folder = tmp_path / "downloads" / "Test Series" / "1"
    folder.mkdir(parents=True)
    Image.new("RGB", (32, 48)).save(folder / "001.png")
    job = DownloadJob(source, series, [group], options(tmp_path), client=source.client)
    summary = job.run()
    assert summary.done == 1
    assert source.client.calls == 2


def test_cancel_before_start(tmp_path):
    series, group = series_group(3)
    source = FakeSource()
    cancel = threading.Event()
    cancel.set()
    job = DownloadJob(
        source,
        series,
        [group],
        options(tmp_path),
        client=source.client,
        cancel=cancel,
    )
    summary = job.run()
    assert summary.cancelled == 1
    assert summary.done == 0
    assert source.client.calls == 0
