"""Scanlator/language filters, then re-index so selection means the visible rows."""

from __future__ import annotations

from collections.abc import Iterable

from .models import ChapterGroup


def available_sources(groups: Iterable[ChapterGroup]) -> list[str]:
    names = {variant.source_name for group in groups for variant in group.variants if variant.source_name}
    return sorted(names, key=str.casefold)


def available_languages(groups: Iterable[ChapterGroup]) -> list[str]:
    return sorted(
        {variant.language for group in groups for variant in group.variants if variant.language}
    )


def filter_chapters(
    groups: list[ChapterGroup],
    source: str | None = None,
    language: str | None = None,
) -> list[ChapterGroup]:
    source_key = (source or "").strip().casefold()
    lang_key = (language or "").strip().lower()
    out: list[ChapterGroup] = []
    for group in groups:
        variants = tuple(
            variant
            for variant in group.variants
            if (not source_key or variant.source_name.casefold() == source_key)
            and (not lang_key or variant.language.lower() == lang_key)
        )
        if not variants:
            continue
        out.append(
            ChapterGroup(
                index=len(out) + 1,
                label=group.label,
                created_at=group.created_at,
                extra=group.extra,
                variants=variants,
            )
        )
    return out
