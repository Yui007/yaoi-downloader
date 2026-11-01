"""Format dispatch: verify, build, move, optionally clean."""

from __future__ import annotations

import shutil
from pathlib import Path

from ..errors import ExportError
from ..models import ChapterGroup, DownloadOptions, Series
from ..names import safe_name, unique_dir, unique_path
from .cbz import build_cbz
from .images import move_folder, verify_images
from .pdf import build_pdf

__all__ = ["export_chapter", "write_cover"]


def export_chapter(
    series: Series,
    group: ChapterGroup,
    images_dir: Path,
    options: DownloadOptions,
) -> Path:
    verify_images(images_dir, group.pages or None)
    series_dir = options.out_dir / safe_name(series.title)
    label = safe_name(group.label, 40)
    fmt = options.format

    if fmt == "images":
        destination = unique_dir(series_dir / label)
        return move_folder(images_dir, destination)

    if fmt not in {"cbz", "pdf"}:
        raise ExportError(f"Unknown format {fmt!r}.")

    name = f"{safe_name(series.title)} - {label}.{fmt}"
    out_path = unique_path(series_dir / name)
    if fmt == "cbz":
        result = build_cbz(series, group, images_dir, out_path, group.language or "en")
    else:
        result = build_pdf(series, group, images_dir, out_path)

    if not options.keep_images:
        shutil.rmtree(images_dir, ignore_errors=True)
    return result


def write_cover(series: Series, cover_bytes: bytes, out_dir: Path) -> Path | None:
    if not cover_bytes:
        return None
    try:
        from io import BytesIO

        from PIL import Image

        with Image.open(BytesIO(cover_bytes)) as image:
            if image.width > 600:
                height = max(1, round(image.height * 600 / image.width))
                image = image.resize((600, height), Image.Resampling.LANCZOS)
            target = out_dir / "cover.jpg"
            if target.exists():
                return target
            image.convert("RGB").save(target, "JPEG", quality=88)
            return target
    except Exception:  # noqa: BLE001 - a cover is optional decoration
        return None
