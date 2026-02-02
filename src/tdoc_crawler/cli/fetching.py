"""Functions for fetching missing TDocs from the portal."""

from __future__ import annotations

import logging
from pathlib import Path

from tdoc_crawler.crawlers import TDocCrawlResult, fetch_tdoc_metadata
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import PortalCredentials, QueryConfig, TDocMetadata

from .console import get_console
from .helpers import resolve_meeting_id

console = get_console()
_logger = logging.getLogger(__name__)


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

    if not credentials:
        errors.append("Portal credentials required for targeted fetch. Set EOL_USERNAME and EOL_PASSWORD.")
        return TDocCrawlResult(processed=len(missing_ids), inserted=0, updated=0, errors=errors)

    inserted_count = 0
    updated_count = 0

    for tdoc_id in missing_ids:
        try:
            # Fetch metadata from portal (now returns TDocMetadata directly)
            metadata = fetch_tdoc_metadata(tdoc_id, credentials)

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

        except Exception as exc:
            error_msg = f"Failed to fetch {tdoc_id}: {exc}"
            _logger.exception(error_msg)
            errors.append(error_msg)

    return TDocCrawlResult(
        processed=len(missing_ids),
        inserted=inserted_count,
        updated=updated_count,
        errors=errors,
    )


def maybe_fetch_missing_tdocs(
    database: TDocDatabase,
    cache_dir: Path,
    config: QueryConfig,
    results: list[TDocMetadata],
    credentials: PortalCredentials | None = None,
) -> list[TDocMetadata]:
    """Check for missing TDocs and fetch them if needed.

    Args:
        database: Database connection
        cache_dir: Cache directory path
        config: Query configuration
        results: Current query results
        credentials: Portal credentials (optional)

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

    console.print(f"[cyan]Fetching missing TDocs: {', '.join(missing)}[/cyan]")
    fetch_result = fetch_missing_tdocs(database, cache_dir, missing, credentials)
    if fetch_result.errors:
        console.print(f"[yellow]{len(fetch_result.errors)} issues detected during targeted crawl[/yellow]")
        for error in fetch_result.errors[:3]:
            console.print(f"  - {error}")

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
