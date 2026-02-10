"""Base classes and protocols for TDoc metadata sources.

This module defines the TDocSource protocol that abstracts different sources
of TDoc metadata (WhatTheSpec, 3GPP portal, meeting document lists, etc.).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from tdoc_crawler.models.base import HttpCacheConfig, PortalCredentials

if TYPE_CHECKING:
    from tdoc_crawler.models.tdocs import TDocMetadata


class TDocSource(Protocol):
    """Protocol for TDoc metadata sources.

    This protocol defines the interface for fetching TDoc metadata from
    various sources (WhatTheSpec API, 3GPP portal, meeting document lists).
    """

    def fetch_by_id(
        self,
        tdoc_id: str,
        *,
        db_file: Path | None = None,
        timeout: int = 30,
    ) -> TDocMetadata | None:
        """Fetch TDoc metadata by TDoc ID.

        Args:
            tdoc_id: TDoc identifier (e.g., "S4-251364")
            db_file: Optional path to database for meeting resolution
            timeout: Request timeout in seconds

        Returns:
            TDocMetadata if found, None otherwise
        """
        ...

    def fetch_by_meeting(
        self,
        meeting_id: int,
        *,
        timeout: int = 30,
    ) -> list[TDocMetadata]:
        """Fetch all TDoc metadata for a meeting.

        Args:
            meeting_id: 3GPP meeting identifier
            timeout: Request timeout in seconds

        Returns:
            List of TDocMetadata for the meeting (empty if not supported)
        """
        ...

    @property
    def source_name(self) -> str:
        """Return the name of this source for logging."""
        ...

    @property
    def requires_authentication(self) -> bool:
        """Return whether this source requires authentication."""
        ...


class TDocSourceConfig:
    """Configuration for TDoc metadata sources.

    This class consolidates common configuration parameters used across
    different TDoc source implementations.
    """

    def __init__(
        self,
        cache_dir: Path,
        http_cache: HttpCacheConfig | None = None,
        credentials: PortalCredentials | None = None,
        timeout: int = 30,
        cache_manager_name: str | None = None,
    ) -> None:
        """Initialize source configuration.

        Args:
            cache_dir: Directory for HTTP cache storage
            http_cache: HTTP cache configuration
            credentials: Optional portal credentials
            timeout: Request timeout in seconds
            cache_manager_name: Optional name of cache manager to use
        """
        self.cache_dir = cache_dir
        self.http_cache = http_cache or HttpCacheConfig()
        self.credentials = credentials
        self.timeout = timeout
        self.cache_manager_name = cache_manager_name


__all__ = [
    "TDocSource",
    "TDocSourceConfig",
]
