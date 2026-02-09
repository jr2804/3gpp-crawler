"""Functions for fetching missing TDocs from the portal."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import ValidationError

from tdoc_crawler.cli.console import get_console
from tdoc_crawler.cli.helpers import resolve_meeting_id
from tdoc_crawler.crawlers import TDocCrawlResult, WhatTheSpecResolutionError, create_portal_client, resolve_via_whatthespec
from tdoc_crawler.credentials import resolve_credentials
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import HttpCacheConfig, PortalCredentials, QueryConfig, TDocMetadata

console = get_console()
_logger = logging.getLogger(__name__)


# TODO: these functions do not belong in the CLI layer, they should be refactored into a separate service layer that can be called from both CLI and API contexts. The CLI should only handle user interaction and delegate fetching logic to a service module. This would improve separation of concerns and make the fetching logic reusable across different interfaces.
# TODO: the fetching logic is currently duplicated between the portal method and the whatthespec method. We should refactor to have a single fetching function that can use different data sources based on configuration, rather than having separate functions with similar logic. This would reduce code duplication and make it easier to maintain.
def fetch_missing_tdocs(
    database: TDocDatabase,
    cache_dir: Path,
    missing_ids: list[str],
    credentials: PortalCredentials | None = None,
) -> TDocCrawlResult:
    """Fetch missing TDocs using portal authentication.

    Args:
        database: Database connection
        cache_dir: Cache directory path
        missing_ids: List of TDoc IDs to fetch
        credentials: Portal credentials (optional)

    Returns:
        TDocCrawlResult with inserted/updated counts and errors
    """
    errors = []

    # Only try to resolve credentials if not explicitly provided
    if credentials is None:
        credentials = resolve_credentials(None, None)

    # If still no credentials, log that portal fetch will be skipped
    # The caller may attempt whatthespec fallback if credentials are unavailable
    if not credentials:
        _logger.info("Portal credentials not available, skipping portal authentication fetch")
        errors.append("Portal credentials required for targeted fetch. Set EOL_USERNAME and EOL_PASSWORD.")
        return TDocCrawlResult(processed=len(missing_ids), inserted=0, updated=0, errors=errors)

    inserted_count = 0
    updated_count = 0

    client = create_portal_client(credentials=credentials, cache_dir=cache_dir)

    for tdoc_id in missing_ids:
        try:
            # Fetch metadata from portal using PortalClient
            metadata = client.fetch_tdoc_metadata(tdoc_id)

            # Resolve meeting_id from meeting name if available
            if metadata.meeting_name:
                meeting_id = resolve_meeting_id(database, metadata.meeting_name)
                if meeting_id:
                    metadata.meeting_id = meeting_id
                else:
                    _logger.warning(f"Could not resolve meeting '{metadata.meeting_name}' to meeting_id for {tdoc_id}")

            # Insert/update in database
            inserted, updated = database.upsert_tdoc(metadata)
            if inserted:
                inserted_count += 1
            elif updated:
                updated_count += 1

            _logger.info(f"Successfully fetched and stored {tdoc_id}")

        except ValidationError as exc:
            # Extract and display only actual validation errors, not full stack trace
            validation_errors = []
            for error in exc.errors():
                field = error["loc"][0] if error["loc"] else "unknown"
                message = error["msg"]
                validation_errors.append(f"{field}: {message}")

            error_msg = f"Failed to fetch {tdoc_id}: {'; '.join(validation_errors)}"
            _logger.warning(error_msg)
            errors.append(error_msg)
        except Exception as exc:
            error_msg = f"Failed to fetch {tdoc_id}: {exc}"
            _logger.error(error_msg)
            errors.append(error_msg)

    return TDocCrawlResult(
        processed=len(missing_ids),
        inserted=inserted_count,
        updated=updated_count,
        errors=errors,
    )


def _fetch_via_whatthespec(
    database: TDocDatabase,
    cache_dir: Path,
    missing_ids: list[str],
) -> None:
    """Fetch missing TDocs using whatthespec.net fallback.

    Args:
        database: Database connection
        cache_dir: Cache directory path
        missing_ids: List of TDoc IDs to fetch
    """
    http_cache = HttpCacheConfig()

    for tdoc_id in missing_ids:
        try:
            metadata = resolve_via_whatthespec(tdoc_id, cache_dir, http_cache)
            if metadata:
                inserted, updated = database.upsert_tdoc(metadata)
                if inserted or updated:
                    _logger.info(f"Successfully fetched {tdoc_id} via whatthespec")
            else:
                _logger.warning(f"WhatTheSpec returned no data for {tdoc_id}")
        except WhatTheSpecResolutionError as exc:
            _logger.warning(f"WhatTheSpec resolution failed for {tdoc_id}: {exc}")
        except Exception as exc:
            _logger.exception(f"Unexpected error fetching {tdoc_id} via whatthespec: {exc}")


def maybe_fetch_missing_tdocs(
    database: TDocDatabase,
    cache_dir: Path,
    config: QueryConfig,
    results: list[TDocMetadata],
    credentials: PortalCredentials | None = None,
    full_metadata: bool = False,
    use_whatthespec: bool = False,
) -> list[TDocMetadata]:
    """Fetch missing TDocs if any are requested but not found in database.

    Args:
        database: Database connection
        cache_dir: Cache directory
        config: Query configuration with requested TDoc IDs
        results: Already found TDoc metadata
        credentials: Portal credentials (None if not available)
        full_metadata: If True, fetch full metadata instead of URL only
        use_whatthespec: If True, use WhatTheSpec API for fetching

    Returns:
        Updated list of TDocMetadata with newly fetched TDocs
    """
    if not config.tdoc_ids:
        return results
    requested = [value.upper() for value in config.tdoc_ids]
    found = {item.tdoc_id for item in results}
    missing = [value for value in requested if value not in found]
    if not missing:
        return results

    # Handle use_whatthespec flag - always use WhatTheSpec method
    if use_whatthespec:
        console.print(f"[cyan]Fetching missing TDocs via WhatTheSpec: {', '.join(missing)}[/cyan]")
        _fetch_via_whatthespec(database, cache_dir, missing)
        refreshed = database.query_tdocs(config)
        return refreshed

    # Handle full_metadata flag - use authenticated portal method
    if full_metadata:
        if credentials is None:
            console.print("[red]Portal credentials required for full metadata fetching[/red]")
            return results
        console.print(f"[cyan]Fetching missing TDocs with full metadata: {', '.join(missing)}[/cyan]")
        fetch_result = fetch_missing_tdocs(database, cache_dir, missing, credentials)
        if fetch_result.errors:
            console.print(f"[yellow]{len(fetch_result.errors)} issues detected during targeted crawl[/yellow]")
            for error in fetch_result.errors[:3]:
                console.print(f"  - {error}")
        refreshed = database.query_tdocs(config)
        return refreshed

    # Default behavior - use unauthenticated portal method with WhatTheSpec fallback
    console.print(f"[cyan]Fetching missing TDocs: {', '.join(missing)}[/cyan]")
    fetch_result = fetch_missing_tdocs(database, cache_dir, missing, credentials)
    if fetch_result.errors:
        console.print(f"[yellow]{len(fetch_result.errors)} issues detected during targeted crawl[/yellow]")
        for error in fetch_result.errors[:3]:
            console.print(f"  - {error}")

    # Check if we should try whatthespec fallback
    credentials_unavailable = credentials is None
    has_credentials_error = any("credentials required" in str(err).lower() for err in fetch_result.errors)
    should_try_whatthespec = credentials_unavailable and has_credentials_error

    # Try whatthespec fallback for remaining unresolved TDocs
    if should_try_whatthespec:
        refreshed = database.query_tdocs(config)
        refreshed_ids = {item.tdoc_id for item in refreshed}
        still_missing = [value for value in requested if value not in refreshed_ids]

        if still_missing:
            console.print(f"[cyan]Trying whatthespec fallback for {len(still_missing)} TDoc(s)[/cyan]")
            _fetch_via_whatthespec(database, cache_dir, still_missing)

    refreshed = database.query_tdocs(config)
    refreshed_ids = {item.tdoc_id for item in refreshed}
    unresolved = [value for value in requested if value not in refreshed_ids]
    if unresolved:
        console.print(f"[yellow]Still missing: {', '.join(unresolved)}[/yellow]")
    else:
        console.print(
            f"[green]Added {fetch_result.inserted} and updated {fetch_result.updated} TDocs[/green]",
        )
    return refreshed
