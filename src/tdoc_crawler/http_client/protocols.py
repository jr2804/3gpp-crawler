"""Protocol definitions for HTTP client provider abstractions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import requests

from tdoc_crawler.http_client.session import create_cached_session


@runtime_checkable
class HttpClientProvider(Protocol):
    """Protocol for providing HTTP sessions."""

    def get_session(self) -> requests.Session:
        """Return a configured requests.Session for HTTP operations."""
        ...


class DefaultHttpClientProvider:
    """Default HttpClientProvider backed by the cached session factory.

    Creates a new session on first call and caches it for reuse.
    """

    def __init__(self, cache_manager_name: str | None = None) -> None:
        """Initialize with optional cache manager name.

        Args:
            cache_manager_name: Optional name of the cache manager to use for
                                HTTP cache storage configuration.
        """
        self._cache_manager_name = cache_manager_name
        self._session: requests.Session | None = None

    def get_session(self) -> requests.Session:
        """Return a cached requests.Session with hishel caching enabled.

        Returns:
            A requests.Session configured with caching.
        """
        if self._session is None:
            self._session = create_cached_session(cache_manager_name=self._cache_manager_name)
        return self._session

    def close(self) -> None:
        """Close and release the cached session."""
        if self._session is not None:
            self._session.close()
            self._session = None


__all__ = ["DefaultHttpClientProvider", "HttpClientProvider"]
