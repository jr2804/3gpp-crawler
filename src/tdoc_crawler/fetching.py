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

from tdoc_crawler.crawlers.portal import create_portal_client
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
    if use_whatthespec:
        # Always use WhatTheSpec method (Method 3)
        logger.debug(f"Fetching {tdoc_id} via WhatTheSpec API")
        metadata = resolve_via_whatthespec(tdoc_id, cache_dir, http_cache, timeout)
        if metadata is None:
            raise ValueError(f"TDoc {tdoc_id} not found via WhatTheSpec")
        return metadata

    elif full_metadata:
        # Use authenticated portal method (Method 2)
        if credentials is None:
            raise ValueError("Portal credentials required for full metadata fetching")
        logger.debug(f"Fetching {tdoc_id} via authenticated 3GPP portal")
        client = create_portal_client(
            credentials=credentials,
            cache_dir=cache_dir,
            cache_ttl=http_cache.ttl,
            cache_refresh_on_access=http_cache.refresh_ttl_on_access,
            timeout=timeout,
        )
        return client.fetch_tdoc_metadata(tdoc_id)

    else:
        # Use unauthenticated portal method (Method 1) - URL only
        logger.debug(f"Fetching {tdoc_id} via unauthenticated 3GPP portal")
        client = create_portal_client(cache_dir=cache_dir, timeout=min(timeout, 15))
        url = client.extract_tdoc_url(tdoc_id)
        return TDocMetadata(
            tdoc_id=tdoc_id.upper(),
            meeting_id=0,
            title="",
            url=url,
            source="",
            contact="",
            tdoc_type="unknown",
            for_purpose="unknown",
            agenda_item_nbr=0,
            agenda_item_text="Unknown",
            validated=False,
            validation_failed=False,
        )
