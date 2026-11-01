"""Verify a page folder; every export starts here."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from ..errors import ExportError

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"}


def image_files(folder: Path) -> list[Path]:
    files = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]
    return sorted(files, key=lambda path: (int(re.sub(r"\D", "", path.stem) or 0), path.name))


def verify_images(folder: Path, expected: int | None = None) -> list[Path]:
    if not folder.exists():
        raise ExportError(f"Page folder is missing: {folder}")
    files = image_files(folder)
    if expected is not None and len(files) != expected:
        raise ExportError(f"{len(files)} images found, {expected} expected; folder kept.")
    if not files:
        raise ExportError(f"No images in {folder}; folder kept.")
    for path in files:
        try:
            if path.stat().st_size == 0:
                raise ExportError(f"Zero-byte image: {path.name}; folder kept.")
        except OSError as exc:
            raise ExportError(f"Cannot read {path.name}: {exc}") from exc
    return files


def move_folder(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(source), str(destination))
    except OSError as exc:
        raise ExportError(f"Could not move {source.name} into the library: {exc}") from exc
    return destination
