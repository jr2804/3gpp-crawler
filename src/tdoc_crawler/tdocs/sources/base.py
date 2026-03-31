"""Base classes and protocols for TDoc metadata sources.

This module defines the TDocSource protocol that abstracts different sources
of TDoc metadata (WhatTheSpec, 3GPP portal, meeting document lists, etc.).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from tdoc_crawler.config.settings import HttpConfig
from tdoc_crawler.tdocs.models import TDocMetadata


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
        timeout: int = 30,
        http_config: HttpConfig | None = None,
        http_cache_file: Path | None = None,
        db_file: Path | None = None,
    ) -> None:
        """Initialize source configuration.

        Args:
            timeout: Request timeout in seconds
            http_config: HTTP configuration from ThreeGPPConfig
            http_cache_file: Optional explicit path to the HTTP cache database
            db_file: Optional explicit path to the metadata database
        """
        self.http_config = http_config
        self.timeout = timeout
        self.http_cache_file = http_cache_file
        self.db_file = db_file


__all__ = [
    "TDocSource",
    "TDocSourceConfig",
]
