"""CBZ: stored images at the archive root, ComicInfo first, atomic replace."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from ..errors import ExportError
from ..models import ChapterGroup, Series
from .comicinfo import build_comicinfo
from .images import verify_images


def build_cbz(
    series: Series,
    group: ChapterGroup,
    images_dir: Path,
    out_path: Path,
    language: str = "en",
) -> Path:
    files = verify_images(images_dir, group.pages or None)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    part = out_path.with_name(out_path.name + ".part")
    info = build_comicinfo(series, group, len(files), language)
    try:
        with zipfile.ZipFile(part, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("ComicInfo.xml", info)
            for path in files:
                archive.write(path, arcname=path.name)
        with zipfile.ZipFile(part) as archive:
            names = archive.namelist()
            if names[0] != "ComicInfo.xml":
                raise ExportError("ComicInfo.xml is not the first CBZ entry.")
            images = [name for name in names if not name.lower().endswith(".xml")]
            if len(images) != len(files):
                raise ExportError(f"CBZ has {len(images)} images, {len(files)} expected.")
            root = ET.fromstring(archive.read("ComicInfo.xml"))
            if root.findtext("PageCount") != str(len(files)):
                raise ExportError("ComicInfo PageCount does not match the archive.")
        os.replace(part, out_path)
        return out_path
    except Exception as exc:
        part.unlink(missing_ok=True)
        if isinstance(exc, ExportError):
            raise
        raise ExportError(f"CBZ build failed: {exc}") from exc
