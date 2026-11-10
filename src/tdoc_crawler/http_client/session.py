"""HTTP client factory with hishel caching support."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from gzip import decompress as gzip_decompress
from pathlib import Path
from zlib import decompress as zlib_decompress

import brotli
import niquests as requests
from hishel import BaseStorage, CacheOptions, Headers, Request, Response, SqliteStorage
from hishel._sync_rfc import handle_request_with_rfc  # hishel exposes no public sync RFC state machine
from niquests.adapters import HTTPAdapter
from urllib3 import HTTPHeaderDict
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


class _NiquetsCacheAdapter(HTTPAdapter):
    """RFC 9111 cache adapter for niquests, driven by hishel's sync state machine.

    hishel's own requests adapter only accepts requests.PreparedRequest, and
    niquests.PreparedRequest does not inherit from it, so the send flow is
    reimplemented here with niquests objects.
    """

    def __init__(self, *, storage: BaseStorage, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.storage = storage

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
        stream: bool = False,
        timeout: float | tuple[float, float] | None = None,
        verify: bool | str = True,
        cert: str | tuple[str, str] | None = None,
        proxies: dict[str, str] | None = None,
        **_kwargs: object,
    ) -> requests.models.Response:
        """Answer from the cache when possible, otherwise fetch upstream and store the result."""

        def send_upstream(prepared: requests.models.PreparedRequest) -> requests.models.Response:
            # Always streamed: the body is read from the cache layer, not by the caller.
            return super(_NiquetsCacheAdapter, self).send(prepared, stream=True, timeout=timeout, verify=verify, cert=cert, proxies=proxies)

        internal_request = _request_to_internal(request)
        key = hashlib.sha256(internal_request.url.encode()).hexdigest()
        upstream: requests.models.Response | None = None

        def send(state_request: Request) -> Response:
            nonlocal upstream
            # Only the state machine's revalidation headers differ from the caller's request.
            prepared = request.copy()
            for name, value in state_request.headers.items():
                if internal_request.headers.get(name) != value:
                    prepared.headers[name] = value

            response = send_upstream(prepared)
            if response.status_code == 304:
                # The cached body is served instead, so this connection is done.
                response.raw.read()
            else:
                upstream = response
            return _response_to_internal(response)

        response, _status = handle_request_with_rfc(internal_request, send, self.storage, key, CacheOptions())
        result = _internal_to_niquests_response(response)
        result.request = request
        result.connection = self  # type: ignore[assignment]
        return result

    def close(self) -> None:
        super().close()
        self.storage.close()


def _request_to_internal(model: requests.models.PreparedRequest) -> Request:
    """Convert a niquests prepared request into a hishel request."""
    if model.method is None:
        msg = "prepared request method must not be None"
        raise ValueError(msg)
    headers = {key.lower(): value.decode("latin-1") if isinstance(value, bytes) else value for key, value in model.headers.items()}
    return Request(method=model.method, url=str(model.url), headers=Headers(headers))


def _response_to_internal(model: requests.models.Response) -> Response:
    """Convert an upstream niquests response into a hishel response, keeping raw (undecoded) bytes."""
    # Raw headers keep repeated values apart; the response's own headers join them with commas.
    raw_headers = model.raw.headers
    headers = {key.lower(): raw_headers.getlist(key) for key in raw_headers}
    # The stored body is not re-framed, so its transfer encoding is dropped.
    headers.pop("transfer-encoding", None)
    return Response(status_code=model.status_code, headers=Headers(headers), stream=model.raw.stream(decode_content=False))


def _internal_to_niquests_response(model: Response) -> requests.models.Response:
    response = requests.models.Response()

    raw_body = b"".join(model.stream) if model.stream is not None else b""
    headers = HTTPHeaderDict([(key, value) for key in model.headers for value in model.headers.get_list(key) or []])
    content_encoding = model.headers.get("content-encoding", "")
    body = _decompress_body(raw_body, content_encoding) if content_encoding else raw_body

    response.raw = HTTPResponse(
        body=raw_body,
        headers=headers,
        status=model.status_code,
        preload_content=False,
        decode_content=False,
    )
    response.status_code = model.status_code
    response.headers.update({key: ", ".join(model.headers.get_list(key) or []) for key in model.headers})
    response._content = body
    response._content_consumed = True
    response.url = ""

    return response


def _decompress_body(body: bytes, content_encoding: str) -> bytes:
    encoding = content_encoding.lower().strip()
    if encoding == "br":
        return brotli.decompress(body)
    if encoding == "gzip":
        return gzip_decompress(body)
    if encoding == "deflate":
        return zlib_decompress(body)
    return body


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

    # Create SQLite storage backend. WAL mode gives concurrent reads while
    # writing and avoids "database is locked" under the threaded sub-interpreter
    # Open the connection ourselves so we can set PRAGMA journal_mode=WAL.
    # WAL mode gives concurrent reads while writing and avoids "database is
    # locked" under the threaded sub-interpreter workers that crawl_tdocs
    # uses under the MCP stdio server. Hishel accepts a pre-built connection,
    # but treats database_path as a plain path so URI-based params like
    # ?journal_mode=WAL won't work without this hook.
    cache_path = Path(cache_file)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(cache_path), check_same_thread=False)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    storage = SqliteStorage(
        connection=connection,
        default_ttl=ttl,
    )

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


__all__ = [
    "PoolConfig",
    "create_cached_session",
    "download_to_file",
    "resolve_ssl_verify",
]
