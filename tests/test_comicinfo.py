from __future__ import annotations

import xml.etree.ElementTree as ET

from yaoi.export.comicinfo import build_comicinfo
from yaoi.models import ChapterGroup, Series, Variant

SERIES = Series(
    source="yaoi",
    url="https://yaoi.me/series/1/test",
    title="A & B",
    authors=("Writer",),
    artists=("Artist",),
    genres=("Drama",),
    tags=("tag",),
    year="2024",
    description="Line one\nLine two",
)
GROUP = ChapterGroup(
    index=1,
    label="23.5",
    variants=(
        Variant("1", "Scarlet", "2", 18, 100, "en"),
    ),
)


def test_comicinfo_fields_and_escaping():
    xml = build_comicinfo(SERIES, GROUP, 18)
    root = ET.fromstring(xml)
    assert root.findtext("Series") == "A & B"
    assert root.findtext("Number") == "23.5"
    assert root.findtext("PageCount") == "18"
    assert root.findtext("Manga") == "YesAndRightToLeft"
    assert root.findtext("Notes").endswith("Scarlet")
    assert "\n" in root.findtext("Summary")


def test_empty_values_are_omitted():
    series = Series(source="yaoi", url="u", title="T")
    group = ChapterGroup(index=1, label="1", variants=(Variant("1", "s", "c", 1, 1, ""),))
    root = ET.fromstring(build_comicinfo(series, group, 1))
    assert root.find("Writer") is None
    assert root.find("Summary") is None
    assert root.find("Year") is None
