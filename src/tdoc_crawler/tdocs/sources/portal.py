"""3GPP Portal TDoc metadata source.

This module provides a TDocSource implementation that fetches metadata
from the official 3GPP portal using authenticated access.
"""

from __future__ import annotations

import logging
from pathlib import Path

from tdoc_crawler.clients.portal import PortalAuthenticationError, PortalClient
from tdoc_crawler.parsers.portal import PortalParsingError
from tdoc_crawler.tdocs.models import TDocMetadata
from tdoc_crawler.tdocs.sources.base import TDocSourceConfig

logger = logging.getLogger(__name__)


class PortalSource:
    """TDoc metadata source using 3GPP Portal.

    This source provides authenticated access to official 3GPP portal metadata.
    It requires EOL credentials and should be used as a fallback when
    WhatTheSpec or other sources fail.
    """

    def __init__(
        self,
        config: TDocSourceConfig,
    ) -> None:
        """Initialize portal source.

        Args:
            config: Source configuration (must include credentials)

        Raises:
            ValueError: If credentials are not provided
        """
        if config.credentials is None:
            raise ValueError("Portal source requires credentials")

        self.config = config
        self._client: PortalClient | None = None

    def close(self) -> None:
        """Close the portal client session."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def fetch_by_id(
        self,
        tdoc_id: str,
        *,
        db_file: Path | None = None,
        timeout: int = 30,
    ) -> TDocMetadata | None:
        """Fetch TDoc metadata by TDoc ID from 3GPP Portal.

        Args:
            tdoc_id: TDoc identifier (e.g., "S4-251364")
            db_file: Optional path to database for meeting resolution (unused)
            timeout: Request timeout in seconds

        Returns:
            TDocMetadata if found, None otherwise
        """
        client = self._get_client()

        try:
            # Try to extract URL first (unauthenticated)
            url = None
            try:
                url = client.extract_tdoc_url(tdoc_id)
            except Exception as exc:
                logger.debug(f"URL extraction failed for {tdoc_id}: {exc}")

            # Fetch full metadata (authenticated)
            metadata = client.fetch_tdoc_metadata(tdoc_id, url)
            return metadata

        except (PortalAuthenticationError, PortalParsingError) as exc:
            logger.warning(f"Portal lookup failed for {tdoc_id}: {exc}")
            return None
        except Exception as exc:
            logger.error(f"Unexpected error fetching {tdoc_id} from portal: {exc}")
            return None

    def fetch_by_meeting(
        self,
        meeting_id: int,
        *,
        timeout: int = 30,
    ) -> list[TDocMetadata]:
        """Fetch all TDoc metadata for a meeting.

        The Portal source does not support bulk meeting queries through
        the authenticated TDoc view interface. Use DocumentListSource instead.

        Args:
            meeting_id: 3GPP meeting identifier
            timeout: Request timeout in seconds

        Returns:
            Empty list (not supported by this source)
        """
        logger.debug(f"Portal source does not support bulk meeting queries for meeting {meeting_id}")
        return []

    @property
    def source_name(self) -> str:
        """Return the name of this source for logging."""
        return "Portal"

    @property
    def requires_authentication(self) -> bool:
        """Return whether this source requires authentication."""
        return True

    def __enter__(self) -> PortalSource:
        """Enter context manager."""
        return self

    def __exit__(self, *args) -> None:
        """Exit context manager and close client."""
        self.close()

    def _get_client(self) -> PortalClient:
        """Get or create portal client.

        Returns:
            Configured PortalClient instance
        """
        if self._client is None:
            self._client = PortalClient(
                credentials=self.config.credentials,
                cache_dir=self.config.cache_dir,
                cache_ttl=self.config.http_cache.ttl,
                cache_refresh_on_access=self.config.http_cache.refresh_ttl_on_access,
                timeout=self.config.timeout,
            )
        return self._client


__all__ = [
    "PortalSource",
]
