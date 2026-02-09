"""Central TDoc fetching interface that consolidates all three fetching methods.

This module provides a unified interface for fetching TDoc metadata using one of three methods:
1. 3GPP portal without credentials (URL only)
2. 3GPP portal with credentials (full metadata)
3. WhatTheSpec.net JSON API (full metadata)

The central fetch_tdoc() function selects the appropriate method based on flags.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from tdoc_crawler.crawlers.portal import create_portal_client
from tdoc_crawler.crawlers.tdocs import TDocCrawlResult
from tdoc_crawler.crawlers.whatthespec import WhatTheSpecResolutionError, resolve_via_whatthespec
from tdoc_crawler.credentials import resolve_credentials
from tdoc_crawler.database import TDocDatabase, resolve_meeting_id
from tdoc_crawler.models.base import HttpCacheConfig, PortalCredentials
from tdoc_crawler.models.tdocs import QueryConfig, TDocMetadata

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
        logger.debug(f"Fetching {tdoc_id} via WhatTheSpec API")
        metadata = resolve_via_whatthespec(tdoc_id, cache_dir, http_cache, timeout)
        if metadata is None:
            raise ValueError(f"TDoc {tdoc_id} not found via WhatTheSpec")
        return metadata

    elif full_metadata:
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
            agenda_item_nbr=Decimal("0"),
            agenda_item_text="Unknown",
            status="",
            meeting_name=None,
            is_revision_of=None,
            file_size=None,
            date_created=None,
            validated=False,
            validation_failed=False,
        )


def fetch_missing_tdocs_batch(
    database: TDocDatabase,
    cache_dir: Path,
    missing_ids: list[str],
    credentials: PortalCredentials | None = None,
    http_cache: HttpCacheConfig | None = None,
    timeout: int = 30,
) -> TDocCrawlResult:
    """Fetch multiple missing TDocs using portal authentication."""
    errors = []

    if credentials is None:
        credentials = resolve_credentials(None, None)

    if not credentials:
        logger.info("Portal credentials not available, skipping portal authentication fetch")
        errors.append("Portal credentials required for targeted fetch. Set TDC_EOL_USERNAME and TDC_EOL_PASSWORD.")
        return TDocCrawlResult(processed=len(missing_ids), inserted=0, updated=0, errors=errors)

    inserted_count = 0
    updated_count = 0

    client = create_portal_client(
        credentials=credentials,
        cache_dir=cache_dir,
        cache_ttl=http_cache.ttl if http_cache else 3600,
        cache_refresh_on_access=http_cache.refresh_ttl_on_access if http_cache else False,
        timeout=timeout,
    )

    for tdoc_id in missing_ids:
        try:
            metadata = client.fetch_tdoc_metadata(tdoc_id)

            if metadata.meeting_name:
                meeting_id = resolve_meeting_id(database, metadata.meeting_name)
                if meeting_id:
                    metadata.meeting_id = meeting_id
                else:
                    logger.warning(f"Could not resolve meeting '{metadata.meeting_name}' to meeting_id for {tdoc_id}")

            inserted, updated = database.upsert_tdoc(metadata)
            if inserted:
                inserted_count += 1
            elif updated:
                updated_count += 1

            logger.info(f"Successfully fetched and stored {tdoc_id}")

        except ValidationError as exc:
            validation_errors = []
            for error in exc.errors():
                field = error["loc"][0] if error["loc"] else "unknown"
                message = error["msg"]
                validation_errors.append(f"{field}: {message}")

            error_msg = f"Failed to fetch {tdoc_id}: {'; '.join(validation_errors)}"
            logger.warning(error_msg)
            errors.append(error_msg)
        except Exception as exc:
            error_msg = f"Failed to fetch {tdoc_id}: {exc}"
            logger.error(error_msg)
            errors.append(error_msg)

    return TDocCrawlResult(
        processed=len(missing_ids),
        inserted=inserted_count,
        updated=updated_count,
        errors=errors,
    )


def fetch_via_whatthespec_batch(
    database: TDocDatabase,
    cache_dir: Path,
    missing_ids: list[str],
    http_cache: HttpCacheConfig | None = None,
) -> TDocCrawlResult:
    """Fetch multiple missing TDocs using WhatTheSpec.net API."""
    errors = []
    inserted_count = 0
    updated_count = 0

    if http_cache is None:
        http_cache = HttpCacheConfig()

    for tdoc_id in missing_ids:
        try:
            metadata = resolve_via_whatthespec(tdoc_id, cache_dir, http_cache)
            if metadata:
                inserted, updated = database.upsert_tdoc(metadata)
                if inserted:
                    inserted_count += 1
                elif updated:
                    updated_count += 1
                logger.info(f"Successfully fetched {tdoc_id} via whatthespec")
            else:
                error_msg = f"WhatTheSpec returned no data for {tdoc_id}"
                logger.warning(error_msg)
                errors.append(error_msg)
        except WhatTheSpecResolutionError as exc:
            error_msg = f"WhatTheSpec resolution failed for {tdoc_id}: {exc}"
            logger.warning(error_msg)
            errors.append(error_msg)
        except Exception as exc:
            error_msg = f"Unexpected error fetching {tdoc_id} via whatthespec: {exc}"
            logger.exception(error_msg)
            errors.append(error_msg)

    return TDocCrawlResult(
        processed=len(missing_ids),
        inserted=inserted_count,
        updated=updated_count,
        errors=errors,
    )


class FetchMissingResult:
    """Result from fetch_missing_tdocs orchestration."""

    def __init__(
        self,
        refreshed: list[TDocMetadata],
        fetch_result: TDocCrawlResult | None = None,
        used_whatthespec_fallback: bool = False,
    ):
        self.refreshed = refreshed
        self.fetch_result = fetch_result
        self.used_whatthespec_fallback = used_whatthespec_fallback


def fetch_missing_tdocs(
    database: TDocDatabase,
    cache_dir: Path,
    config: QueryConfig,
    results: list[TDocMetadata],
    credentials: PortalCredentials | None = None,
    full_metadata: bool = False,
    use_whatthespec: bool = False,
) -> FetchMissingResult:
    """Fetch missing TDocs if any are requested but not found in database.

    Orchestrates fetching based on flags, uses WhatTheSpec fallback when needed.
    """
    if not config.tdoc_ids:
        return FetchMissingResult(refreshed=results)

    requested = [value.upper() for value in config.tdoc_ids]
    found = {item.tdoc_id for item in results}
    missing = [value for value in requested if value not in found]
    if not missing:
        return FetchMissingResult(refreshed=results)

    # Log what we're about to do
    if use_whatthespec:
        logger.info(f"Fetching missing TDocs via WhatTheSpec: {', '.join(missing)}")
    elif full_metadata:
        logger.info(f"Fetching missing TDocs with full metadata: {', '.join(missing)}")
    else:
        logger.info(f"Fetching missing TDocs: {', '.join(missing)}")

    # Handle use_whatthespec flag - always use WhatTheSpec method
    if use_whatthespec:
        fetch_result = fetch_via_whatthespec_batch(database, cache_dir, missing)
        refreshed = database.query_tdocs(config)
        return FetchMissingResult(
            refreshed=refreshed,
            fetch_result=fetch_result,
            used_whatthespec_fallback=True,
        )

    # Handle full_metadata flag - use authenticated portal method
    if full_metadata:
        if credentials is None:
            fetch_result = TDocCrawlResult(
                processed=len(missing),
                inserted=0,
                updated=0,
                errors=["Portal credentials required for full metadata fetching"],
            )
            logger.warning("Portal credentials required for full metadata fetching")
            return FetchMissingResult(refreshed=results, fetch_result=fetch_result)

        fetch_result = fetch_missing_tdocs_batch(
            database=database,
            cache_dir=cache_dir,
            missing_ids=missing,
            credentials=credentials,
        )
        refreshed = database.query_tdocs(config)
        return FetchMissingResult(refreshed=refreshed, fetch_result=fetch_result)

    # Default behavior - use unauthenticated portal method with WhatTheSpec fallback
    fetch_result = fetch_missing_tdocs_batch(
        database=database,
        cache_dir=cache_dir,
        missing_ids=missing,
        credentials=credentials,
    )

    # Check if we should try whatthespec fallback
    credentials_unavailable = credentials is None
    has_credentials_error = any("credentials required" in str(err).lower() for err in fetch_result.errors)
    should_try_whatthespec = credentials_unavailable and has_credentials_error

    used_fallback = False
    if should_try_whatthespec:
        refreshed = database.query_tdocs(config)
        refreshed_ids = {item.tdoc_id for item in refreshed}
        still_missing = [value for value in requested if value not in refreshed_ids]

        if still_missing:
            logger.info(f"Trying whatthespec fallback for {len(still_missing)} TDoc(s)")
            fallback_result = fetch_via_whatthespec_batch(database, cache_dir, still_missing)
            fetch_result = TDocCrawlResult(
                processed=fetch_result.processed + fallback_result.processed,
                inserted=fetch_result.inserted + fallback_result.inserted,
                updated=fetch_result.updated + fallback_result.updated,
                errors=fetch_result.errors + fallback_result.errors,
            )
            used_fallback = True

    refreshed = database.query_tdocs(config)
    return FetchMissingResult(
        refreshed=refreshed,
        fetch_result=fetch_result,
        used_whatthespec_fallback=used_fallback,
    )
