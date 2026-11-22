"""Runtime cache. Empty CACHE_STORE_URL disables it.

Local development may use ``memory://`` or ``sqlite:///path``. Vercel must leave
the URL empty or point it at an external store. This module never writes a
cache file unless the URL says to.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Protocol

PLACES_TTL_SECONDS = 30 * 24 * 3600
ROUTES_TTL_SECONDS = 7 * 24 * 3600
WEATHER_TTL_SECONDS = 3 * 3600


def cache_key(namespace: str, payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return f"{namespace}:{digest}"


class Cache(Protocol):
    persistent: bool

    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str, ttl_seconds: int) -> None: ...


class NullCache:
    """No reads and no writes. Used when CACHE_STORE_URL is empty."""

    persistent = False

    def get(self, key: str) -> str | None:
        _ = key
        return None

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        _ = (key, value, ttl_seconds)


class MemoryCache:
    """Process-local store for tests and a single local run."""

    persistent = True

    def __init__(self, clock=time.time) -> None:
        self._clock = clock
        self._rows: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            row = self._rows.get(key)
            if row is None:
                return None
            value, expires = row
            if expires <= self._clock():
                self._rows.pop(key, None)
                return None
            return value

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        expires = self._clock() + ttl_seconds
        with self._lock:
            self._rows[key] = (value, expires)


class SqliteCache:
    """Local SQLite cache. Do not point this at the Vercel filesystem."""

    persistent = True

    def __init__(self, path: Path, clock=time.time) -> None:
        self.path = path
        self._clock = clock
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def get(self, key: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            value, expires = row
            if float(expires) <= self._clock():
                self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                self._conn.commit()
                return None
            return str(value)

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        expires = self._clock() + ttl_seconds
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO cache (key, value, expires_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    expires_at = excluded.expires_at
                """,
                (key, value, expires),
            )
            self._conn.commit()


def open_cache(url: str) -> Cache:
    text = url.strip()
    if not text:
        return NullCache()
    if text == "memory://":
        return MemoryCache()
    if text.startswith("sqlite:"):
        return SqliteCache(_sqlite_path(text[len("sqlite:") :]))
    scheme = text.split(":", 1)[0]
    raise ValueError(
        f"Unsupported CACHE_STORE_URL scheme '{scheme}'. "
        "Leave it empty, or use memory:// or sqlite:///path for local development."
    )


def _sqlite_path(rest: str) -> Path:
    path = rest
    if path.startswith("///"):
        path = path[3:]
    elif path.startswith("//"):
        path = path[2:]
    return Path(path)
