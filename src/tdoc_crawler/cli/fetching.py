"""Functions for fetching missing TDocs from the portal."""

from __future__ import annotations

import logging
from pathlib import Path

from rich.console import Console

from tdoc_crawler.crawlers import TDocCrawlResult, fetch_tdoc_metadata
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import PortalCredentials, QueryConfig, TDocMetadata, WorkingGroup

from .helpers import resolve_meeting_id

console = Console()
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
            # Fetch metadata from portal
            portal_data = fetch_tdoc_metadata(tdoc_id, credentials)

            if not portal_data:
                errors.append(f"Portal returned no data for {tdoc_id}")
                continue

            # Resolve meeting_id from meeting name
            meeting_id = None
            meeting_name = portal_data.get("meeting")
            if meeting_name:
                meeting_id = resolve_meeting_id(database, meeting_name)
                if not meeting_id:
                    _logger.warning(f"Could not resolve meeting '{meeting_name}' to meeting_id for {tdoc_id}")

            # Infer working group from TDoc ID
            tdoc_prefix = tdoc_id[0].upper()
            working_group_map = {"R": WorkingGroup.RAN, "S": WorkingGroup.SA, "C": WorkingGroup.CT, "T": WorkingGroup.CT}
            working_group = working_group_map.get(tdoc_prefix, WorkingGroup.RAN)

            # Build TDoc URL (using meeting info if available)
            # For now, use a placeholder URL since we're fetching from portal
            url = f"https://www.3gpp.org/ftp/tsg_{working_group.value.lower()}/.../{tdoc_id}.zip"

            # Create TDocMetadata object (all fields without defaults must be provided)
            metadata = TDocMetadata(
                tdoc_id=tdoc_id.upper(),
                url=url,
                working_group=working_group,
                subgroup=None,
                meeting=meeting_name,
                meeting_id=meeting_id,
                file_size=None,
                title=portal_data.get("title"),
                contact=portal_data.get("contact"),
                tdoc_type=portal_data.get("tdoc_type"),
                for_purpose=portal_data.get("for_purpose"),
                agenda_item=portal_data.get("agenda_item"),
                status=portal_data.get("status"),
                is_revision_of=portal_data.get("is_revision_of"),
                document_type=None,
                checksum=None,
                source_path=None,
                date_created=None,
                validated=True,
                validation_failed=False,
            )

            # Insert/update in database
            inserted, updated = database.upsert_tdoc(metadata)
            if inserted:
                inserted_count += 1
            elif updated:
                updated_count += 1

            _logger.info(f"Successfully fetched and stored {tdoc_id}")

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
