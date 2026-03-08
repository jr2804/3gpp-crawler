"""HTTP client with hishel caching for TEDDI requests."""

import logging
from pathlib import Path

import httpx
from hishel import AsyncSqliteStorage
from hishel.httpx import AsyncCacheClient

logger = logging.getLogger(__name__)


async def create_cached_teddi_async_client(
    cache_dir: Path | None = None,
    cache_ttl: int = 7200,
    refresh_ttl_on_access: bool = True,
) -> httpx.AsyncClient:
    """Create an async httpx.AsyncClient with hishel caching for TEDDI requests.

    Args:
        cache_dir: Directory for cache SQLite database. Defaults to `.cache/`.
        cache_ttl: Cache TTL in seconds. Defaults to 2 hours (7200 seconds).
        refresh_ttl_on_access: If True, extends TTL on cache hits. Defaults to True.

    Returns:
        httpx.AsyncClient configured with hishel caching.
    """
    if cache_dir is None:
        cache_dir = Path.cwd() / ".cache"

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "teddi_http.sqlite3"

    logger.debug(f"HTTP cache (async): {cache_file}")

    # Create storage backend
    storage = AsyncSqliteStorage(
        database_path=str(cache_file),
        default_ttl=cache_ttl,
        refresh_ttl_on_access=refresh_ttl_on_access,
    )

    # Create httpx async client with hishel caching
    client = AsyncCacheClient(
        storage=storage,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        },
        timeout=30.0,
    )

    return client
