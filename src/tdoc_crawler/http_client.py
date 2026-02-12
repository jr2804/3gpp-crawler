"""HTTP client factory with hishel caching support."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import requests
from hishel import SyncBaseStorage, SyncSqliteStorage
from hishel.requests import CacheAdapter
from urllib3.util.retry import Retry

from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models import HttpCacheConfig

logger = get_logger(__name__)


def download_to_file(
    url: str,
    destination: Path,
    session: requests.Session | None = None,
    close_session: bool = True,
    http_cache: HttpCacheConfig | None = None,
    cache_manager_name: str | None = None,
) -> requests.Session | None:
    """Download a file from URL to destination path.

    Args:
        url: Source URL
        destination: Destination path
        session: Optional requests.Session to reuse. If None, a temporary cached session is created.
        close_session: Whether to close the session after download. Only applicable if a temporary session is created.
        http_cache: Optional HTTP cache configuration
        cache_manager_name: Optional cache manager name to determine cache directory when creating a temporary session.

    Raises:
        ValueError: If URL scheme is not supported
        FileNotFoundError: If download fails
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    lowered = url.lower()
    allowed_schemes = ("ftp://", "http://", "https://")
    if not lowered.startswith(allowed_schemes):
        raise ValueError("unsupported-url-scheme")

    # Use provided session or create a new one (might be used for multiple downloads, so we don't want to create a new session for each)
    temp_session: requests.Session | None = None
    if session is None:
        temp_session = create_cached_session(http_cache=http_cache, cache_manager_name=cache_manager_name)
        active_session = temp_session
    else:
        active_session = session

    try:
        # Use requests with browser-like headers to avoid 403 Forbidden
        active_session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )

        response = active_session.get(url, timeout=60, stream=True)
        response.raise_for_status()
        with destination.open("wb") as target:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    target.write(chunk)

        # return session or None if we created a temporary session and are closing it
        if close_session:
            active_session = None
        return active_session

    finally:
        if temp_session and close_session:
            temp_session.close()


def create_cached_session(
    http_cache: HttpCacheConfig | None = None,
    cache_manager_name: str | None = None,
) -> requests.Session:
    """Create a requests.Session with hishel caching enabled.

    Args:
        http_cache: HTTP cache configuration
        cache_manager_name: Optional cache manager name to determine cache configuration.

    Returns:
        Configured requests.Session with caching enabled
    """
    manager = resolve_cache_manager(cache_manager_name)
    http_cache = http_cache or HttpCacheConfig.resolve_http_cache_config()
    logger.debug(f"Creating cached HTTP session with cache_db={manager.http_cache_file})")
    logger.debug(f"HTTP cache config: ttl={http_cache.ttl}, refresh_ttl_on_access={http_cache.refresh_ttl_on_access}, max_retries={http_cache.max_retries}")

    # Create SQLite storage backend (cache_dir is the database file path)
    storage = SyncSqliteStorage(
        database_path=str(manager.http_cache_file),
        default_ttl=http_cache.ttl,
        refresh_ttl_on_access=http_cache.refresh_ttl_on_access,
    )
    storage = cast(SyncBaseStorage, storage)

    # Configure retry strategy for the session
    max_retries = Retry(
        total=http_cache.max_retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
    )

    # Create cache adapter
    cache_adapter = CacheAdapter(storage=storage, max_retries=max_retries)  # ty:ignore[invalid-argument-type]

    # Create session
    session = requests.Session()

    # Mount the cache adapter
    session.mount("http://", cache_adapter)
    session.mount("https://", cache_adapter)

    return session


__all__ = ["create_cached_session"]
