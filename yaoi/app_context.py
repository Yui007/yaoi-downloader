"""Build the same source and options for both faces."""

from __future__ import annotations

from pathlib import Path

from .config import ROOT, ensure_dirs, paths, resolve, workers
from .http import HttpClient
from .models import DownloadOptions
from .sources.yaoi import YaoiSource


def source_from_settings(settings: dict) -> YaoiSource:
    dirs = ensure_dirs(settings)
    client = HttpClient(
        timeout=int(settings["network"]["timeout"]),
        retries=int(settings["network"]["retries"]),
        cache_dir=dirs["cache"],
    )
    return YaoiSource(
        client=client,
        keys_path=ROOT / "keys.json",
        cache_ttl=int(settings["network"]["cache_ttl"]),
    )


def options_from_settings(
    settings: dict,
    *,
    format: str | None = None,
    keep_images: bool | None = None,
    chapters_workers: int | None = None,
    images_workers: int | None = None,
    out: Path | None = None,
) -> DownloadOptions:
    dirs = paths(settings)
    chapter_workers, image_workers = workers(settings)
    return DownloadOptions(
        format=resolve(settings, "download", "format", format),
        keep_images=bool(resolve(settings, "download", "keep_images", keep_images)),
        chapters_workers=int(chapters_workers or chapter_workers),
        images_workers=int(images_workers or image_workers),
        out_dir=(out or dirs["library"]),
        work_dir=dirs["downloads"],
    )
