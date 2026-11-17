"""Maintenance for the hishel SQLite HTTP cache.

Hishel expires entries on *reads* and reclaims rows lazily when a new response
is stored, but SQLite never shrinks the database file when rows are deleted:
freed pages stay allocated. Over time the cache file can grow to several times
the size of its live payload. This module bounds the physical file by deleting
expired rows, evicting the oldest rows when a size limit is given, and running
``VACUUM`` to return the freed pages to the filesystem.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from tdoc_crawler.logging import get_logger

#: Grace period hishel keeps an expired row around so in-flight readers finish.
#: Mirrors hishel 2.x ``SqliteStorage(soft_delete_ttl=...)`` default.
SOFT_DELETE_TTL = 180.0
#: Rows removed per eviction batch, so pruning stays bounded.
EVICTION_BATCH_SIZE = 100
#: Max eviction batches per prune call.
EVICTION_MAX_BATCHES = 50

logger = get_logger(__name__)


@dataclass(frozen=True)
class HttpCacheStats:
    """Outcome of a cache prune (sizes are physical file bytes)."""

    entries_before: int
    entries_after: int
    expired_removed: int
    evicted: int
    bytes_before: int
    bytes_after: int
    vacuumed: bool

    @property
    def reclaimed_bytes(self) -> int:
        return max(0, self.bytes_before - self.bytes_after)


def prune_http_cache(cache_file: str | Path, *, max_bytes: int | None = None, now: float | None = None) -> HttpCacheStats:
    """Remove expired entries, optionally evict to *max_bytes*, and vacuum.

    Safe to call at any time: a missing or uninitialised database is a no-op,
    and a concurrent writer that holds a lock only prevents the ``VACUUM``
    (logged at debug level) — row deletions still succeed.

    Args:
        cache_file: Path to the hishel SQLite cache database.
        max_bytes: When set, evict the least-recently-used entries until the
            live database size is at or below this many bytes.
        now: Overridable clock for deterministic tests.

    Returns:
        :class:`HttpCacheStats` describing what was reclaimed.
    """
    path = Path(cache_file)
    empty = HttpCacheStats(0, 0, 0, 0, 0, 0, False)
    if not path.exists():
        return empty

    now = time.time() if now is None else now
    connection = sqlite3.connect(str(path), timeout=5)
    connection.execute("PRAGMA busy_timeout=5000")
    # Cascading deletes of stream chunks depend on foreign keys being enabled,
    # the same way hishel's own connection does.
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "entries" not in tables:
            return empty

        bytes_before = path.stat().st_size
        entries_before = int(connection.execute("SELECT COUNT(*) FROM entries").fetchone()[0])

        expired = connection.execute(
            "DELETE FROM entries WHERE expires_at < ? AND last_accessed_at < ?",
            (now, now - SOFT_DELETE_TTL),
        )
        expired_removed = max(0, expired.rowcount)
        connection.commit()

        evicted = 0
        if max_bytes is not None and _live_size(connection) > max_bytes:
            for _ in range(EVICTION_MAX_BATCHES):
                if _live_size(connection) <= max_bytes:
                    break
                batch = connection.execute(
                    "DELETE FROM entries WHERE id IN ( SELECT id FROM entries ORDER BY last_accessed_at LIMIT ?)",
                    (EVICTION_BATCH_SIZE,),
                )
                deleted = max(0, batch.rowcount)
                connection.commit()
                evicted += deleted
                if deleted == 0:
                    break

        vacuumed = True
        try:
            connection.execute("VACUUM")
        except sqlite3.Error:
            vacuumed = False
            logger.debug("Could not vacuum HTTP cache %s (a writer may hold a lock)", path)

        entries_after = int(connection.execute("SELECT COUNT(*) FROM entries").fetchone()[0])
        bytes_after = path.stat().st_size
        return HttpCacheStats(
            entries_before=entries_before,
            entries_after=entries_after,
            expired_removed=expired_removed,
            evicted=evicted,
            bytes_before=bytes_before,
            bytes_after=bytes_after,
            vacuumed=vacuumed,
        )
    finally:
        connection.close()


def _live_size(connection: sqlite3.Connection) -> int:
    """Non-free page bytes, matching hishel's own ``max_size`` accounting."""
    row = connection.execute(
        "SELECT (page_count - freelist_count) * page_size FROM pragma_page_count(), pragma_freelist_count(), pragma_page_size()"
    ).fetchone()
    return int(row[0]) if row is not None else 0


__all__ = ["HttpCacheStats", "prune_http_cache"]
