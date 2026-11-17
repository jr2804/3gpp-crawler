"""Unit tests for the HTTP cache maintenance/prune helper."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from tdoc_crawler.http_client import HttpCacheStats, prune_http_cache


def test_prune_missing_file_is_noop(tmp_path: Path) -> None:
    stats = prune_http_cache(tmp_path / "missing.sqlite3")
    assert stats == HttpCacheStats(0, 0, 0, 0, 0, 0, False)
    assert stats.reclaimed_bytes == 0


def test_prune_empty_file_is_noop(tmp_path: Path) -> None:
    path = tmp_path / "empty.sqlite3"
    path.touch()
    stats = prune_http_cache(path)
    assert stats.entries_before == 0
    assert stats.vacuumed is False  # no schema: nothing to vacuum


def test_prune_removes_expired_entries_and_streams(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite3"
    _make_cache(path, expired=3, fresh=2)
    stats = prune_http_cache(path)
    assert stats.entries_before == 5
    assert stats.expired_removed == 3
    assert stats.entries_after == 2

    connection = sqlite3.connect(str(path))
    assert connection.execute("SELECT COUNT(*) FROM entries").fetchone()[0] == 2
    assert connection.execute("SELECT COUNT(*) FROM streams").fetchone()[0] == 2
    connection.close()


def test_prune_respects_soft_delete_ttl(tmp_path: Path) -> None:
    """An entry expired only seconds ago stays until the grace period elapses."""
    path = tmp_path / "cache.sqlite3"
    connection = sqlite3.connect(str(path))
    connection.execute(
        "CREATE TABLE entries (id BLOB PRIMARY KEY, cache_key BLOB, data BLOB, expires_at REAL, last_accessed_at REAL NOT NULL, chunk_count INTEGER, ttl_deadline REAL, tti REAL)"
    )
    now = time.time()
    connection.execute("INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (b"recent", b"k", b"d", now - 10, now, 1, None, None))
    connection.commit()
    connection.close()

    stats = prune_http_cache(path, now=now)
    assert stats.expired_removed == 0
    assert stats.entries_after == 1


def test_prune_evicts_to_max_bytes(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite3"
    _make_cache(path, fresh=6, payload=b"x" * 4096)
    before = path.stat().st_size
    # A tiny cap forces eviction of every entry.
    stats = prune_http_cache(path, max_bytes=1)
    assert stats.evicted == 6
    assert stats.entries_after == 0
    assert stats.bytes_before == before
    assert stats.bytes_after < before
    assert stats.reclaimed_bytes > 0
    assert stats.vacuumed is True


def test_prune_max_bytes_none_skips_eviction(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite3"
    _make_cache(path, fresh=3)
    stats = prune_http_cache(path, max_bytes=None)
    assert stats.evicted == 0
    assert stats.entries_after == 3


def test_prune_reports_reclaimed_bytes(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite3"
    _make_cache(path, expired=4, payload=b"y" * 8192)
    before = path.stat().st_size
    stats = prune_http_cache(path)
    assert stats.bytes_before == before
    assert stats.bytes_after < before
    assert stats.reclaimed_bytes == before - stats.bytes_after


def _make_cache(path: Path, *, expired: int = 0, fresh: int = 0, payload: bytes = b"x" * 2048) -> list[bytes]:
    """Create a hishel-shaped cache DB with ``expired`` + ``fresh`` entries.

    Returns the list of entry ids (as bytes) in insertion order.
    """
    connection = sqlite3.connect(str(path))
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        "CREATE TABLE entries (id BLOB PRIMARY KEY, cache_key BLOB NOT NULL, data BLOB NOT NULL,"
        " expires_at REAL, last_accessed_at REAL NOT NULL, chunk_count INTEGER,"
        " ttl_deadline REAL, tti REAL)"
    )
    connection.execute(
        "CREATE TABLE streams (entry_id BLOB NOT NULL, chunk_number INTEGER NOT NULL,"
        " chunk_data BLOB NOT NULL, PRIMARY KEY (entry_id, chunk_number),"
        " FOREIGN KEY (entry_id) REFERENCES entries(id) ON DELETE CASCADE)"
    )
    now = time.time()
    ids: list[bytes] = []
    for i in range(expired + fresh):
        entry_id = f"entry-{i}".encode()
        ids.append(entry_id)
        is_expired = i < expired
        expires_at = (now - 1000.0) if is_expired else (now + 1000.0)
        connection.execute(
            "INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (entry_id, f"key-{i}".encode(), b"data", expires_at, now - 500.0, 1, None, None),
        )
        connection.execute("INSERT INTO streams VALUES (?, 0, ?)", (entry_id, payload))
    connection.commit()
    connection.close()
    return ids
