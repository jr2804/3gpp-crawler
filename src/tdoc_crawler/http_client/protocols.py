"""Protocol definitions for HTTP client provider abstractions."""

from __future__ import annotations

from pathlib import Path

import requests


class DefaultHttpClientProvider:
    """Default HttpClientProvider backed by the cached session factory.

    Creates a new session on first call and caches it for reuse.
    """

    def __init__(self, http_cache_file: Path | None = None) -> None:
        """Initialize with optional HTTP cache file path.

        Args:
            http_cache_file: Optional explicit path to the HTTP cache database.
                             Falls back to PathConfig default when caching is enabled.
        """
        self._http_cache_file = http_cache_file
        self._session: requests.Session | None = None

    def close(self) -> None:
        """Close and release the cached session."""
        if self._session is not None:
            self._session.close()
            self._session = None


__all__ = ["DefaultHttpClientProvider"]
