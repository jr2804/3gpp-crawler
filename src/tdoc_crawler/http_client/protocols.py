"""Protocol definitions for HTTP client provider abstractions."""

from __future__ import annotations

import requests


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

    def close(self) -> None:
        """Close and release the cached session."""
        if self._session is not None:
            self._session.close()
            self._session = None


__all__ = ["DefaultHttpClientProvider"]
