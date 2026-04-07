"""HTTP client factory with hishel caching support."""

from __future__ import annotations

import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import niquests as requests
from hishel import SyncBaseStorage, SyncSqliteStorage
from hishel.requests import CacheAdapter
from niquests.adapters import HTTPAdapter
from truststore import SSLContext as TruststoreSSLContext
from urllib3.util.retry import Retry

from tdoc_crawler.config.settings import HttpConfig, PathConfig
from tdoc_crawler.constants.urls import BROWSER_HEADERS
from tdoc_crawler.logging import get_logger

logger = get_logger(__name__)


class SSLContextHTTPAdapter(HTTPAdapter):
    """HTTP adapter that can enforce a specific SSL context."""

    def __init__(self, *args: object, ssl_context: ssl.SSLContext | None = None, **kwargs: object) -> None:
        self._ssl_context = ssl_context
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, connections: int, maxsize: int, block: bool = False, **pool_kwargs: object) -> None:
        if self._ssl_context is not None:
            pool_kwargs["ssl_context"] = self._ssl_context
        super().init_poolmanager(connections=connections, maxsize=maxsize, block=block, **pool_kwargs)

    def proxy_manager_for(self, proxy: str, **proxy_kwargs: object) -> object:
        if self._ssl_context is not None:
            proxy_kwargs["ssl_context"] = self._ssl_context
        return super().proxy_manager_for(proxy, **proxy_kwargs)


class SSLContextCacheAdapter(CacheAdapter):
    """Cache adapter variant that can enforce a specific SSL context."""

    def __init__(self, *args: object, ssl_context: ssl.SSLContext | None = None, **kwargs: object) -> None:
        self._ssl_context = ssl_context
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, connections: int, maxsize: int, block: bool = False, **pool_kwargs: object) -> None:
        if self._ssl_context is not None:
            pool_kwargs["ssl_context"] = self._ssl_context
        super().init_poolmanager(connections=connections, maxsize=maxsize, block=block, **pool_kwargs)

    def proxy_manager_for(self, proxy: str, **proxy_kwargs: object) -> object:
        if self._ssl_context is not None:
            proxy_kwargs["ssl_context"] = self._ssl_context
        return super().proxy_manager_for(proxy, **proxy_kwargs)


@dataclass
class PoolConfig:
    """HTTP connection pool configuration.

    Attributes:
        max_connections: Maximum number of connection pools to cache
        max_per_host: Maximum number of connections per host
        connection_timeout: Connection timeout in seconds
        enable_retry: Whether to enable retry logic
        retry_attempts: Number of retry attempts for failed requests
    """

    max_connections: int = 10
    max_per_host: int = 5
    connection_timeout: float = 30.0
    enable_retry: bool = True
    retry_attempts: int = 3


def resolve_ssl_verify(
    verify: bool | str | None = None,
    http_config: HttpConfig | None = None,
) -> bool | str:
    """Resolve SSL verification behavior from explicit argument or HttpConfig.

    Resolution order:
    1. Explicit `verify` parameter
    2. http_config.verify_ssl if provided
    3. Default (True)

    Args:
        verify: Optional explicit SSL verification mode.
        http_config: Optional HttpConfig. When provided, verify_ssl is used as fallback.

    Returns:
        Either a boolean verification flag or a certificate bundle path.
    """
    if verify is not None:
        resolved = verify
    elif http_config is not None:
        resolved = http_config.verify_ssl
    else:
        resolved = True

    if resolved is False:
        logger.warning("SSL certificate verification is disabled. This is insecure.")

    return resolved


def _resolve_ssl_context(verify: bool | str) -> ssl.SSLContext | None:
    """Build SSL context for adapter-level TLS verification.

    Args:
        verify: Resolved SSL verification behavior.

    Returns:
        SSL context when adapter-level override is needed, otherwise None.
    """
    if verify is True:
        return TruststoreSSLContext(ssl.PROTOCOL_TLS_CLIENT)
    return None


def download_to_file(
    url: str,
    destination: Path,
    session: requests.Session | None = None,
    close_session: bool = True,
    http_cache_file: Path | None = None,
    http_cache_enabled: bool | None = None,
    pool_config: PoolConfig | None = None,
    verify: bool | str | None = None,
    http_config: HttpConfig | None = None,
) -> requests.Session | None:
    """Download a file from URL to destination path.

    Args:
        url: Source URL
        destination: Destination path
        session: Optional requests.Session to reuse. If None, a temporary cached session is created.
        close_session: Whether to close the session after download. Only applicable if a temporary session is created.
        http_cache_file: Optional explicit path to the HTTP cache database. Falls back to PathConfig default.
        http_cache_enabled: Whether to enable HTTP caching. If None, defaults to http_config.cache_enabled or True.
        pool_config: Optional connection pool configuration.
        verify: SSL certificate verification mode. Can be bool or CA bundle path.
        http_config: HttpConfig from ThreeGPPConfig. Controls caching, retries, SSL.

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
        temp_session = create_cached_session(
            http_cache_file=http_cache_file,
            http_cache_enabled=http_cache_enabled,
            pool_config=pool_config,
            verify=verify,
            http_config=http_config,
        )
        active_session = temp_session
    else:
        active_session = session

    try:
        timeout = pool_config.connection_timeout if pool_config is not None else 60
        response = active_session.get(url, timeout=timeout, stream=True)
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
    http_cache_file: Path | None = None,
    http_cache_enabled: bool | None = None,
    pool_config: PoolConfig | None = None,
    verify: bool | str | None = None,
    http_config: HttpConfig | None = None,
) -> requests.Session:
    """Create a requests.Session with hishel caching enabled.

    Args:
        http_cache_file: Optional explicit path to the HTTP cache database.
                         Falls back to PathConfig().http_cache_file when caching is enabled.
        http_cache_enabled: Whether to enable HTTP caching. If None, uses http_config.cache_enabled or True.
        pool_config: Optional connection pool configuration.
                When provided, pool settings are applied to the active adapter
                (cache adapter when caching is enabled, HTTPAdapter otherwise).
        verify: SSL certificate verification mode. Can be bool or CA bundle path.
        http_config: HttpConfig from ThreeGPPConfig. Controls caching TTL, retries, SSL.

    Returns:
        Configured requests.Session with caching enabled (unless disabled)
    """
    # Create session, use requests with browser-like headers to avoid 403 Forbidden
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)

    # Use http_config for SSL if no explicit verify provided
    verify_mode = http_config.verify_ssl if verify is None and http_config is not None else resolve_ssl_verify(verify, http_config)
    ssl_context = _resolve_ssl_context(verify_mode)
    session.verify = verify_mode

    # Resolve cache enabled flag: explicit param → http_config → default True
    if http_cache_enabled is None:
        http_cache_enabled = http_config.cache_enabled if http_config is not None else True

    # If caching is disabled, optionally configure a pooled HTTP adapter and return.
    if not http_cache_enabled:
        if pool_config is not None or ssl_context is not None:
            retry_attempts = pool_config.retry_attempts if pool_config and pool_config.enable_retry else 0
            retry_strategy = Retry(
                total=retry_attempts,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS"],
            )
            adapter = SSLContextHTTPAdapter(
                pool_connections=pool_config.max_connections if pool_config is not None else 10,
                pool_maxsize=pool_config.max_per_host if pool_config is not None else 10,
                max_retries=retry_strategy,
                ssl_context=ssl_context,
            )
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            if pool_config is not None:
                logger.debug(
                    f"Configured connection pool without caching: max_connections={pool_config.max_connections}, max_per_host={pool_config.max_per_host}"
                )

        logger.debug("Creating plain HTTP session (caching disabled)")
        return session

    # Resolve cache settings from http_config or defaults
    ttl = http_config.cache_ttl if http_config is not None else 7200
    refresh_ttl_on_access = http_config.cache_refresh_on_access if http_config is not None else True
    max_retries_count = http_config.max_retries if http_config is not None else 3

    # Determine cache file path — use explicit param or fall back to PathConfig default
    cache_file = str(http_cache_file) if http_cache_file is not None else str(PathConfig().http_cache_file)

    logger.debug(f"Creating cached HTTP session with cache_db={cache_file})")
    logger.debug(f"HTTP cache config: ttl={ttl}, refresh_ttl_on_access={refresh_ttl_on_access}, max_retries={max_retries_count}")

    # Create SQLite storage backend
    storage = SyncSqliteStorage(
        database_path=cache_file,
        default_ttl=ttl,
        refresh_ttl_on_access=refresh_ttl_on_access,
    )
    storage = cast(SyncBaseStorage, storage)

    # Configure retry strategy for the cache adapter.
    # If pool_config is set, reuse its retry settings so caching + pooling share one adapter.
    retry_attempts = pool_config.retry_attempts if pool_config and pool_config.enable_retry else max_retries_count
    max_retries = Retry(
        total=retry_attempts,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
    )

    # Create a single cache adapter with pool settings so both behaviors are active.
    cache_adapter = SSLContextCacheAdapter(
        pool_connections=pool_config.max_connections if pool_config is not None else 10,
        pool_maxsize=pool_config.max_per_host if pool_config is not None else 10,
        max_retries=max_retries,
        storage=storage,
        ssl_context=ssl_context,
    )

    # Mount the cache adapter
    session.mount("http://", cache_adapter)
    session.mount("https://", cache_adapter)

    if pool_config is not None:
        logger.debug(f"Configured cache + pool adapter: max_connections={pool_config.max_connections}, max_per_host={pool_config.max_per_host}")

    return session


__all__ = [
    "PoolConfig",
    "SSLContextCacheAdapter",
    "SSLContextHTTPAdapter",
    "create_cached_session",
    "download_to_file",
    "resolve_ssl_verify",
]
