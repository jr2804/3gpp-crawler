"""Central TDoc fetching interface that consolidates all three fetching methods.

This module provides a unified interface for fetching TDoc metadata using one of three methods:
1. 3GPP portal without credentials (URL only)
2. 3GPP portal with credentials (full metadata)
3. WhatTheSpec.net JSON API (full metadata)

The central fetch_tdoc() function selects the appropriate method based on flags.
"""

from __future__ import annotations

import logging
from pathlib import Path

from tdoc_crawler.crawlers.portal import extract_tdoc_url_from_portal, fetch_tdoc_metadata
from tdoc_crawler.crawlers.whatthespec import resolve_via_whatthespec
from tdoc_crawler.models.base import HttpCacheConfig, PortalCredentials
from tdoc_crawler.models.tdocs import TDocMetadata

logger = logging.getLogger(__name__)


def fetch_tdoc(
    tdoc_id: str,
    cache_dir: Path,
    http_cache: HttpCacheConfig,
    full_metadata: bool = False,
    use_whatthespec: bool = False,
    credentials: PortalCredentials | None = None,
    timeout: int = 30,
) -> TDocMetadata:
    """Fetch TDoc using the appropriate method based on flags.

    Args:
        tdoc_id: TDoc identifier (e.g., "S4-260001").
        cache_dir: Directory for HTTP cache storage.
        http_cache: HTTP cache configuration.
        full_metadata: If True, fetch full metadata (requires credentials for portal method).
        use_whatthespec: If True, always use WhatTheSpec method regardless of full_metadata.
        credentials: Portal credentials (required for authenticated portal method).
        timeout: Request timeout in seconds.

    Returns:
        TDocMetadata with available information.

    Raises:
        Exception: If fetching fails for any reason.
    """
    # Import here to avoid circular imports

    if use_whatthespec:
        # Always use WhatTheSpec method (Method 3)
        logger.debug(f"Fetching {tdoc_id} via WhatTheSpec API")
        return resolve_via_whatthespec(tdoc_id, cache_dir, http_cache, timeout)

    elif full_metadata:
        # Use authenticated portal method (Method 2)
        if credentials is None:
            raise ValueError("Portal credentials required for full metadata fetching")
        logger.debug(f"Fetching {tdoc_id} via authenticated 3GPP portal")
        return fetch_tdoc_metadata(tdoc_id, credentials, cache_dir, http_cache.ttl, http_cache.refresh_ttl_on_access, timeout)

    else:
        # Use unauthenticated portal method (Method 1) - URL only
        logger.debug(f"Fetching {tdoc_id} via unauthenticated 3GPP portal")
        # Extract URL and create minimal TDocMetadata
        url = extract_tdoc_url_from_portal(tdoc_id, timeout=min(timeout, 15))
        return TDocMetadata(
            tdoc_id=tdoc_id,
            url=url,
            title="",
            meeting_id=0,
            source="",
            contact="",
            agenda_item_nbr=0,
            date=None,
            revision_of="",
            technical_committee="",
            working_group="",
            type="",
            status="",
            referenced_documents=[],
            filename="",
            size=0,
            validated=False,
            validation_failed=False,
        )
