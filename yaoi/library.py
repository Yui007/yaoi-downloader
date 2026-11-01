"""Read-only scan of the library folder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .names import human_bytes


@dataclass(frozen=True)
class LibrarySeries:
    title: str
    path: Path
    chapters: int
    archives: int
    bytes: int
    updated: float
    cover: Path | None = None

    @property
    def size_label(self) -> str:
        return human_bytes(self.bytes)


def scan_library(root: Path) -> list[LibrarySeries]:
    if not root.exists():
        return []
    items: list[LibrarySeries] = []
    for folder in root.iterdir():
        if not folder.is_dir():
            continue
        archives = [path for path in folder.iterdir() if path.suffix.lower() in {".cbz", ".pdf"}]
        chapter_dirs = [
            path
            for path in folder.iterdir()
            if path.is_dir()
            and any(
                child.is_file() and child.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"}
                for child in path.iterdir()
            )
        ]
        files = archives + [
            file for folder_path in chapter_dirs for file in folder_path.iterdir() if file.is_file()
        ]
        if not files:
            continue
        total = sum(file.stat().st_size for file in files)
        latest = max((file.stat().st_mtime for file in files), default=folder.stat().st_mtime)
        cover = folder / "cover.jpg"
        items.append(
            LibrarySeries(
                title=folder.name,
                path=folder,
                chapters=len(archives) + len(chapter_dirs),
                archives=len(archives),
                bytes=total,
                updated=latest,
                cover=cover if cover.exists() else None,
            )
        )
    return sorted(items, key=lambda item: item.updated, reverse=True)


def open_path(path: Path) -> None:
    import os
    import subprocess
    import sys

    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
