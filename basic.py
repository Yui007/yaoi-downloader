#!/usr/bin/env python3
"""Inspect a yaoi.me series and download its latest chapter.

Install:
    pip install requests beautifulsoup4 cryptography
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

BASE = "https://yaoi.me"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

# Public constants from the site's reader bundle (module 50309).
# They can change when the site redeploys.
SIGN_KEY = bytes.fromhex(
    "85cedf4fed3602c3a35c18010b502584"
    "dee9594708ba673052d562c7f2b1a9de"
)
SEAL_KEY = bytes.fromhex(
    "10dd8dff9911000f9286d3dfd8b9f72b"
    "3f763c2f783f89f5c384cff4a11988ac"
)

TIMEOUT = 40
IMAGE_WORKERS = 4


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    return s


def rsc_payload(html: str) -> str:
    """Join the self.__next_f flight rows into one text blob."""
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
    """Return the complete JSON array/object beginning at start."""
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("unbalanced JSON in RSC payload")


def extract_groups(html: str) -> list[dict]:
    payload = rsc_payload(html)
    needle = '"groups":['
    pos = payload.find(needle)
    if pos < 0:
        raise ValueError("chapter groups not found in series payload")
    start = pos + len(needle) - 1
    return json.loads(balanced_slice(payload, start))


def json_ld(soup: BeautifulSoup) -> dict:
    for tag in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and item.get("@type") == "ComicSeries":
                return item
    return {}


def first_match(pattern: str, text: str, default: str = "") -> str:
    m = re.search(pattern, text, flags=re.I | re.S)
    return m.group(1).strip() if m else default


def human_bytes(value: int | float | None) -> str:
    if not value:
        return "0 B"
    value = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} GB"


def human_date(ms: int | None) -> str:
    if not ms:
        return "unknown"
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def safe_name(value: str, limit: int = 80) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return (value or "untitled")[:limit]


def series_metadata(html: str, groups: list[dict]) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    ld = json_ld(soup)

    h1 = soup.find("h1")
    head = h1.find_parent("div") if h1 else None
    head_text = head.get_text(" ", strip=True) if head else soup.get_text(" ", strip=True)
    page_text = soup.get_text(" ", strip=True)

    title = ld.get("name") or (h1.get_text(" ", strip=True) if h1 else "Unknown")
    authors = [
        a.get("name", "").strip()
        for a in ld.get("author", [])
        if isinstance(a, dict) and a.get("name")
    ]

    author_links: list[str] = []
    for a in soup.select('a[href^="/author/"]'):
        name = a.get_text(" ", strip=True)
        if name and name not in author_links:
            author_links.append(name)
    artists = [n for n in author_links if n not in authors]

    genres = ld.get("genre") or [
        a.get_text(" ", strip=True) for a in soup.select('a[href^="/genre/"]')
    ]
    genres = [g for g in genres if g]

    tags: list[str] = []
    for a in soup.select('a[href^="/tag/"]'):
        name = a.get_text(" ", strip=True)
        if name and name not in tags:
            tags.append(name)

    prose = soup.select_one(".prose-text")
    description = (
        prose.get_text(" ", strip=True)
        if prose
        else ld.get("description", "")
    )

    return {
        "title": title,
        "alt_titles": ld.get("alternateName", []),
        "authors": authors,
        "artists": artists,
        "genres": genres,
        "tags": tags,
        "status": first_match(r"\b(Ongoing|Completed|Hiatus|Cancelled|Canceled|Upcoming|Dropped)\b", head_text),
        "type": first_match(r"\b(Manga|Manhwa|Manhua|Novel)\b", head_text),
        "year": first_match(r"\b((?:19|20)\d{2})\b", head_text),
        "score": first_match(r"([0-9]+(?:\.[0-9]+)?)\s*score", page_text),
        "popularity": first_match(r"#([0-9]+)\s*popularity", page_text),
        "saved": first_match(r"([0-9,]+)\s*saved", page_text),
        "comments": first_match(r"([0-9,]+)\s*comments", page_text),
        "cover": ld.get("image", ""),
        "start_date": ld.get("startDate", ""),
        "content_rating": ld.get("contentRating", ""),
        "description": description,
        "groups": len(groups),
        "variants": sum(len(g.get("variants", [])) for g in groups),
    }


def signed_json(session: requests.Session, path: str) -> dict:
    """GET an /api/ reader route with the site's HMAC headers."""
    stamp = str(int(time.time() * 1000))
    digest = hmac.new(
        SIGN_KEY,
        f"{path} {stamp}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    response = session.get(
        BASE + path,
        headers={"x-yf-t": stamp, "x-yf-s": signature, "Accept": "application/json"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def unseal(blob: str) -> dict:
    """AES-256-GCM: 16-byte salt, 12-byte IV, ciphertext+tag."""
    raw = base64.urlsafe_b64decode(blob + "=" * (-len(blob) % 4))
    salt, iv, ciphertext = raw[:16], raw[16:28], raw[28:]
    key = hashlib.sha256(SEAL_KEY + salt).digest()
    plaintext = AESGCM(key).decrypt(iv, ciphertext, None)
    return json.loads(plaintext.decode("utf-8"))


def extension_for(content_type: str | None) -> str:
    value = (content_type or "").split(";", 1)[0].strip().lower()
    return {
        "image/avif": ".avif",
        "image/webp": ".webp",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
    }.get(value, ".bin")


def print_metadata(meta: dict) -> None:
    print("\n=== MANGA INFO ===")
    print(f"Title           : {meta['title']}")
    if meta["alt_titles"]:
        print(f"Alternate titles: {', '.join(meta['alt_titles'])}")
    print(f"Type            : {meta['type'] or 'unknown'}")
    print(f"Year            : {meta['year'] or 'unknown'}")
    print(f"Status          : {meta['status'] or 'unknown'}")
    print(f"Content rating  : {meta['content_rating'] or 'unknown'}")
    print(f"Score           : {meta['score'] or 'unknown'}")
    print(f"Popularity      : {('#' + meta['popularity']) if meta['popularity'] else 'unknown'}")
    print(f"Saved           : {meta['saved'] or 'unknown'}")
    print(f"Comments        : {meta['comments'] or 'unknown'}")
    print(f"Story by        : {', '.join(meta['authors']) or 'unknown'}")
    print(f"Art by          : {', '.join(meta['artists']) or 'unknown'}")
    print(f"Genres          : {', '.join(meta['genres']) or 'unknown'}")
    print(f"Tags            : {', '.join(meta['tags']) or 'unknown'}")
    print(f"Start date      : {meta['start_date'] or 'unknown'}")
    print(f"Cover           : {meta['cover'] or 'unknown'}")
    print(f"Chapters        : {meta['groups']} logical groups, {meta['variants']} versions")
    print(f"Description     : {meta['description'] or 'unknown'}")


def print_chapters(groups: list[dict], sources: dict) -> None:
    print(f"\n=== CHAPTERS ({len(groups)}) ===")
    print(f"{'#':>3}  {'Label':<42} {'Date':<10} {'Pages':>5} {'Size':>9}  {'Source':<14} Versions")
    for i, group in enumerate(groups, 1):
        variants = group.get("variants") or []
        first = variants[0] if variants else {}
        source_id = str(first.get("s", ""))
        source = sources.get(source_id, source_id or "?")
        label = group.get("label", "?")
        extra = " [extra]" if group.get("extra") else ""
        print(
            f"{i:>3}  {label:<42} {human_date(group.get('createdAt')):<10} "
            f"{first.get('nPages', '?'):>5} {human_bytes(first.get('b')):>9}  "
            f"{source:<14} {len(variants)}{extra}"
        )


def download_pages(
    pages: list[dict],
    hashes: list[str],
    out_dir: Path,
) -> None:
    if len(pages) != len(hashes):
        raise ValueError(f"page/hash mismatch: {len(pages)} pages, {len(hashes)} hashes")

    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(hashes)
    print(f"\nDownloading {total} pages to {out_dir}")

    def one(index: int) -> tuple[int, str, int]:
        url = f"{BASE}/i/p/{hashes[index]}"
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = requests.get(
                    url,
                    headers={"User-Agent": UA, "Accept": "*/*"},
                    timeout=TIMEOUT,
                )
                response.raise_for_status()
                suffix = extension_for(response.headers.get("Content-Type"))
                path = out_dir / f"{index + 1:03d}{suffix}"
                path.write_bytes(response.content)
                return index, path.name, len(response.content)
            except Exception as exc:  # network, 404, write error
                last_error = exc
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"page {index + 1} failed: {last_error}")

    total_bytes = 0
    with ThreadPoolExecutor(max_workers=IMAGE_WORKERS) as pool:
        futures = {pool.submit(one, i): i for i in range(total)}
        for done, future in enumerate(as_completed(futures), 1):
            index, name, size = future.result()
            total_bytes += size
            print(f"  [{done:>3}/{total}] page {index + 1:>3} -> {name} ({human_bytes(size)})")

    print(f"Done: {total} pages, {human_bytes(total_bytes)}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    raw_url = input("Manga URL: ").strip()
    if not raw_url:
        print("No URL supplied.")
        return 1
    if not raw_url.startswith(("http://", "https://")):
        raw_url = "https://" + raw_url

    parsed = urlparse(raw_url)
    if parsed.netloc not in {"yaoi.me", "www.yaoi.me"}:
        print("Expected a yaoi.me URL.")
        return 1
    if not parsed.path.startswith("/series/"):
        print("Expected a /series/... URL.")
        return 1

    session = make_session()
    print(f"Fetching {raw_url} ...")
    response = session.get(raw_url, timeout=TIMEOUT)
    response.raise_for_status()
    html = response.text

    groups = extract_groups(html)
    meta = series_metadata(html, groups)

    latest_group = next((g for g in groups if g.get("variants")), None)
    if not latest_group:
        print("No chapter variants found.")
        return 1
    latest_variant = latest_group["variants"][0]
    source_id = latest_variant["s"]
    chapter_id = latest_variant["id"]

    print(f"Fetching latest chapter {latest_group.get('label')} ...")
    api_path = f"/api/reader/chapter?s={source_id}&c={chapter_id}"
    try:
        chapter_json = signed_json(session, api_path)
    except requests.HTTPError as exc:
        print(f"Reader API failed: {exc}")
        if exc.response is not None:
            print(f"Response: {exc.response.text[:300]}")
        print("The signing constants may have changed after a site redeploy.")
        return 1

    chapter = chapter_json["chapter"]
    sources = {str(k): str(v) for k, v in (chapter.get("sources") or {}).items()}
    sealed = chapter.get("sealed")
    if not sealed:
        print("This chapter has no sealed page payload.")
        return 1

    secret = unseal(sealed)
    hashes = secret.get("p") or []

    print_metadata(meta)
    print_chapters(groups, sources)

    print("\n=== LATEST CHAPTER ===")
    print(f"Title       : {chapter.get('title')}")
    print(f"Label       : {chapter.get('label')}")
    print(f"Chapter ID  : {chapter.get('id')}")
    print(f"Source      : {chapter.get('source')} (s={chapter.get('sourceSeriesId')})")
    print(f"Rank        : {chapter.get('rank')}")
    print(f"Pages       : {len(chapter.get('pages', []))}")
    print(f"Size        : {human_bytes(chapter.get('bytes'))}")
    print(f"Added       : {human_date(chapter.get('createdAt'))}")
    print(f"URL         : {BASE}{chapter.get('href', '')}")
    print(f"Alternates  : {len(chapter.get('alternates', []))}")

    out_dir = (
        Path("downloads")
        / safe_name(meta["title"])
        / f"{safe_name(str(chapter.get('label', 'chapter')), 40)}_{chapter.get('id')}"
    )
    download_pages(list(chapter.get("pages", [])), hashes, out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
