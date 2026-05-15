"""HTTP client factory with hishel caching support."""

from __future__ import annotations

from dataclasses import dataclass
from gzip import decompress as gzip_decompress
from pathlib import Path
from typing import cast
from zlib import decompress as zlib_decompress

import brotli
import niquests as requests
from hishel import SyncBaseStorage, SyncSqliteStorage
from hishel._core._headers import Headers
from hishel._core.models import Request, Response
from hishel.requests import CacheAdapter, extract_metadata_from_headers, snake_to_header
from niquests.adapters import HTTPAdapter
from urllib3.response import HTTPResponse
from urllib3.util.retry import Retry

try:
    from urllib3.connection import HttpVersion
except ImportError:
    HttpVersion = None  # type: ignore[assignment,misc]

from tdoc_crawler.config.settings import HttpConfig, PathConfig
from tdoc_crawler.constants.urls import BROWSER_HEADERS
from tdoc_crawler.logging import get_logger

logger = get_logger(__name__)


def _niquests_to_internal_request(model: requests.models.PreparedRequest) -> Request:
    """Convert niquests prepared request into hishel internal request model."""
    body: bytes
    if isinstance(model.body, str):
        body = model.body.encode("utf-8")
    elif isinstance(model.body, bytes):
        body = model.body
    else:
        body = b""

    if model.method is None:
        msg = "prepared request method must not be None"
        raise ValueError(msg)

    return Request(
        method=model.method,
        url=str(model.url),
        headers=Headers(model.headers),
        stream=iter([body]),
        metadata=extract_metadata_from_headers(model.headers),
    )


def _decompress_body(body: bytes, content_encoding: str) -> bytes:
    encoding = content_encoding.lower().strip()
    if encoding == "br":
        return brotli.decompress(body)
    if encoding == "gzip":
        return gzip_decompress(body)
    if encoding == "deflate":
        return zlib_decompress(body)
    return body


def _internal_to_niquests_response(model: Response) -> requests.models.Response:
    response = requests.models.Response()

    raw_body = b"".join(model.stream) if model.stream is not None else b""
    metadata_headers = {snake_to_header(key): str(value) for key, value in model.metadata.items()}
    merged_headers = {**model.headers, **metadata_headers}

    content_encoding = merged_headers.get("content-encoding", "")
    body = _decompress_body(raw_body, content_encoding) if content_encoding else raw_body

    response.raw = HTTPResponse(
        body=raw_body,
        headers=merged_headers,
        status=model.status_code,
        preload_content=False,
        decode_content=False,
    )
    response.status_code = model.status_code
    response.headers.update(model.headers)
    response.headers.update(metadata_headers)
    response._content = body
    response._content_consumed = True
    response.url = ""

    return response


class _NiquetsCacheAdapter(CacheAdapter):
    """Bridges niquests PreparedRequest to hishel CacheAdapter.

    niquests.PreparedRequest does not inherit requests.PreparedRequest,
    so hishel's isinstance checks would fail without this bridge.
    """

    def init_poolmanager(self, connections: int, maxsize: int, block: bool = False, **pool_kwargs: object) -> None:
        """Disable HTTP/3 to prevent MustDowngradeError from 3GPP servers."""
        if HttpVersion is not None:
            disabled: set[HttpVersion] = pool_kwargs.get("disabled_svn", set())  # type: ignore[assignment]
            if not isinstance(disabled, set):
                disabled = set()
            disabled.add(HttpVersion.h3)
            pool_kwargs["disabled_svn"] = disabled  # type: ignore[assignment]
        super().init_poolmanager(connections, maxsize, block, **pool_kwargs)

    def send(
        self,
        request: requests.models.PreparedRequest,
        **_kwargs: object,
    ) -> requests.models.Response:
        """Bridge niquests request/response objects to hishel cache internals."""
        internal_request = _niquests_to_internal_request(request)
        internal_response = self._cache_proxy.handle_request(internal_request)
        response = _internal_to_niquests_response(internal_response)
        response.request = request
        response.connection = self  # type: ignore[assignment]
        return response


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


def download_to_file(
    url: str,
    target_file: Path,
    session: requests.Session | None = None,
    http_cache_file: Path | None = None,
    http_cache_enabled: bool | None = None,
    pool_config: PoolConfig | None = None,
    verify: bool | str | None = None,
    http_config: HttpConfig | None = None,
) -> None:
    """Download a file from URL to destination path.

    Args:
        url: Source URL
        target_file: Destination file path
        session: Optional requests.Session to reuse. If None, a temporary cached session is created and closed.
        http_cache_file: Optional explicit path to the HTTP cache database. Falls back to PathConfig default.
        http_cache_enabled: Whether to enable HTTP caching. If None, defaults to http_config.cache_enabled or True.
        pool_config: Optional connection pool configuration.
        verify: SSL certificate verification mode. Can be bool or CA bundle path.
        http_config: HttpConfig from ThreeGPPConfig. Controls caching, retries, SSL.

    Raises:
        ValueError: If URL scheme is not supported
        FileNotFoundError: If download fails
    """
    target_file.parent.mkdir(parents=True, exist_ok=True)
    lowered = url.lower()
    allowed_schemes = ("ftp://", "http://", "https://")
    if not lowered.startswith(allowed_schemes):
        msg = "unsupported-url-scheme"
        raise ValueError(msg)

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
        with target_file.open("wb") as target:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    target.write(chunk)

    finally:
        if temp_session:
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
    # Disable HTTP/3 to avoid MustDowngradeError with servers advertising Alt-Svc: h3
    session = requests.Session(disable_http3=True)
    session.headers.update(BROWSER_HEADERS)

    # Use http_config for SSL if no explicit verify provided
    verify_mode = http_config.verify_ssl if verify is None and http_config is not None else resolve_ssl_verify(verify, http_config)
    session.verify = verify_mode

    # Resolve cache enabled flag: explicit param → http_config → default True
    if http_cache_enabled is None:
        http_cache_enabled = http_config.cache_enabled if http_config is not None else True

    # If caching is disabled, optionally configure a pooled HTTP adapter and return.
    # niquests handles SSL natively, so no custom SSL context injection is needed.
    if not http_cache_enabled:
        if pool_config is not None:
            retry_attempts = pool_config.retry_attempts if pool_config.enable_retry else 0
            retry_strategy = Retry(
                total=retry_attempts,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS"],
            )
            adapter = HTTPAdapter(
                pool_connections=pool_config.max_connections,
                pool_maxsize=pool_config.max_per_host,
                max_retries=retry_strategy,
            )
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            logger.debug(f"Configured connection pool without caching: max_connections={pool_config.max_connections}, max_per_host={pool_config.max_per_host}")

        logger.debug("Creating plain HTTP session (caching disabled)")
        return session

    # Resolve cache settings from http_config or defaults
    ttl = http_config.cache_ttl if http_config is not None else 7200
    max_retries_count = http_config.max_retries if http_config is not None else 3

    # Determine cache file path — use explicit param or fall back to PathConfig default
    cache_file = str(http_cache_file) if http_cache_file is not None else str(PathConfig().http_cache_file)

    logger.debug("Creating cached HTTP session with cache_db=%s)", cache_file)
    logger.debug("HTTP cache config: ttl=%s, max_retries=%s", ttl, max_retries_count)

    # Create SQLite storage backend
    storage = SyncSqliteStorage(
        database_path=cache_file,
        default_ttl=ttl,
    )
    storage = cast("SyncBaseStorage", storage)

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
    # _NiquetsCacheAdapter bridges niquests<->hishel type incompatibility in send().
    cache_adapter = _NiquetsCacheAdapter(
        pool_connections=pool_config.max_connections if pool_config is not None else 10,
        pool_maxsize=pool_config.max_per_host if pool_config is not None else 10,
        max_retries=max_retries,
        storage=storage,
    )

    # Mount the cache adapter
    session.mount("http://", cache_adapter)
    session.mount("https://", cache_adapter)

    if pool_config is not None:
        logger.debug(f"Configured cache + pool adapter: max_connections={pool_config.max_connections}, max_per_host={pool_config.max_per_host}")

    return session


__all__ = [
    "PoolConfig",
    "create_cached_session",
    "download_to_file",
    "resolve_ssl_verify",
]
