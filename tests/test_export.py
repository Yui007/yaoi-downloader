from __future__ import annotations

import zipfile
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from yaoi.export import export_chapter
from yaoi.export.cbz import build_cbz
from yaoi.export.pdf import build_pdf
from yaoi.models import ChapterGroup, DownloadOptions, Series, Variant


def make_images(folder: Path, count: int = 2) -> None:
    folder.mkdir(parents=True)
    for index in range(1, count + 1):
        Image.new("RGB", (64, 96), (index * 40, 90, 130)).save(folder / f"{index:03d}.png")


def series_and_group(pages: int):
    series = Series(
        source="yaoi",
        url="https://yaoi.me/series/1/test",
        title="Test Series",
        authors=("A",),
        artists=("B",),
        genres=("Drama",),
        tags=("tag",),
        year="2024",
        description="Summary",
    )
    group = ChapterGroup(
        index=1,
        label="23.5",
        variants=(Variant("1", "Scarlet", "2", pages, 100, "en"),),
    )
    return series, group


def test_cbz_layout_and_page_count(tmp_path):
    pages = tmp_path / "pages"
    make_images(pages, 2)
    series, group = series_and_group(2)
    output = build_cbz(series, group, pages, tmp_path / "book.cbz")
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        assert names[0] == "ComicInfo.xml"
        assert names[1:] == ["001.png", "002.png"]
        assert b"<PageCount>2</PageCount>" in archive.read("ComicInfo.xml")


def test_pdf_page_count(tmp_path):
    pages = tmp_path / "pages"
    make_images(pages, 2)
    series, group = series_and_group(2)
    output = build_pdf(series, group, pages, tmp_path / "book.pdf")
    assert len(PdfReader(str(output)).pages) == 2


def test_export_dispatch_and_cleanup(tmp_path):
    pages = tmp_path / "pages"
    make_images(pages, 2)
    series, group = series_and_group(2)
    options = DownloadOptions(
        format="cbz",
        keep_images=False,
        out_dir=tmp_path / "library",
        work_dir=tmp_path / "downloads",
    )
    output = export_chapter(series, group, pages, options)
    assert output.exists()
    assert not pages.exists()


def test_raw_images_move(tmp_path):
    pages = tmp_path / "pages"
    make_images(pages, 2)
    series, group = series_and_group(2)
    options = DownloadOptions(
        format="images",
        out_dir=tmp_path / "library",
        work_dir=tmp_path / "downloads",
    )
    output = export_chapter(series, group, pages, options)
    assert output.is_dir()
    assert len(list(output.glob("*.png"))) == 2
