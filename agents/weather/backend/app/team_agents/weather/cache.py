from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


class WeatherCache:
    """Small SQLite cache. The key is a hash; requested coordinates are never stored."""

    def __init__(self, path: str | Path | None = None) -> None:
        configured = path or os.getenv("WEATHER_CACHE_PATH")
        self.path = (
            Path(configured).expanduser() if configured else Path.home() / ".cache" / "kisanos" / "weather.sqlite3"
        )

    @staticmethod
    def key(latitude: float, longitude: float, endpoint: str) -> str:
        # Round to a coarse ~0.1 degree cell before hashing; never persist field-level
        # GPS precision in either the cache key or the cached provider payload.
        canonical = f"{endpoint}|{latitude:.1f}|{longitude:.1f}".encode()
        return hashlib.sha256(canonical).hexdigest()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            self.path.parent.chmod(0o700)
        except OSError:
            pass
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS weather_cache (
                cache_key TEXT PRIMARY KEY,
                fetched_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )"""
        )
        connection.commit()
        try:
            self.path.chmod(0o600)
        except OSError:
            pass
        return connection

    def put(self, key: str, payload: dict[str, Any], fetched_at: datetime | None = None) -> None:
        fetched = (fetched_at or datetime.now(UTC)).astimezone(UTC).isoformat()
        encoded = json.dumps(payload, separators=(",", ":"), allow_nan=False)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO weather_cache(cache_key, fetched_at, payload_json) VALUES (?, ?, ?) "
                "ON CONFLICT(cache_key) DO UPDATE SET fetched_at=excluded.fetched_at, payload_json=excluded.payload_json",
                (key, fetched, encoded),
            )
            # Retain only a bounded set of recent cells; never accumulate every coordinate queried.
            cutoff = (datetime.now(UTC) - timedelta(days=8)).isoformat()
            connection.execute("DELETE FROM weather_cache WHERE fetched_at < ?", (cutoff,))
            connection.execute(
                "DELETE FROM weather_cache WHERE cache_key NOT IN "
                "(SELECT cache_key FROM weather_cache ORDER BY fetched_at DESC LIMIT 256)"
            )
            connection.commit()

    def get(self, key: str) -> tuple[dict[str, Any], datetime] | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT fetched_at, payload_json FROM weather_cache WHERE cache_key = ?",
                    (key,),
                ).fetchone()
            if row is None:
                return None
            fetched_at = datetime.fromisoformat(row[0]).astimezone(UTC)
            payload = json.loads(row[1])
            if not isinstance(payload, dict):
                return None
            return payload, fetched_at
        except (OSError, sqlite3.Error, ValueError, TypeError, json.JSONDecodeError):
            return None
