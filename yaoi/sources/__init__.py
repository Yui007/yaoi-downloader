"""Source registry — adding a site is one file and one line."""

from __future__ import annotations

from .base import Source
from .yaoi import YaoiSource

SOURCES: dict[str, Source] = {"yaoi": YaoiSource()}


def get_source(source_id: str = "yaoi") -> Source:
    try:
        return SOURCES[source_id]
    except KeyError as exc:
        raise KeyError(f"Unknown source {source_id!r}") from exc
