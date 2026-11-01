"""yaoi.me adapter: listings, metadata, signed reader, and page hashes."""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from bs4 import BeautifulSoup

from ..config import ROOT
from ..errors import AuthError, SealError, SourceError
from ..http import HttpClient
from ..models import ChapterGroup, PageRef, Series, SeriesCard, Variant
from . import keys as keylib

BASE = "https://yaoi.me"
_HOSTS = {"yaoi.me", "www.yaoi.me"}
_LANG = {
    "English": "en",
    "Spanish": "es",
    "Portuguese": "pt",
    "French": "fr",
    "German": "de",
    "Italian": "it",
    "Russian": "ru",
    "Japanese": "ja",
    "Korean": "ko",
    "Chinese": "zh",
    "Arabic": "ar",
    "Turkish": "tr",
    "Polish": "pl",
}


def rsc_payload(html: str) -> str:
    rows = re.findall(
        r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)',
        html,
        flags=re.S,
    )
    out: list[str] = []
    for row in rows:
        try:
            out.append(json.loads(f'"{row}"'))
        except json.JSONDecodeError:
            continue
    return "".join(out)


def balanced_slice(text: str, start: int) -> str:
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        char = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise SourceError("Unbalanced JSON in the series payload.")


def extract_groups(html: str) -> list[dict]:
    payload = rsc_payload(html)
    needle = '"groups":['
    pos = payload.find(needle)
    if pos < 0:
        raise SourceError("Chapter groups were not found in the series payload.")
    start = pos + len(needle) - 1
    try:
        groups = json.loads(balanced_slice(payload, start))
    except (ValueError, json.JSONDecodeError) as exc:
        raise SourceError("The chapter payload was not valid JSON.") from exc
    if not isinstance(groups, list):
        raise SourceError("The chapter payload has an unexpected shape.")
    return groups


def _first(pattern: str, text: str, default: str = "") -> str:
    match = re.search(pattern, text, flags=re.I | re.S)
    return match.group(1).strip() if match else default


def _absolute(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return BASE + url
    return url


class YaoiSource:
    id = "yaoi"
    name = "yaoi.me"

    def __init__(
        self,
        client: HttpClient | None = None,
        keys_path: Path | None = None,
        cache_ttl: int = 21600,
    ):
        self.client = client or HttpClient()
        self.store = keylib.KeyStore(keys_path or (ROOT / "keys.json"))
        self.cache_ttl = cache_ttl
        self._auth_lock = threading.Lock()
        self._last_refresh = 0.0
        self._sources_maps: dict[str, dict[str, str]] = {}

    # ---------- listings ----------

    def search(self, query: str, limit: int = 24) -> list[SeriesCard]:
        query = query.strip()
        if not query:
            return []
        return self._listing(f"/browse?q={quote(query)}&sort=relevance", limit)

    def trending(self, limit: int = 24) -> list[SeriesCard]:
        return self._listing("/browse?sort=popular", limit)

    def latest(self, limit: int = 24) -> list[SeriesCard]:
        return self._listing("/browse?sort=update", limit)

    def _listing(self, path: str, limit: int) -> list[SeriesCard]:
        key = f"listing|{path}|{limit}"
        cached = self.client.cached_json(
            key,
            self.cache_ttl,
            lambda: [card.to_dict() for card in self._parse_cards(self.client.get_text(BASE + path), limit)],
        )
        return [SeriesCard.from_dict(item) for item in cached]

    def _parse_cards(self, html: str, limit: int) -> list[SeriesCard]:
        soup = BeautifulSoup(html, "html.parser")
        found: list[SeriesCard] = []
        seen: set[str] = set()

        def add(anchor, title: str) -> None:
            href = _absolute(anchor.get("href", ""))
            if not href.startswith(BASE + "/series/") or href in seen:
                return
            seen.add(href)
            container = anchor
            if not container.select_one("img[src^='/i/c/']"):
                for _ in range(5):
                    if container.parent is None:
                        break
                    container = container.parent
                    if container.select_one("img[src^='/i/c/']"):
                        break
            image = container.select_one("img[src^='/i/c/']") or container.select_one("img")
            cover = _absolute(image.get("src", "") if image else "")
            status = ""
            labels = container.select_one(".cover-labels")
            if labels:
                status = labels.get_text(" ", strip=True)
            if not status:
                status = _first(r"\b(Ongoing|Completed|Hiatus|Cancelled|Canceled|Upcoming|Dropped)\b", container.get_text(" ", strip=True))
            rating = ""
            rating_node = container.select_one(".card-rating")
            if rating_node:
                rating = rating_node.get_text(" ", strip=True)
            chapters = 0
            chapters_node = container.select_one(".card-chapters")
            if chapters_node:
                chapters = int(_first(r"(\d+)", chapters_node.get_text(), "0") or 0)
            trail = container.select_one(".card-trail")
            genres = tuple(
                part.strip(" ,")
                for part in (trail.get_text(" ", strip=True).split(",") if trail else ())
                if part.strip(" ,")
            )
            languages = tuple(
                sorted(
                    {
                        _LANG.get(img.get("title", ""), img.get("title", ""))
                        for img in container.select("img[title]")
                        if img.get("title")
                    }
                )
            )
            found.append(
                SeriesCard(
                    url=href,
                    title=" ".join(title.split()),
                    cover=cover,
                    status=status.split()[0] if status else "",
                    rating=rating,
                    chapters=chapters,
                    genres=genres,
                    languages=languages,
                )
            )

        for anchor in soup.select("a.card-title[href^='/series/']"):
            add(anchor, anchor.get("title") or anchor.get_text(" ", strip=True))
        for anchor in soup.select("a.tile[title][href^='/series/']"):
            add(anchor, anchor.get("title") or "")
        return found[: max(1, limit)]

    # ---------- series ----------

    def normalize_url(self, url: str) -> str:
        value = (url or "").strip()
        if not value:
            raise SourceError("Paste a yaoi.me series URL.")
        if not value.startswith(("http://", "https://")):
            value = "https://" + value
        parsed = urlparse(value)
        if parsed.netloc not in _HOSTS:
            raise SourceError("Expected a yaoi.me URL.")
        if not parsed.path.startswith("/series/"):
            raise SourceError("Expected a /series/... URL.")
        return f"{BASE}{parsed.path.rstrip('/')}"

    def series(self, url: str) -> Series:
        canonical = self.normalize_url(url)
        data = self.client.cached_json(
            f"series|{canonical}",
            self.cache_ttl,
            lambda: self._parse_series(self.client.get_text(canonical), canonical).to_dict(),
        )
        return Series.from_dict(data)

    def _parse_series(self, html: str, canonical: str = "") -> Series:
        soup = BeautifulSoup(html, "html.parser")
        ld: dict[str, Any] = {}
        for tag in soup.find_all("script", {"type": "application/ld+json"}):
            try:
                payload = json.loads(tag.string or "")
            except (json.JSONDecodeError, TypeError):
                continue
            items = payload if isinstance(payload, list) else [payload]
            for item in items:
                if isinstance(item, dict) and item.get("@type") == "ComicSeries":
                    ld = item
                    break
            if ld:
                break

        h1 = soup.find("h1")
        head = h1.find_parent("div") if h1 else None
        head_text = head.get_text(" ", strip=True) if head else soup.get_text(" ", strip=True)
        page_text = soup.get_text(" ", strip=True)
        title = ld.get("name") or (h1.get_text(" ", strip=True) if h1 else "Unknown")
        authors = tuple(
            item.get("name", "").strip()
            for item in ld.get("author", [])
            if isinstance(item, dict) and item.get("name")
        )
        links: list[str] = []
        for anchor in soup.select('a[href^="/author/"]'):
            name = anchor.get_text(" ", strip=True)
            if name and name not in links:
                links.append(name)
        artists = tuple(name for name in links if name not in authors)
        genres = tuple(ld.get("genre") or [
            a.get_text(" ", strip=True) for a in soup.select('a[href^="/genre/"]')
        ])
        tags: list[str] = []
        for anchor in soup.select('a[href^="/tag/"]'):
            name = anchor.get_text(" ", strip=True)
            if name and name not in tags:
                tags.append(name)
        prose = soup.select_one(".prose-text")
        description = prose.get_text(" ", strip=True) if prose else ld.get("description", "")
        cover = ld.get("image", "")
        if not cover:
            image = soup.select_one("img[src*='/i/c/']")
            cover = image.get("src", "") if image else ""
        link = soup.select_one('link[rel="canonical"]')
        page_url = _absolute(link.get("href", "")) if link else ""
        return Series(
            source=self.id,
            url=page_url or canonical,
            title=title,
            cover=_absolute(cover),
            authors=tuple(authors),
            artists=artists,
            genres=tuple(g for g in genres if g),
            tags=tuple(tags),
            status=_first(r"\b(Ongoing|Completed|Hiatus|Cancelled|Canceled|Upcoming|Dropped)\b", head_text),
            year=_first(r"\b((?:19|20)\d{2})\b", head_text),
            description=description,
            type=_first(r"\b(Manga|Manhwa|Manhua|Novel)\b", head_text),
            score=_first(r"([0-9]+(?:\.[0-9]+)?)\s*score", page_text),
            alt_titles=tuple(ld.get("alternateName") or ()),
            content_rating=ld.get("contentRating", ""),
            start_date=ld.get("startDate", ""),
        )

    # ---------- chapters ----------

    def chapters(self, series: Series) -> list[ChapterGroup]:
        canonical = self.normalize_url(series.url)
        data = self.client.cached_json(
            f"chapters|{canonical}",
            self.cache_ttl,
            lambda: [group.to_dict() for group in self._parse_chapters(canonical)],
        )
        return [ChapterGroup.from_dict(item) for item in data]

    def _parse_chapters(self, url: str) -> list[ChapterGroup]:
        html = self.client.get_text(url)
        raw_groups = extract_groups(html)
        sources = self._source_names(url, raw_groups)
        groups: list[ChapterGroup] = []
        for group in raw_groups:
            variants = tuple(
                Variant(
                    source_id=str(item.get("s", "")),
                    source_name=sources.get(str(item.get("s", "")), f"Source {item.get('s', '?')}"),
                    chapter_id=str(item.get("id", "")),
                    pages=int(item.get("nPages") or 0),
                    bytes=int(item.get("b") or 0),
                    language=str(item.get("lang") or ""),
                )
                for item in (group.get("variants") or [])
            )
            if not variants:
                continue
            groups.append(
                ChapterGroup(
                    index=len(groups) + 1,
                    label=str(group.get("label") or "?"),
                    created_at=int(group.get("createdAt") or 0),
                    extra=bool(group.get("extra")),
                    variants=variants,
                )
            )
        return groups

    def _source_names(self, series_url: str, raw_groups: list[dict]) -> dict[str, str]:
        cached = self._sources_maps.get(series_url)
        if cached is not None:
            return cached
        first = next(
            (group["variants"][0] for group in raw_groups if group.get("variants")),
            None,
        )
        if not first:
            return {}
        path = f"/api/reader/chapter?s={first.get('s')}&c={first.get('id')}"
        try:
            payload = self.client.cached_json(
                f"chapter-raw|{first.get('s')}|{first.get('id')}",
                0,
                lambda: self._signed_payload(path, series_url),
            )
            chapter = payload.get("chapter") or {}
            names = {str(k): str(v) for k, v in (chapter.get("sources") or {}).items()}
            self._sources_maps[series_url] = names
            return names
        except Exception:  # noqa: BLE001 - names are decoration; chapters still work
            return {}

    # ---------- pages ----------

    def pages(self, group: ChapterGroup, variant: Variant) -> list[PageRef]:
        path = f"/api/reader/chapter?s={variant.source_id}&c={variant.chapter_id}"
        payload = self.client.cached_json(
            f"reader|{variant.source_id}|{variant.chapter_id}",
            0,
            lambda: self._signed_payload(path, ""),
        )
        chapter = payload.get("chapter") or {}
        sealed = chapter.get("sealed")
        if not sealed:
            raise SealError("This chapter has no sealed page payload.")
        info = self._keys()
        plain = keylib.unseal(sealed, info.seal)
        hashes = plain.get("p") or []
        pages = chapter.get("pages") or []
        if len(hashes) != len(pages) or not hashes:
            raise SealError(f"Page/hash mismatch: {len(pages)} pages, {len(hashes)} hashes.")
        return [
            PageRef(index=i + 1, hash=str(hash_value), url=f"{BASE}/i/p/{hash_value}")
            for i, hash_value in enumerate(hashes)
        ]

    def _keys(self):
        return self.store.load()

    def _signed_payload(self, path: str, series_url: str) -> dict:
        info = self._keys()
        headers = keylib.signed_headers(path, info.sign)
        try:
            response = self.client.get(BASE + path, headers=headers, raise_on_status=False)
            if response.status_code in {401, 403}:
                raise AuthError(f"Reader API rejected the signature ({response.status_code}).")
            response.raise_for_status()
            payload = response.json()
            if "sealed" in (payload.get("chapter") or {}):
                keylib.unseal(payload["chapter"]["sealed"], info.seal)
            return payload
        except (AuthError, SealError):
            self._try_refresh(series_url)
            info = self._keys()
            response = self.client.get(
                BASE + path,
                headers=keylib.signed_headers(path, info.sign),
                raise_on_status=False,
            )
            if response.status_code in {401, 403}:
                raise AuthError(f"Reader API rejected the refreshed signature ({response.status_code}).")
            response.raise_for_status()
            return response.json()

    def _try_refresh(self, series_url: str) -> None:
        with self._auth_lock:
            if time.time() - self._last_refresh < 60:
                return
            self._last_refresh = time.time()
            keylib.refresh(self.client, self.store, series_url or BASE)

    # ---------- covers ----------

    def cover_bytes(self, url: str, ttl: int = 86400) -> bytes:
        return self.client.get_bytes(url, ttl=ttl, key=f"cover|{url}")
