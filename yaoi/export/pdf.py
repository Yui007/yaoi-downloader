"""PDF: lossless for JPEG/PNG, transcode WebP/AVIF, verify page count."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import img2pdf
from PIL import Image
from pypdf import PdfReader

from ..errors import ExportError
from ..models import ChapterGroup, Series
from .images import verify_images

_DIRECT = {".jpg", ".jpeg", ".png"}


def _convert(path: Path, target: Path) -> None:
    with Image.open(path) as image:
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        image.save(target, "JPEG", quality=92)


def build_pdf(
    series: Series,
    group: ChapterGroup,
    images_dir: Path,
    out_path: Path,
) -> Path:
    files = verify_images(images_dir, group.pages or None)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    part = out_path.with_name(out_path.name + ".part")
    try:
        with tempfile.TemporaryDirectory(prefix="yaoi-pdf-", dir=out_path.parent) as temp:
            prepared: list[str] = []
            for index, path in enumerate(files, 1):
                if path.suffix.lower() in _DIRECT:
                    prepared.append(str(path))
                else:
                    target = Path(temp) / f"{index:03d}.jpg"
                    _convert(path, target)
                    prepared.append(str(target))
            title = f"{series.title} - {group.label}"
            with open(part, "wb") as handle:
                handle.write(img2pdf.convert(prepared, title=title))
        reader = PdfReader(str(part))
        if len(reader.pages) != len(files):
            raise ExportError(f"PDF has {len(reader.pages)} pages, {len(files)} expected.")
        os.replace(part, out_path)
        return out_path
    except Exception as exc:
        part.unlink(missing_ok=True)
        if isinstance(exc, ExportError):
            raise
        raise ExportError(f"PDF build failed: {exc}") from exc
