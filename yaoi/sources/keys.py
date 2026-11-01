"""Reader constants: recover, verify, cache, and sign requests."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..errors import AuthError, SealError
from ..http import HttpClient

BASE = "https://yaoi.me"
# Public constants from the reader bundle (module 50309); refresh when they move.
DEFAULT_SIGN = bytes.fromhex(
    "85cedf4fed3602c3a35c18010b502584"
    "dee9594708ba673052d562c7f2b1a9de"
)
DEFAULT_SEAL = bytes.fromhex(
    "10dd8dff9911000f9286d3dfd8b9f72b"
    "3f763c2f783f89f5c384cff4a11988ac"
)


def fingerprint(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()[:12]


def signed_headers(path: str, sign_key: bytes) -> dict[str, str]:
    stamp = str(int(time.time() * 1000))
    digest = hmac.new(sign_key, f"{path} {stamp}".encode("utf-8"), hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return {"x-yf-t": stamp, "x-yf-s": signature, "Accept": "application/json"}


def unseal(blob: str, seal_key: bytes) -> dict:
    raw = base64.urlsafe_b64decode(blob + "=" * (-len(blob) % 4))
    salt, iv, ciphertext = raw[:16], raw[16:28], raw[28:]
    key = hashlib.sha256(seal_key + salt).digest()
    try:
        plain = AESGCM(key).decrypt(iv, ciphertext, None)
        return json.loads(plain.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - any decrypt failure is a seal failure
        raise SealError("Could not unseal the chapter payload.") from exc


@dataclass(frozen=True)
class KeyInfo:
    sign: bytes
    seal: bytes
    verified_at: int = 0
    chapter_url: str = ""

    @property
    def sign_fp(self) -> str:
        return fingerprint(self.sign)

    @property
    def seal_fp(self) -> str:
        return fingerprint(self.seal)


class KeyStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> KeyInfo:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                sign = bytes.fromhex(data["sign"])
                seal = bytes.fromhex(data["seal"])
                if len(sign) == 32 and len(seal) == 32:
                    return KeyInfo(
                        sign=sign,
                        seal=seal,
                        verified_at=int(data.get("verified_at") or 0),
                        chapter_url=data.get("chapter_url", ""),
                    )
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                pass
        return KeyInfo(sign=DEFAULT_SIGN, seal=DEFAULT_SEAL)

    def save(self, info: KeyInfo) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        part = self.path.with_suffix(".json.part")
        part.write_text(
            json.dumps(
                {
                    "sign": info.sign.hex(),
                    "seal": info.seal.hex(),
                    "verified_at": info.verified_at,
                    "chapter_url": info.chapter_url,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        part.replace(self.path)


def _int_array(text: str) -> list[int]:
    values = [int(x) for x in re.findall(r"\d+", text)]
    if len(values) != 32:
        raise ValueError(f"expected 32 bytes, got {len(values)}")
    return values


def recover_from_js(js: str) -> tuple[bytes, bytes] | None:
    """Return (seal_key, sign_key) from one reader chunk, or None."""
    if "sealKey" not in js or "signKey" not in js:
        return None
    idx = js.find("sealKey")
    window = js[max(0, idx - 1800) : idx + 1800]
    mask_match = re.search(
        r"([A-Za-z_$][\w$]*)=\[([0-9,\s]+)\],\s*"
        r"[A-Za-z_$][\w$]*=e=>Uint8Array\.from\(e,\(e,a\)=>e\^\1\[a\]\)",
        window,
    )
    if not mask_match:
        return None
    mask = _int_array(mask_match.group(2))
    seal_match = re.search(
        r'["\']sealKey["\']\s*,\s*0\s*,\s*\(\)\s*=>\s*'
        r"[A-Za-z_$][\w$]*\s*\(\s*\[([0-9,\s]+)\]\s*\)",
        window,
    )
    if not seal_match:
        return None
    seal = bytes(a ^ b for a, b in zip(_int_array(seal_match.group(1)), mask))
    sign_ref = re.search(
        r'["\']signKey["\']\s*,\s*0\s*,\s*([A-Za-z_$][\w$]*)\s*\]',
        window,
    )
    if not sign_ref:
        return None
    sign_match = re.search(
        rf"\b{re.escape(sign_ref.group(1))}\s*=\s*\(\)\s*=>\s*"
        rf"[A-Za-z_$][\w$]*\s*\(\s*\[([0-9,\s]+)\]\s*\)",
        window,
    )
    if not sign_match:
        return None
    sign = bytes(a ^ b for a, b in zip(_int_array(sign_match.group(1)), mask))
    return seal, sign


def chapter_ids(url: str) -> tuple[int, int]:
    match = re.search(r"/chapter/(\d+)/(\d+)", url)
    if not match:
        raise AuthError("Could not read series/chapter IDs from the chapter URL.")
    return int(match.group(1)), int(match.group(2))


def _script_urls(html: str, page_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls = [urljoin(page_url, tag["src"]) for tag in soup.select("script[src]")]
    for match in re.findall(r"/_next/static/chunks/[A-Za-z0-9._-]+\.js", html):
        urls.append(urljoin(BASE, match))
    out: list[str] = []
    for item in urls:
        parsed = urlparse(item)
        if parsed.netloc in {"yaoi.me", "www.yaoi.me"} and item not in out:
            out.append(item)
    return out


def find_chapter_url(client: HttpClient, url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc not in {"yaoi.me", "www.yaoi.me"}:
        raise AuthError("Expected a yaoi.me URL.")
    if re.search(r"/chapter/\d+/\d+", parsed.path):
        return url
    html = client.get_text(url)
    soup = BeautifulSoup(html, "html.parser")
    links = [
        a.get("href", "")
        for a in soup.select('a[href^="/chapter/"]')
        if re.search(r"/chapter/\d+/\d+", a.get("href", ""))
    ]
    if not links:
        raise AuthError("No chapter link found on that page.")
    for anchor in soup.select('a[href^="/chapter/"]'):
        text = anchor.get_text(" ", strip=True).lower()
        if "latest" in text or "start reading" in text:
            return urljoin(BASE, anchor["href"])
    return urljoin(BASE, links[0])


def verify(client: HttpClient, chapter_url: str, seal_key: bytes, sign_key: bytes) -> str:
    series_id, chapter_id = chapter_ids(chapter_url)
    path = f"/api/reader/chapter?s={series_id}&c={chapter_id}"
    response = client.get(BASE + path, headers=signed_headers(path, sign_key))
    if response.status_code != 200:
        raise AuthError(f"Reader API returned {response.status_code}.")
    chapter = response.json().get("chapter") or {}
    sealed = chapter.get("sealed")
    if not sealed:
        raise SealError("Chapter has no sealed payload.")
    plain = unseal(sealed, seal_key)
    hashes = plain.get("p") or []
    pages = chapter.get("pages") or []
    if len(hashes) != len(pages) or not hashes:
        raise SealError(f"Decrypted {len(hashes)} hashes for {len(pages)} pages.")
    return f"{len(pages)} pages verified"


def refresh(client: HttpClient, store: KeyStore, url: str = BASE, save: bool = True) -> KeyInfo:
    chapter_url = find_chapter_url(client, url)
    html = client.get_text(chapter_url)
    tried = 0
    for script in _script_urls(html, chapter_url):
        tried += 1
        try:
            text = client.get_text(script)
            if "sealKey" not in text:
                continue
            candidate = recover_from_js(text)
            if not candidate:
                continue
            seal, sign = candidate
            verify(client, chapter_url, seal, sign)
            info = KeyInfo(sign=sign, seal=seal, verified_at=int(time.time()), chapter_url=chapter_url)
            if save:
                store.save(info)
            return info
        except Exception:  # noqa: BLE001 - candidate scripts can fail for many reasons
            continue
    raise AuthError(
        f"Could not recover verified keys from {tried} scripts. "
        "The reader bundle layout may have changed."
    )
