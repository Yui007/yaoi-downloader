"""HTTP session, retry budget, and the only place that writes bytes to disk."""

from __future__ import annotations

import hashlib
import json
import os
import random
import threading
import time
from pathlib import Path
from typing import Any

import requests

from .errors import Cancelled, NetworkError

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}
IMAGE_TYPES = {
    "image/avif": ".avif",
    "image/webp": ".webp",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
}


def extension_for(content_type: str | None) -> str:
    value = (content_type or "").split(";", 1)[0].strip().lower()
    return IMAGE_TYPES.get(value, ".bin")


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    with part.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(part, path)


def cache_key(*parts: str | int) -> str:
    return hashlib.sha1("|".join(str(part) for part in parts).encode()).hexdigest()


def sleep_cancellable(seconds: float, cancel: threading.Event | None) -> None:
    end = time.monotonic() + seconds
    while True:
        if cancel is not None and cancel.is_set():
            raise Cancelled("Cancelled.")
        left = end - time.monotonic()
        if left <= 0:
            return
        time.sleep(min(0.1, left))


class HttpClient:
    def __init__(
        self,
        timeout: int = 40,
        retries: int = 3,
        cache_dir: Path | None = None,
        cancel: threading.Event | None = None,
    ):
        self.timeout = max(5, int(timeout))
        self.retries = max(0, int(retries))
        self.cache_dir = cache_dir
        self.cancel = cancel
        self._local = threading.local()
        self._sessions: list[requests.Session] = []
        self._lock = threading.Lock()

    @property
    def session(self) -> requests.Session:
        session = getattr(self._local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
            self._local.session = session
            with self._lock:
                self._sessions.append(session)
        return session

    def close(self) -> None:
        with self._lock:
            sessions, self._sessions = self._sessions, []
        for session in sessions:
            session.close()

    def _check(self) -> None:
        if self.cancel is not None and self.cancel.is_set():
            raise Cancelled("Cancelled.")

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        retry: bool = True,
        image: bool = False,
        raise_on_status: bool = True,
    ) -> requests.Response:
        attempts = self.retries + 1 if retry else 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            self._check()
            try:
                response = self.session.get(url, headers=headers, timeout=self.timeout)
                if response.status_code in RETRY_STATUS and attempt + 1 < attempts:
                    delay = self._delay(attempt, response.headers.get("Retry-After"))
                    sleep_cancellable(delay, self.cancel)
                    continue
                if not raise_on_status:
                    return response
                response.raise_for_status()
                if image and "text/html" in response.headers.get("Content-Type", ""):
                    raise NetworkError("The image server returned a web page.")
                return response
            except requests.HTTPError as exc:
                last_error = exc
                status = exc.response.status_code if exc.response is not None else 0
                if status in RETRY_STATUS and attempt + 1 < attempts:
                    sleep_cancellable(self._delay(attempt), self.cancel)
                    continue
                raise NetworkError(f"HTTP {status or 'error'}: {url}") from exc
            except (requests.RequestException, NetworkError) as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    sleep_cancellable(self._delay(attempt), self.cancel)
                    continue
        raise NetworkError(f"Request failed after {attempts} tries: {url} ({last_error})")

    def _delay(self, attempt: int, retry_after: str | None = None) -> float:
        if retry_after:
            try:
                return min(60.0, max(0.0, float(retry_after)))
            except ValueError:
                pass
        return min(20.0, 1.5 * 2**attempt) * random.uniform(0.5, 1.5)

    def get_text(self, url: str, headers: dict[str, str] | None = None) -> str:
        return self.get(url, headers=headers).text

    def get_json(self, url: str, headers: dict[str, str] | None = None) -> Any:
        response = self.get(url, headers=headers)
        try:
            return response.json()
        except ValueError as exc:
            raise NetworkError(f"Expected JSON from {url}.") from exc

    def get_bytes(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        ttl: int = 0,
        key: str | None = None,
    ) -> bytes:
        """Bytes with an optional disk cache. Used for covers and exports."""
        if self.cache_dir and key and ttl:
            path = self.cache_dir / f"{cache_key(key)}.bin"
            if path.exists() and time.time() - path.stat().st_mtime < ttl:
                try:
                    return path.read_bytes()
                except OSError:
                    pass
        response = self.get(url, headers=headers, image=True)
        data = response.content
        if self.cache_dir and key and ttl:
            try:
                atomic_write(self.cache_dir / f"{cache_key(key)}.bin", data)
            except OSError:
                pass
        return data

    def fetch_image(self, url: str, folder: Path, index: int) -> tuple[Path, int, str]:
        response = self.get(url, headers={"Accept": "*/*"}, image=True)
        ext = extension_for(response.headers.get("Content-Type"))
        if ext == ".bin":
            raise NetworkError(f"Not an image: {url}")
        path = folder / f"{index:03d}{ext}"
        atomic_write(path, response.content)
        for old in folder.glob(f"{index:03d}.*"):
            if old != path and old.suffix != ".part":
                try:
                    old.unlink()
                except OSError:
                    pass
        return path, len(response.content), ext

    def cached_json(self, key: str, ttl: int, loader) -> Any:
        if not self.cache_dir:
            return loader()
        path = self.cache_dir / f"{cache_key(key)}.json"
        if path.exists():
            age = time.time() - path.stat().st_mtime
            if ttl <= 0 or age < ttl:
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    path.unlink(missing_ok=True)
        value = loader()
        try:
            atomic_write(path, json.dumps(value).encode("utf-8"))
        except OSError:
            pass
        return value

    def clear_listings(self) -> int:
        if not self.cache_dir or not self.cache_dir.exists():
            return 0
        removed = 0
        for path in self.cache_dir.glob("*.json"):
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
        return removed
