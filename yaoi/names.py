"""Names, sizes, and collision-free targets."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path


def safe_name(value: str, limit: int = 80) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value or ""))
    value = re.sub(r"\s+", " ", value).strip(" .")
    return (value or "untitled")[:limit].strip(" .") or "untitled"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for number in range(2, 1000):
        candidate = path.with_name(f"{path.stem} ({number}){path.suffix}")
        if not candidate.exists():
            return candidate
    return path.with_name(f"{path.stem} ({path.stat().st_mtime_ns}){path.suffix}")


def unique_dir(path: Path) -> Path:
    if not path.exists():
        return path
    for number in range(2, 1000):
        candidate = path.with_name(f"{path.name} ({number})")
        if not candidate.exists():
            return candidate
    return path


def human_bytes(value: int | float | None) -> str:
    if not value:
        return "0 B"
    number = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if number < 1024 or unit == "GB":
            return f"{int(number)} B" if unit == "B" else f"{number:.1f} {unit}"
        number /= 1024
    return f"{number:.1f} GB"


def human_date(ms: int | None) -> str:
    if not ms:
        return "unknown"
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def short_date(ms: int | None) -> str:
    return human_date(ms).replace("unknown", "—")
