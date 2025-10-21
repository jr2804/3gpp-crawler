"""Typer-based command line interface for the TDoc crawler."""

from __future__ import annotations

import json
import logging
import os
import posixpath
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Iterable
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

import typer
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from tdoc_crawler.crawlers import MeetingCrawler, TDocCrawler, TDocCrawlResult, fetch_tdoc_metadata
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import (
    CrawlLimits,
    MeetingCrawlConfig,
    MeetingMetadata,
    MeetingQueryConfig,
    OutputFormat,
    PortalCredentials,
    QueryConfig,
    SortOrder,
    TDocCrawlConfig,
    TDocMetadata,
    WorkingGroup,
)

load_dotenv()

app = typer.Typer(help="TDoc crawler - crawl and query structured 3GPP metadata")
console = Console()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _parse_working_groups(values: list[str] | None) -> list[WorkingGroup]:
    """Parse and normalize working group names, expanding plenary aliases."""
    from tdoc_crawler.crawlers import normalize_working_group_alias

    if not values:
        return [WorkingGroup.RAN, WorkingGroup.SA, WorkingGroup.CT]
    resolved: list[WorkingGroup] = []
    for item in values:
        # Try alias normalization first (RP->RAN, SP->SA, CP->CT)
        normalized = normalize_working_group_alias(item)
        try:
            resolved.append(WorkingGroup(normalized.upper()))
        except ValueError as exc:
            console.print(f"[red]Unknown working group: {item}")
            raise typer.Exit(code=2) from exc
    if not resolved:
        console.print("[red]No valid working groups specified")
        raise typer.Exit(code=2)
    return resolved


def _parse_subgroups(values: list[str] | None) -> list[str] | None:
    """Parse and normalize subgroup aliases to canonical names."""
    from tdoc_crawler.crawlers import normalize_subgroup_alias

    if not values:
        return None

    resolved: list[str] = []
    for item in values:
        normalized = normalize_subgroup_alias(item)
        if not normalized:
            console.print(f"[red]Unknown subgroup: {item}")
            raise typer.Exit(code=2)
        resolved.extend(normalized)

    return resolved

    # Remove duplicates while preserving order
    seen = set()
    unique_resolved = []
    for name in resolved:
        if name not in seen:
            seen.add(name)
            unique_resolved.append(name)

    return unique_resolved if unique_resolved else None


def _build_limits(
    limit_tdocs: int | None,
    limit_meetings: int | None,
    limit_meetings_per_wg: int | None,
    limit_wgs: int | None,
) -> CrawlLimits:
    return CrawlLimits(
        limit_tdocs=limit_tdocs,
        limit_meetings=limit_meetings,
        limit_meetings_per_wg=limit_meetings_per_wg,
        limit_wgs=limit_wgs,
    )


def _resolve_credentials(
    username: str | None,
    password: str | None,
    prompt: bool,
) -> PortalCredentials | None:
    resolved_username = username or os.getenv("EOL_USERNAME")
    resolved_password = password or os.getenv("EOL_PASSWORD")

    if resolved_username and resolved_password:
        return PortalCredentials(username=resolved_username, password=resolved_password)

    if prompt:
        resolved_username = typer.prompt("EOL username")
        resolved_password = typer.prompt("EOL password", hide_input=True)
        return PortalCredentials(username=resolved_username, password=resolved_password)

    return None


def _database_path(cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "tdoc_crawler.db"


DOWNLOAD_TIMEOUT = 60
ALLOWED_DOWNLOAD_SCHEMES = ("ftp://", "http://", "https://")


def _infer_working_groups_from_ids(ids: Iterable[str]) -> list[WorkingGroup]:
    mapping = {
        "R": WorkingGroup.RAN,
        "S": WorkingGroup.SA,
        "T": WorkingGroup.CT,
        "C": WorkingGroup.CT,
    }
    resolved: list[WorkingGroup] = []
    for value in ids:
        if not value:
            continue
        group = mapping.get(value[0].upper())
        if group and group not in resolved:
            resolved.append(group)
    return resolved or [WorkingGroup.RAN, WorkingGroup.SA, WorkingGroup.CT]


def _download_to_path(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    lowered = url.lower()
    if not lowered.startswith(ALLOWED_DOWNLOAD_SCHEMES):
        raise ValueError("unsupported-url-scheme")
    with urlopen(url, timeout=DOWNLOAD_TIMEOUT) as response, destination.open("wb") as target:  # noqa: S310
        shutil.copyfileobj(response, target)


def _prepare_tdoc_file(metadata: TDocMetadata, cache_dir: Path) -> Path:
    downloads_dir = cache_dir / "tdocs"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    path = urlparse(metadata.url).path
    filename = posixpath.basename(path)
    suffix = Path(filename).suffix.lower()

    if suffix == ".zip":
        extract_dir = downloads_dir / metadata.tdoc_id
        if extract_dir.exists():
            files = sorted(p for p in extract_dir.rglob("*") if p.is_file())
            if files:
                return files[0]
            shutil.rmtree(extract_dir)
        zip_path = downloads_dir / f"{metadata.tdoc_id}.zip"
        _download_to_path(metadata.url, zip_path)
        try:
            with zipfile.ZipFile(zip_path) as archive:
                archive.extractall(extract_dir)
        finally:
            with suppress(FileNotFoundError):
                zip_path.unlink()
        files = sorted(p for p in extract_dir.rglob("*") if p.is_file())
        if not files:
            raise FileNotFoundError("no-files-in-archive")
        return files[0]

    target_suffix = suffix or ""
    target_name = filename if filename else f"{metadata.tdoc_id}{target_suffix or '.bin'}"
    target_path = downloads_dir / target_name
    if not target_path.exists():
        _download_to_path(metadata.url, target_path)
    return target_path


def _launch_file(path: Path) -> None:
    if not path.exists():
        console.print(f"[red]File not found: {path}")
        raise typer.Exit(code=1)
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]  # noqa: S606
        elif sys.platform == "darwin":
            open_cmd = Path("/usr/bin/open")
            if open_cmd.exists():
                subprocess.run([str(open_cmd), str(path)], check=False)  # noqa: S603
            else:
                console.print("[yellow]/usr/bin/open not available[/yellow]")
        else:
            xdg_cmd = Path("/usr/bin/xdg-open")
            if xdg_cmd.exists():
                subprocess.run([str(xdg_cmd), str(path)], check=False)  # noqa: S603
            else:
                console.print("[yellow]xdg-open command not available[/yellow]")
    except OSError as exc:
        console.print(f"[red]Failed to open file: {exc}")
        raise typer.Exit(code=1) from exc


_logger = logging.getLogger(__name__)


def _normalize_portal_meeting_name(portal_meeting: str) -> str:
    """Normalize portal meeting name to database format.

    The portal uses format like "SA4#133-e" while the database uses "S4-133-e".
    This function converts portal format to database format.

    Args:
        portal_meeting: Meeting name from portal (e.g., "SA4#133-e")

    Returns:
        Normalized meeting name (e.g., "S4-133-e")
    """
    # Replace "SA4#" with "S4-", "RAN1#" with "R1-", etc.
    normalized = portal_meeting.replace("#", "-")

    # Handle full working group names (SA, RAN, CT)
    for full_name, short_prefix in [("SA", "S"), ("RAN", "R"), ("CT", "C")]:
        # Match patterns like "SA4-" and replace with "S4-"
        if normalized.startswith(f"{full_name}"):
            # Extract the subgroup number if present
            for i, char in enumerate(normalized[len(full_name) :]):
                if not char.isdigit():
                    subgroup_num = normalized[len(full_name) : len(full_name) + i] if i > 0 else ""
                    rest = normalized[len(full_name) + i :]
                    if subgroup_num:
                        normalized = f"{short_prefix}{subgroup_num}{rest}"
                    break
            break

    return normalized


def _resolve_meeting_id(database: TDocDatabase, meeting_name: str) -> int | None:
    """Resolve meeting name to meeting_id from database.

    Uses fuzzy matching to handle variations in meeting names:
    - Exact match (case-insensitive)
    - Normalized name match
    - Prefix/suffix matching for variations like "SA4-e" vs "3GPPSA4-e"

    Args:
        database: Database connection
        meeting_name: Meeting identifier (e.g., "SA4#133-e" or "S4-133-e")

    Returns:
        Meeting ID if found, None otherwise
    """
    # Try exact match first (case-insensitive)
    cursor = database.connection.execute(
        "SELECT meeting_id FROM meetings WHERE short_name = ? COLLATE NOCASE",
        (meeting_name,),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    # Try normalized name
    normalized = _normalize_portal_meeting_name(meeting_name)
    if normalized != meeting_name:
        cursor = database.connection.execute(
            "SELECT meeting_id FROM meetings WHERE short_name = ? COLLATE NOCASE",
            (normalized,),
        )
        row = cursor.fetchone()
        if row:
            return row[0]

    # Try fuzzy matching with meeting names in database
    # Use SQL LIKE for better performance
    candidate_lower = meeting_name.lower()
    normalized_lower = normalized.lower()

    # Try fuzzy patterns with candidate
    for pattern in [
        f"{candidate_lower}%",  # candidate is prefix of cached
        f"%{candidate_lower}",  # candidate is suffix of cached
    ]:
        cursor = database.connection.execute(
            "SELECT meeting_id FROM meetings WHERE LOWER(short_name) LIKE ? LIMIT 1",
            (pattern,),
        )
        row = cursor.fetchone()
        if row:
            return row[0]

    # Try fuzzy patterns with normalized candidate
    if normalized_lower != candidate_lower:
        for pattern in [
            f"{normalized_lower}%",  # normalized is prefix of cached
            f"%{normalized_lower}",  # normalized is suffix of cached
        ]:
            cursor = database.connection.execute(
                "SELECT meeting_id FROM meetings WHERE LOWER(short_name) LIKE ? LIMIT 1",
                (pattern,),
            )
            row = cursor.fetchone()
            if row:
                return row[0]

    # Try reverse patterns: cached is prefix/suffix of candidate
    cursor = database.connection.execute("SELECT meeting_id, short_name FROM meetings")
    for meeting_id, cached_name in cursor.fetchall():
        cached_lower = cached_name.lower()
        # Check if cached_name is prefix of candidate
        if candidate_lower.startswith(cached_lower):
            return meeting_id
        # Check if cached_name is suffix of candidate
        if candidate_lower.endswith(cached_lower):
            return meeting_id
        # Also check with normalized candidate
        if normalized_lower != candidate_lower:
            if normalized_lower.startswith(cached_lower):
                return meeting_id
            if normalized_lower.endswith(cached_lower):
                return meeting_id

    return None


def _fetch_missing_tdocs(
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
                meeting_id = _resolve_meeting_id(database, meeting_name)
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


def _maybe_fetch_missing_tdocs(
    database: TDocDatabase,
    cache_dir: Path,
    config: QueryConfig,
    results: list[TDocMetadata],
    credentials: PortalCredentials | None = None,
) -> list[TDocMetadata]:
    if not config.tdoc_ids:
        return results
    requested = [value.upper() for value in config.tdoc_ids]
    found = {item.tdoc_id for item in results}
    missing = [value for value in requested if value not in found]
    if not missing:
        return results

    console.print(f"[cyan]Fetching missing TDocs: {', '.join(missing)}[/cyan]")
    fetch_result = _fetch_missing_tdocs(database, cache_dir, missing, credentials)
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


@app.command()
def crawl(
    cache_dir: Path = typer.Option(Path.home() / ".tdoc-crawler", "--cache-dir", "-c", help="Cache directory"),
    working_group: list[str] | None = typer.Option(None, "--working-group", "-w", help="Working groups to crawl"),
    subgroup: list[str] | None = typer.Option(None, "--sub-group", "-s", help="Filter by sub-working group"),
    incremental: bool = typer.Option(True, "--incremental/--full", help="Toggle incremental mode"),
    limit_tdocs: int | None = typer.Option(None, "--limit-tdocs", help="Limit number of TDocs"),
    limit_meetings: int | None = typer.Option(None, "--limit-meetings", help="Limit meetings considered"),
    limit_meetings_per_wg: int | None = typer.Option(None, "--limit-meetings-per-wg", help="Limit meetings per working group"),
    limit_wgs: int | None = typer.Option(None, "--limit-wgs", help="Limit number of working groups"),
    max_retries: int = typer.Option(3, "--max-retries", help="HTTP connection retry attempts"),
    timeout: int = typer.Option(30, "--timeout", help="HTTP request timeout seconds"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    working_groups = _parse_working_groups(working_group)
    subgroups = _parse_subgroups(subgroup)
    limits = _build_limits(limit_tdocs, limit_meetings, limit_meetings_per_wg, limit_wgs)
    config = TDocCrawlConfig(
        cache_dir=cache_dir,
        working_groups=working_groups,
        subgroups=subgroups,
        meeting_ids=None,
        start_date=None,
        end_date=None,
        incremental=incremental,
        force_revalidate=False,
        workers=4,
        max_retries=max_retries,
        timeout=timeout,
        verbose=verbose,
        limits=limits,
        target_ids=None,
        credentials=None,
    )

    database_path = _database_path(config.cache_dir)

    # Build descriptive message
    scope_parts = []
    if subgroups:
        scope_parts.append(f"subgroups: {', '.join(subgroups)}")
    else:
        scope_parts.append(f"working groups: {', '.join(wg.value for wg in working_groups)}")
    console.print(f"[cyan]Crawling TDocs ({', '.join(scope_parts)})[/cyan]")

    if config.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    with TDocDatabase(database_path) as database:
        crawler = TDocCrawler(database)
        crawl_id = database.log_crawl_start("tdoc", config.working_groups, config.incremental)
        result = crawler.crawl(config)
        database.log_crawl_end(
            crawl_id,
            items_added=result.inserted,
            items_updated=result.updated,
            errors_count=len(result.errors),
        )

    console.print(f"[green]Processed {result.processed} TDocs[/green]")
    console.print(f"[green]Inserted {result.inserted}, updated {result.updated}[/green]")
    if result.errors:
        console.print(f"[yellow]{len(result.errors)} issues detected[/yellow]")
        for error in result.errors[:5]:
            console.print(f"  - {error}")


@app.command("crawl-meetings")
def crawl_meetings(
    cache_dir: Path = typer.Option(Path.home() / ".tdoc-crawler", "--cache-dir", "-c", help="Cache directory"),
    working_group: list[str] | None = typer.Option(None, "--working-group", "-w", help="Working groups to crawl"),
    incremental: bool = typer.Option(True, "--incremental/--full", help="Toggle incremental mode"),
    limit_meetings: int | None = typer.Option(None, "--limit-meetings", help="Limit meetings overall"),
    limit_meetings_per_wg: int | None = typer.Option(None, "--limit-meetings-per-wg", help="Limit meetings per working group"),
    limit_wgs: int | None = typer.Option(None, "--limit-wgs", help="Limit number of working groups"),
    max_retries: int = typer.Option(3, "--max-retries", help="HTTP retry attempts"),
    timeout: int = typer.Option(30, "--timeout", help="HTTP timeout seconds"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    eol_username: str | None = typer.Option(None, "--eol-username", help="ETSI Online account username"),
    eol_password: str | None = typer.Option(None, "--eol-password", help="ETSI Online account password"),
    prompt_credentials: bool = typer.Option(True, "--prompt-credentials/--no-prompt-credentials", help="Prompt for credentials when missing"),
) -> None:
    working_groups = _parse_working_groups(working_group)
    limits = _build_limits(None, limit_meetings, limit_meetings_per_wg, limit_wgs)
    credentials = _resolve_credentials(eol_username, eol_password, prompt_credentials)
    config = MeetingCrawlConfig(
        cache_dir=cache_dir,
        working_groups=working_groups,
        incremental=incremental,
        max_retries=max_retries,
        timeout=timeout,
        verbose=verbose,
        limits=limits,
        credentials=credentials,
    )

    database_path = _database_path(config.cache_dir)
    console.print(f"[cyan]Crawling meetings for {', '.join(wg.value for wg in working_groups)}[/cyan]")

    if config.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    with TDocDatabase(database_path) as database:
        crawler = MeetingCrawler(database)
        crawl_id = database.log_crawl_start("meeting", config.working_groups, config.incremental)
        result = crawler.crawl(config)
        database.log_crawl_end(
            crawl_id,
            items_added=result.inserted,
            items_updated=result.updated,
            errors_count=len(result.errors),
        )

    console.print(f"[green]Processed {result.processed} meetings[/green]")
    console.print(f"[green]Inserted {result.inserted}, updated {result.updated}[/green]")
    if result.errors:
        console.print(f"[yellow]{len(result.errors)} issues detected[/yellow]")
        for error in result.errors[:5]:
            console.print(f"  - {error}")


@app.command()
def query(
    tdoc_ids: list[str] | None = typer.Argument(None, help="TDoc identifiers to query"),
    cache_dir: Path = typer.Option(Path.home() / ".tdoc-crawler", "--cache-dir", "-c", help="Cache directory"),
    working_group: list[str] | None = typer.Option(None, "--working-group", "-w", help="Filter by working group"),
    output_format: str = typer.Option(OutputFormat.TABLE.value, "--output", "-o", help="Output format"),
    limit: int | None = typer.Option(None, "--limit", "-l", help="Maximum number of rows"),
    order: str = typer.Option(SortOrder.DESC.value, "--order", help="Sort order (asc|desc)"),
    start_date: str | None = typer.Option(None, "--start-date", help="Filter from ISO timestamp"),
    end_date: str | None = typer.Option(None, "--end-date", help="Filter until ISO timestamp"),
    no_fetch: bool = typer.Option(False, "--no-fetch", help="Disable automatic fetching of missing TDocs from portal"),
    eol_username: str | None = typer.Option(None, "--eol-username", help="ETSI Online Account username"),
    eol_password: str | None = typer.Option(None, "--eol-password", help="ETSI Online Account password"),
) -> None:
    working_groups = _parse_working_groups(working_group)
    try:
        start = datetime.fromisoformat(start_date) if start_date else None
    except ValueError as exc:
        console.print("[red]Invalid start date format; use ISO-8601")
        raise typer.Exit(code=2) from exc
    try:
        end = datetime.fromisoformat(end_date) if end_date else None
    except ValueError as exc:
        console.print("[red]Invalid end date format; use ISO-8601")
        raise typer.Exit(code=2) from exc

    try:
        sort_order = SortOrder(order.lower())
    except ValueError as exc:
        console.print("[red]Invalid order value; use asc or desc")
        raise typer.Exit(code=2) from exc

    config = QueryConfig(
        cache_dir=cache_dir,
        output_format=output_format,
        tdoc_ids=tdoc_ids,
        working_groups=working_groups,
        start_date=start,
        end_date=end,
        limit=limit,
        order=sort_order,
    )

    # Resolve credentials (only if --no-fetch is not set)
    credentials = None
    if not no_fetch:
        credentials = _resolve_credentials(eol_username, eol_password, prompt=True)

    database_path = _database_path(config.cache_dir)
    with TDocDatabase(database_path) as database:
        results = database.query_tdocs(config)
        if not no_fetch:
            results = _maybe_fetch_missing_tdocs(database, config.cache_dir, config, results, credentials)

    if not results:
        console.print("[yellow]No TDocs found[/yellow]")
        return

    if config.output_format is OutputFormat.JSON:
        console.print(json.dumps([_tdoc_to_dict(result) for result in results], indent=2))
    elif config.output_format is OutputFormat.YAML:
        console.print(yaml.dump([_tdoc_to_dict(result) for result in results], sort_keys=False))
    else:
        _print_tdoc_table(results)


@app.command("query-meetings")
def query_meetings(
    cache_dir: Path = typer.Option(Path.home() / ".tdoc-crawler", "--cache-dir", "-c", help="Cache directory"),
    working_group: list[str] | None = typer.Option(None, "--working-group", "-w", help="Filter by working group"),
    subgroup: list[str] | None = typer.Option(None, "--sub-group", "-s", help="Filter by sub-working group"),
    output_format: str = typer.Option(OutputFormat.TABLE.value, "--output", "-o", help="Output format"),
    limit: int | None = typer.Option(None, "--limit", "-l", help="Maximum number of rows"),
    order: str = typer.Option(SortOrder.DESC.value, "--order", help="Sort order (asc|desc)"),
    include_without_files: bool = typer.Option(False, "--include-without-files", help="Include meetings without files URLs"),
) -> None:
    working_groups = _parse_working_groups(working_group)
    subgroups = _parse_subgroups(subgroup)
    try:
        sort_order_meetings = SortOrder(order.lower())
    except ValueError as exc:
        console.print("[red]Invalid order value; use asc or desc")
        raise typer.Exit(code=2) from exc

    config = MeetingQueryConfig(
        cache_dir=cache_dir,
        working_groups=working_groups,
        subgroups=subgroups,
        limit=limit,
        order=sort_order_meetings,
        include_without_files=include_without_files,
    )

    database_path = _database_path(config.cache_dir)
    with TDocDatabase(database_path) as database:
        meetings = database.query_meetings(config)

    if not meetings:
        console.print("[yellow]No meetings found[/yellow]")
        return

    try:
        output = OutputFormat(output_format.lower())
    except ValueError as exc:
        console.print("[red]Invalid output format; use table, json, or yaml")
        raise typer.Exit(code=2) from exc
    if output is OutputFormat.JSON:
        console.print(json.dumps([_meeting_to_dict(meeting) for meeting in meetings], indent=2))
    elif output is OutputFormat.YAML:
        console.print(yaml.dump([_meeting_to_dict(meeting) for meeting in meetings], sort_keys=False))
    else:
        _print_meeting_table(meetings)


@app.command("open")
def open_tdoc(
    tdoc_id: str = typer.Argument(..., help="TDoc identifier to download and open"),
    cache_dir: Path = typer.Option(Path.home() / ".tdoc-crawler", "--cache-dir", "-c", help="Cache directory"),
) -> None:
    normalized_id = tdoc_id.strip().upper()
    config = QueryConfig(
        cache_dir=cache_dir,
        tdoc_ids=[normalized_id],
    )

    database_path = _database_path(cache_dir)
    with TDocDatabase(database_path) as database:
        results = database.query_tdocs(config)
        results = _maybe_fetch_missing_tdocs(database, cache_dir, config, results)
        if not results:
            console.print(f"[red]TDoc {normalized_id} not found[/red]")
            raise typer.Exit(code=1)
        metadata = results[0]

    try:
        target_file = _prepare_tdoc_file(metadata, cache_dir)
    except (FileNotFoundError, OSError, ValueError, zipfile.BadZipFile) as exc:
        console.print(f"[red]Failed to prepare TDoc {normalized_id}: {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]Opening {target_file}")
    _launch_file(target_file)


@app.command()
def stats(
    cache_dir: Path = typer.Option(Path.home() / ".tdoc-crawler", "--cache-dir", "-c", help="Cache directory"),
) -> None:
    database_path = _database_path(cache_dir)
    if not database_path.exists():
        console.print(f"[red]Database not found: {database_path}[/red]")
        raise typer.Exit(code=1)

    with TDocDatabase(database_path) as database:
        stats_dict = database.get_statistics()

    table = Table(title="TDoc database statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="magenta")

    table.add_row("Total TDocs", str(stats_dict.get("total_tdocs", 0)))
    for wg, count in stats_dict.get("by_working_group", {}).items():
        table.add_row(f"  {wg}", str(count))
    table.add_row("Last 24 hours", str(stats_dict.get("last_24_hours", 0)))
    table.add_row(
        "Date range",
        f"{stats_dict.get('date_first', 'N/A')} -> {stats_dict.get('date_last', 'N/A')}",
    )
    table.add_row("Unique document types", str(stats_dict.get("unique_document_types", 0)))

    console.print(table)


def _tdoc_to_dict(result: TDocMetadata) -> dict[str, object]:
    return {
        "tdoc_id": result.tdoc_id,
        "url": result.url,
        "working_group": result.working_group.value,
        "subgroup": result.subgroup,
        "meeting": result.meeting,
        "meeting_id": result.meeting_id,
        "file_size": result.file_size,
        "document_type": result.document_type,
        "checksum": result.checksum,
        "source_path": result.source_path,
        "date_created": result.date_created.isoformat() if result.date_created else None,
        "date_retrieved": result.date_retrieved.isoformat(),
    }


def _meeting_to_dict(meeting: MeetingMetadata) -> dict[str, object]:
    return {
        "meeting_id": meeting.meeting_id,
        "working_group": meeting.working_group.value,
        "subgroup": meeting.subgroup,
        "short_name": meeting.short_name,
        "title": meeting.title,
        "start_date": meeting.start_date.isoformat() if meeting.start_date else None,
        "end_date": meeting.end_date.isoformat() if meeting.end_date else None,
        "location": meeting.location,
        "files_url": meeting.files_url,
        "portal_url": meeting.portal_url,
    }


def _print_tdoc_table(results: list[TDocMetadata]) -> None:
    table = Table(title=f"TDoc results ({len(results)} rows)")
    table.add_column("TDoc", style="cyan")
    table.add_column("WG", style="magenta")
    table.add_column("Subgroup", style="yellow")
    table.add_column("Meeting", style="green")
    table.add_column("Size (KB)", justify="right", style="blue")

    for result in results[:100]:
        size_kb = f"{result.file_size // 1024}" if result.file_size else "?"
        table.add_row(
            result.tdoc_id,
            result.working_group.value,
            result.subgroup or "-",
            result.meeting or "-",
            size_kb,
        )

    console.print(table)


def _print_meeting_table(results: list[MeetingMetadata]) -> None:
    table = Table(title=f"Meetings ({len(results)} rows)")
    table.add_column("Meeting", style="cyan")
    table.add_column("WG", style="magenta")
    table.add_column("Subgroup", style="yellow")
    table.add_column("Dates", style="green")
    table.add_column("Location", style="blue")
    table.add_column("Files", style="white")

    for meeting in results[:100]:
        date_range = (
            " - ".join(
                filter(
                    None,
                    [
                        meeting.start_date.isoformat() if meeting.start_date else None,
                        meeting.end_date.isoformat() if meeting.end_date else None,
                    ],
                )
            )
            or "-"
        )
        table.add_row(
            meeting.short_name,
            meeting.working_group.value,
            meeting.subgroup or "-",
            date_range,
            meeting.location or "-",
            meeting.files_url or "-",
        )

    console.print(table)


if __name__ == "__main__":
    pass
# end of file
