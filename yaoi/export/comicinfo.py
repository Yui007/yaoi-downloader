"""ComicInfo.xml — the subset Kavita and Komga actually read."""

from __future__ import annotations

import re
from xml.sax.saxutils import escape

from ..models import ChapterGroup, Series

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _clean(value: str) -> str:
    return escape(_CONTROL.sub("", str(value or "")).strip(), {'"': "&quot;"})


def _number(label: str) -> str:
    match = re.search(r"\d+(?:\.\d+)?", label or "")
    return match.group() if match else ""


def build_comicinfo(
    series: Series,
    group: ChapterGroup,
    page_count: int,
    language: str = "en",
) -> str:
    title = f"{series.title} - {group.label}"
    fields: list[tuple[str, str]] = [
        ("Title", title),
        ("Series", series.title),
        ("Number", _number(group.label)),
        ("Volume", "0"),
        ("Summary", series.description),
        ("Writer", ", ".join(series.authors)),
        ("Penciller", ", ".join(series.artists)),
        ("Genre", ", ".join(series.genres)),
        ("Tags", ", ".join(series.tags)),
        ("Web", series.url),
        ("LanguageISO", language or "en"),
        ("PageCount", str(page_count)),
        ("Year", series.year),
        ("Manga", "YesAndRightToLeft"),
        ("Notes", f"Downloaded with yaoi · source: {group.variant.source_name if group.variant else 'unknown'}"),
    ]
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<ComicInfo>"]
    for name, value in fields:
        if value:
            lines.append(f"  <{name}>{_clean(value)}</{name}>")
    lines.append("</ComicInfo>")
    return "\n".join(lines) + "\n"
