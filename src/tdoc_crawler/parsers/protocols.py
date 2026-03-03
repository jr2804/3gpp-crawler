"""Protocol definitions for parser and HTTP client abstractions."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import requests


@runtime_checkable
class ParserProtocol(Protocol):
    """Protocol for HTML/data parser implementations.

    Parsers accept raw content (typically HTML strings) and return
    structured data objects.
    """

    def parse(self, content: str, **kwargs: Any) -> Any:
        """Parse raw content into structured data.

        Args:
            content: Raw content to parse (e.g., HTML string).
            **kwargs: Parser-specific keyword arguments.

        Returns:
            Parsed structured data (type depends on implementation).
        """
        ...


@runtime_checkable
class ClientProtocol(Protocol):
    """Protocol for HTTP client abstractions used by parsers and sources.

    Implementations wrap a requests.Session and provide a uniform
    fetch interface.
    """

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        """Perform an HTTP GET request.

        Args:
            url: Target URL.
            **kwargs: Additional keyword arguments forwarded to requests.

        Returns:
            HTTP response object.
        """
        ...

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        """Perform an HTTP POST request.

        Args:
            url: Target URL.
            **kwargs: Additional keyword arguments forwarded to requests.

        Returns:
            HTTP response object.
        """
        ...


__all__ = ["ClientProtocol", "ParserProtocol"]
