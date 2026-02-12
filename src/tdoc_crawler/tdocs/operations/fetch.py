"""TDoc fetching operations using source abstraction.

This module provides unified fetching interface that uses the TDocSource
abstraction to fetch metadata from various sources (WhatTheSpec, Portal, etc.).
"""

from __future__ import annotations

from enum import Enum

import requests
from pydantic import ValidationError

from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.credentials import resolve_credentials
from tdoc_crawler.database import MeetingDatabase, TDocDatabase
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.base import HttpCacheConfig
from tdoc_crawler.tdocs.models import TDocMetadata, TDocQueryConfig
from tdoc_crawler.tdocs.operations.crawl import TDocCrawlResult
from tdoc_crawler.tdocs.sources import (
    DocumentListSource,
    PortalSource,
    TDocSourceConfig,
    WhatTheSpecSource,
)

logger = get_logger(__name__)


class FetchMethod(Enum):
    """Enumeration of available TDoc fetching methods."""

    PORTAL_URL_ONLY = "portal_url_only"
    PORTAL_FULL_METADATA = "portal_full_metadata"
    WHATTHESPEC = "whatthespec"
    DOCUMENT_LIST = "document_list"


class FetchMissingResult:
    """Result from fetch_missing_tdocs orchestration."""

    def __init__(
        self,
        refreshed: list[TDocMetadata],
        fetch_result: TDocCrawlResult | None = None,
        used_whatthespec_fallback: bool = False,
    ):
        """Initialize fetch result.

        Args:
            refreshed: Updated list of TDoc metadata after fetching
            fetch_result: Result of the batch fetch operation
            used_whatthespec_fallback: Whether WhatTheSpec was used as fallback
        """
        self.refreshed = refreshed
        self.fetch_result = fetch_result
        self.used_whatthespec_fallback = used_whatthespec_fallback


def create_source(
    method: FetchMethod,
    config: TDocSourceConfig,
    session: requests.Session | None = None,
) -> WhatTheSpecSource | PortalSource | DocumentListSource:
    """Create TDoc source based on fetch method.

    Args:
        method: Fetch method to use
        config: Source configuration
        session: Optional requests.Session to reuse

    Returns:
        Configured TDoc source instance

    Raises:
        ValueError: If method requires credentials but none provided
    """
    if method == FetchMethod.WHATTHESPEC:
        return WhatTheSpecSource(config=config, session=session)
    elif method == FetchMethod.PORTAL_FULL_METADATA:
        return PortalSource(config=config)
    elif method == FetchMethod.DOCUMENT_LIST:
        return DocumentListSource(config=config)
    elif method == FetchMethod.PORTAL_URL_ONLY:
        # For URL-only method, we'll handle it separately as it doesn't fit the source pattern
        raise ValueError("PORTAL_URL_ONLY method should be handled separately")
    else:
        raise ValueError(f"Unknown fetch method: {method}")


'''
def fetch_tdoc(
    tdoc_id: str,
    full_metadata: bool = False,
    use_whatthespec: bool = False,
    session: requests.Session | None = None,
    timeout: int = 30,
    http_cache: HttpCacheConfig | None = None,
    cache_manager_name: str | None = None,
) -> TDocMetadata:
    """Fetch TDoc using the appropriate method based on flags.

    Args:
        tdoc_id: TDoc identifier (e.g., "S4-260001")
        full_metadata: If True, fetch full metadata (requires credentials for portal)
        use_whatthespec: If True, always use WhatTheSpec method
        credentials: Portal credentials (required for authenticated portal method)
        session: Optional requests.Session to reuse
        timeout: Request timeout in seconds
        http_cache: HTTP cache configuration
        cache_manager_name: Optional cache manager name

    Returns:
        TDocMetadata with available information

    Raises:
        ValueError: If required credentials are missing
    """
    manager = resolve_cache_manager(cache_manager_name)

    # Determine fetch method
    if use_whatthespec:
        method = FetchMethod.WHATTHESPEC
    elif full_metadata:
        method = FetchMethod.PORTAL_FULL_METADATA
    else:
        method = FetchMethod.PORTAL_URL_ONLY

    # Handle URL-only method separately (doesn't use source abstraction)
    if method == FetchMethod.PORTAL_URL_ONLY:

        logger.debug(f"Fetching {tdoc_id} via unauthenticated 3GPP portal")
        client = create_portal_client(cache_dir=manager.root, timeout=min(timeout, 15), session=session)
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

    # Create source configuration
    config = TDocSourceConfig(
        cache_manager_name=cache_manager_name,
        http_cache=http_cache,
        timeout=timeout,
    )

    # Create and use appropriate source
    source = create_source(method, config, session)
    logger.debug(f"Fetching {tdoc_id} via {source.source_name}")

    metadata = source.fetch_by_id(tdoc_id, db_file=manager.db_file, timeout=timeout)
    if metadata is None:
        raise ValueError(f"TDoc {tdoc_id} not found via {source.source_name}")

    return metadata
'''


def fetch_missing_tdocs_batch(
    database: TDocDatabase,
    missing_ids: list[str],
    session: requests.Session | None = None,
    timeout: int = 30,
    http_cache: HttpCacheConfig | None = None,
    cache_manager_name: str | None = None,
) -> TDocCrawlResult:
    """Fetch multiple missing TDocs using portal authentication.

    Args:
        database: Database instance for storing results
        missing_ids: List of TDoc IDs to fetch
        credentials: Portal credentials (auto-resolved if None)
        http_cache: HTTP cache configuration
        timeout: Request timeout in seconds
        session: Optional requests.Session to reuse
        cache_manager_name: Optional cache manager name

    Returns:
        TDocCrawlResult with fetch statistics
    """
    errors = []
    inserted_count = 0
    updated_count = 0

    # Create source configuration and portal source
    config = TDocSourceConfig(
        http_cache=http_cache,
        cache_manager_name=cache_manager_name,
        timeout=timeout,
    )
    source = PortalSource(config=config)

    for tdoc_id in missing_ids:
        try:
            metadata = source.fetch_by_id(tdoc_id, timeout=timeout)
            if metadata is None:
                error_msg = f"Portal returned no data for {tdoc_id}"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue

            # Resolve meeting_id if needed
            if metadata.meeting_name:
                with MeetingDatabase(database.db_file) as meeting_db:
                    meeting_id = meeting_db.resolve_meeting_id(metadata.meeting_name)
                if meeting_id is not None:
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

    # Clean up source
    source.close()

    return TDocCrawlResult(
        processed=len(missing_ids),
        inserted=inserted_count,
        updated=updated_count,
        errors=errors,
    )


def fetch_via_whatthespec_batch(
    database: TDocDatabase,
    missing_ids: list[str],
    http_cache: HttpCacheConfig | None = None,
    session: requests.Session | None = None,
    cache_manager_name: str | None = None,
) -> TDocCrawlResult:
    """Fetch multiple missing TDocs using WhatTheSpec.net API.

    Args:
        database: Database instance for storing results
        missing_ids: List of TDoc IDs to fetch
        http_cache: HTTP cache configuration
        session: Optional requests.Session to reuse
        cache_manager_name: Optional cache manager name

    Returns:
        TDocCrawlResult with fetch statistics
    """
    errors = []
    inserted_count = 0
    updated_count = 0

    # Create source configuration and WhatTheSpec source
    config = TDocSourceConfig(
        http_cache=http_cache,
        cache_manager_name=cache_manager_name,
    )
    source = WhatTheSpecSource(config=config, session=session)
    manager = resolve_cache_manager(cache_manager_name)

    for tdoc_id in missing_ids:
        try:
            metadata = source.fetch_by_id(tdoc_id, db_file=manager.db_file)
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
        except Exception as exc:
            error_msg = f"Error fetching {tdoc_id} via whatthespec: {exc}"
            logger.warning(error_msg)
            errors.append(error_msg)

    return TDocCrawlResult(
        processed=len(missing_ids),
        inserted=inserted_count,
        updated=updated_count,
        errors=errors,
    )


def fetch_missing_tdocs(
    database: TDocDatabase,
    config: TDocQueryConfig,
    results: list[TDocMetadata],
    full_metadata: bool = False,
    use_whatthespec: bool = False,
    session: requests.Session | None = None,
    cache_manager_name: str | None = None,
) -> FetchMissingResult:
    """Fetch missing TDocs if any are requested but not found in database.

    Orchestrates fetching based on flags, uses WhatTheSpec fallback when needed.

    Args:
        database: Database instance
        config: TDocQueryConfig with requested TDoc IDs
        results: Current query results
        full_metadata: If True, fetch full metadata from portal
        use_whatthespec: If True, always use WhatTheSpec
        session: Optional requests.Session to reuse
        cache_manager_name: Optional cache manager name

    Returns:
        FetchMissingResult with updated results and fetch statistics
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
        fetch_result = fetch_via_whatthespec_batch(database, missing, session=session, cache_manager_name=cache_manager_name)
        refreshed = database.query_tdocs(config)
        return FetchMissingResult(
            refreshed=refreshed,
            fetch_result=fetch_result,
            used_whatthespec_fallback=True,
        )

    # Handle full_metadata flag - use authenticated portal method
    credentials = resolve_credentials(None, None)
    credentials_unavailable = credentials is None

    if full_metadata:
        if credentials_unavailable:
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
            missing_ids=missing,
            session=session,
            cache_manager_name=cache_manager_name,
        )

        refreshed = database.query_tdocs(config)
        return FetchMissingResult(refreshed=refreshed, fetch_result=fetch_result)

    # Default behavior - use unauthenticated portal method with WhatTheSpec fallback
    fetch_result = fetch_missing_tdocs_batch(
        database=database,
        missing_ids=missing,
        session=session,
        cache_manager_name=cache_manager_name,
    )

    # Check if we should try whatthespec fallback
    has_credentials_error = any("credentials required" in str(err).lower() for err in fetch_result.errors)
    if credentials_unavailable or has_credentials_error:
        logger.info("Falling back to WhatTheSpec for missing TDocs due to credential issues")
        fetch_result = fetch_via_whatthespec_batch(database, missing, session=session, cache_manager_name=cache_manager_name)
        used_fallback = True
    else:
        used_fallback = False

    refreshed = database.query_tdocs(config)
    return FetchMissingResult(
        refreshed=refreshed,
        fetch_result=fetch_result,
        used_whatthespec_fallback=used_fallback,
    )


__all__ = [
    "FetchMethod",
    "FetchMissingResult",
    "create_source",
    "fetch_missing_tdocs",
    "fetch_missing_tdocs_batch",
    "fetch_tdoc",
    "fetch_via_whatthespec_batch",
]
