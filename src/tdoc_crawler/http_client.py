"""HTTP client factory with hishel caching support."""

from __future__ import annotations

import logging
from pathlib import Path

import requests
from hishel import SyncSqliteStorage
from hishel.requests import CacheAdapter
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


def download_to_path(url: str, destination: Path) -> None:
    """Download a file from URL to destination path.

    Args:
        url: Source URL
        destination: Destination path

    Raises:
        ValueError: If URL scheme is not supported
        FileNotFoundError: If download fails
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    lowered = url.lower()
    allowed_schemes = ("ftp://", "http://", "https://")
    if not lowered.startswith(allowed_schemes):
        raise ValueError("unsupported-url-scheme")

    # Use requests with browser-like headers to avoid 403 Forbidden
    session = requests.Session()
    session.headers.update(
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

    response = session.get(url, timeout=60, stream=True)
    response.raise_for_status()
    with destination.open("wb") as target:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                target.write(chunk)


def create_cached_session(
    cache_dir: Path,
    ttl: int = 7200,
    refresh_ttl_on_access: bool = True,
    max_retries: int = 3,
) -> requests.Session:
    """Create a requests.Session with hishel caching enabled.

    Args:
        cache_dir: Directory to store the cache database
        ttl: Time-to-live for cached responses in seconds (default: 7200)
        refresh_ttl_on_access: Whether to refresh TTL on cache access (default: True)
        max_retries: Number of retry attempts for failed requests (default: 3)

    Returns:
        Configured requests.Session with caching enabled
    """
    # Ensure cache directory exists
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Create cache database path
    cache_db_path = cache_dir / "http-cache.sqlite3"

    logger.debug(f"Creating cached HTTP session: cache_db={cache_db_path}, ttl={ttl}s, refresh_on_access={refresh_ttl_on_access}, max_retries={max_retries}")

    # Create SQLite storage backend
    storage = SyncSqliteStorage(
        database_path=str(cache_db_path),
        default_ttl=ttl,
        refresh_ttl_on_access=refresh_ttl_on_access,
    )

    # Configure retry strategy for the session
    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
    )

    # Create HTTP adapter with retry support
    HTTPAdapter(max_retries=retry_strategy)

    # Create cache adapter without specifying an adapter (hishel will handle it internally)
    cache_adapter = CacheAdapter(storage=storage)

    # Create session
    session = requests.Session()

    # Mount the cache adapter which handles both caching and delegates to the HTTP adapter for network requests
    session.mount("http://", cache_adapter)
    session.mount("https://", cache_adapter)

    return session


__all__ = ["create_cached_session"]
