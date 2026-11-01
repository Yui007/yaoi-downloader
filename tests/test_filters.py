from __future__ import annotations

from yaoi.filters import available_languages, available_sources, filter_chapters
from yaoi.models import ChapterGroup, Variant


def group(index, label, variants):
    return ChapterGroup(index=index, label=label, variants=tuple(variants))


def variant(source, language):
    return Variant(
        source_id=source,
        source_name=source,
        chapter_id=f"{source}-{language}",
        pages=10,
        bytes=100,
        language=language,
    )


def test_filter_and_reindex():
    groups = [
        group(1, "1", [variant("Scarlet", "en"), variant("Cyan", "es")]),
        group(2, "2", [variant("Cyan", "en")]),
        group(3, "3", [variant("Scarlet", "es")]),
    ]
    assert available_sources(groups) == ["Cyan", "Scarlet"]
    assert available_languages(groups) == ["en", "es"]

    visible = filter_chapters(groups, "Cyan", None)
    assert [item.label for item in visible] == ["1", "2"]
    assert [item.index for item in visible] == [1, 2]
    assert visible[0].variant.language == "es"

    english = filter_chapters(groups, None, "en")
    assert [item.label for item in english] == ["1", "2"]
    assert english[0].variant.source_name == "Scarlet"
