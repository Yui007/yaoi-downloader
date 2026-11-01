"""Immutable core data. Workers read these; only Job mutates."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SeriesCard:
    url: str
    title: str
    cover: str = ""
    year: str = ""
    status: str = ""
    rating: str = ""
    chapters: int = 0
    genres: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "cover": self.cover,
            "year": self.year,
            "status": self.status,
            "rating": self.rating,
            "chapters": self.chapters,
            "genres": list(self.genres),
            "languages": list(self.languages),
        }

    @classmethod
    def from_dict(cls, data: dict) -> SeriesCard:
        return cls(
            url=data.get("url", ""),
            title=data.get("title") or "Untitled",
            cover=data.get("cover", ""),
            year=data.get("year", ""),
            status=data.get("status", ""),
            rating=data.get("rating", ""),
            chapters=int(data.get("chapters") or 0),
            genres=tuple(data.get("genres") or ()),
            languages=tuple(data.get("languages") or ()),
        )


@dataclass(frozen=True)
class Series:
    source: str
    url: str
    title: str
    cover: str = ""
    authors: tuple[str, ...] = ()
    artists: tuple[str, ...] = ()
    genres: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    status: str = ""
    year: str = ""
    description: str = ""
    type: str = ""
    score: str = ""
    alt_titles: tuple[str, ...] = ()
    content_rating: str = ""
    start_date: str = ""

    @property
    def authors_line(self) -> str:
        return ", ".join(self.authors) or "Unknown"

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "url": self.url,
            "title": self.title,
            "cover": self.cover,
            "authors": list(self.authors),
            "artists": list(self.artists),
            "genres": list(self.genres),
            "tags": list(self.tags),
            "status": self.status,
            "year": self.year,
            "description": self.description,
            "type": self.type,
            "score": self.score,
            "alt_titles": list(self.alt_titles),
            "content_rating": self.content_rating,
            "start_date": self.start_date,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Series:
        return cls(
            source=data.get("source", "yaoi"),
            url=data.get("url", ""),
            title=data.get("title") or "Untitled",
            cover=data.get("cover", ""),
            authors=tuple(data.get("authors") or ()),
            artists=tuple(data.get("artists") or ()),
            genres=tuple(data.get("genres") or ()),
            tags=tuple(data.get("tags") or ()),
            status=data.get("status", ""),
            year=data.get("year", ""),
            description=data.get("description", ""),
            type=data.get("type", ""),
            score=data.get("score", ""),
            alt_titles=tuple(data.get("alt_titles") or ()),
            content_rating=data.get("content_rating", ""),
            start_date=data.get("start_date", ""),
        )


@dataclass(frozen=True)
class Variant:
    source_id: str
    source_name: str
    chapter_id: str
    pages: int
    bytes: int
    language: str = ""

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "chapter_id": self.chapter_id,
            "pages": self.pages,
            "bytes": self.bytes,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Variant:
        return cls(
            source_id=str(data.get("source_id", "")),
            source_name=data.get("source_name", ""),
            chapter_id=str(data.get("chapter_id", "")),
            pages=int(data.get("pages") or 0),
            bytes=int(data.get("bytes") or 0),
            language=data.get("language", ""),
        )


@dataclass(frozen=True)
class ChapterGroup:
    index: int
    label: str
    created_at: int = 0
    extra: bool = False
    variants: tuple[Variant, ...] = ()

    @property
    def variant(self) -> Variant | None:
        return self.variants[0] if self.variants else None

    @property
    def pages(self) -> int:
        return self.variant.pages if self.variant else 0

    @property
    def size(self) -> int:
        return self.variant.bytes if self.variant else 0

    @property
    def language(self) -> str:
        return self.variant.language if self.variant else ""

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "label": self.label,
            "created_at": self.created_at,
            "extra": self.extra,
            "variants": [v.to_dict() for v in self.variants],
        }

    @classmethod
    def from_dict(cls, data: dict) -> ChapterGroup:
        return cls(
            index=int(data.get("index") or 0),
            label=data.get("label") or "?",
            created_at=int(data.get("created_at") or 0),
            extra=bool(data.get("extra")),
            variants=tuple(Variant.from_dict(v) for v in data.get("variants") or ()),
        )


@dataclass(frozen=True)
class PageRef:
    index: int
    hash: str
    url: str
    ext: str = ""


@dataclass(frozen=True)
class DownloadOptions:
    format: str = "cbz"
    keep_images: bool = False
    chapters_workers: int = 4
    images_workers: int = 6
    out_dir: Path = Path("library")
    work_dir: Path = Path("downloads")
    force: bool = False
    global_limit: int = 24

    def __post_init__(self) -> None:
        object.__setattr__(self, "format", self.format.lower())
        object.__setattr__(self, "chapters_workers", max(1, min(8, self.chapters_workers)))
        object.__setattr__(self, "images_workers", max(1, min(10, self.images_workers)))


@dataclass(frozen=True)
class JobEvent:
    kind: str
    chapter_index: int = 0
    label: str = ""
    state: str = ""
    done: int = 0
    total: int = 0
    bytes: int = 0
    total_bytes: int = 0
    message: str = ""
    path: str = ""
    speed: float = 0.0

    def to_dict(self) -> dict:
        return {
            "event": self.kind,
            "chapter_index": self.chapter_index,
            "label": self.label,
            "state": self.state,
            "done": self.done,
            "total": self.total,
            "bytes": self.bytes,
            "total_bytes": self.total_bytes,
            "message": self.message,
            "path": self.path,
            "speed": round(self.speed, 2),
        }


@dataclass
class JobSummary:
    done: int = 0
    failed: int = 0
    cancelled: int = 0
    bytes: int = 0
    paths: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.done + self.failed + self.cancelled

    @property
    def ok(self) -> bool:
        return self.failed == 0 and self.cancelled == 0


def cards_from_dict(data: list[dict[str, Any]]) -> list[SeriesCard]:
    return [SeriesCard.from_dict(item) for item in data]


def groups_from_dict(data: list[dict[str, Any]]) -> list[ChapterGroup]:
    return [ChapterGroup.from_dict(item) for item in data]
