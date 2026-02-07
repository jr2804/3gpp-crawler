"""Helper functions for CLI operations."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

import click
import typer

from tdoc_crawler.crawlers import normalize_subgroup_alias, normalize_working_group_alias
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import CrawlLimits, HttpCacheConfig, MeetingQueryConfig, SortOrder, WorkingGroup
from tdoc_crawler.specs.normalization import normalize_portal_meeting_name

from .console import get_console

console = get_console()
_logger = logging.getLogger(__name__)

DEFAULT_DATABASE_FILENAME = "tdoc_crawler.db"
DOWNLOAD_TIMEOUT = 60
ALLOWED_DOWNLOAD_SCHEMES = ("ftp://", "http://", "https://")


def infer_working_groups_from_subgroups(subgroups: list[str]) -> list[WorkingGroup]:
    """Infer working groups from subgroup codes.

    Args:
        subgroups: List of subgroup codes (e.g., ["S4", "R1"])

    Returns:
        List of inferred working groups without duplicates
    """
    working_groups: list[WorkingGroup] = []
    for subgroup in subgroups:
        # Extract first character to determine working group
        if subgroup and len(subgroup) >= 1:
            first_char = subgroup[0].upper()
            if first_char == "R":
                wg = WorkingGroup.RAN
            elif first_char == "S":
                wg = WorkingGroup.SA
            elif first_char == "C":
                wg = WorkingGroup.CT
            else:
                continue

            if wg not in working_groups:
                working_groups.append(wg)

    return working_groups if working_groups else [WorkingGroup.RAN, WorkingGroup.SA, WorkingGroup.CT]


def parse_working_groups(values: list[str] | None, subgroups: list[str] | None = None) -> list[WorkingGroup]:
    """Parse and normalize working group names, expanding plenary aliases.

    Args:
        values: Explicit working group values from CLI
        subgroups: Optional subgroup list to infer working groups from

    Returns:
        List of working groups to crawl
    """
    if not values:
        # If subgroups are specified but no explicit working groups, infer from subgroups
        if subgroups:
            return infer_working_groups_from_subgroups(subgroups)
        # Otherwise default to all working groups
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


def parse_subgroups(values: list[str] | None) -> list[str] | None:
    """Parse and normalize subgroup aliases to canonical names."""
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


def collect_spec_numbers(specs: list[str] | None, spec_file: Path | None) -> list[str]:
    """Collect spec numbers from CLI arguments or a file."""
    collected: list[str] = []

    if specs:
        for spec in specs:
            if spec == "-":
                # Read from stdin
                for line in sys.stdin:
                    line_stripped = line.strip()
                    if line_stripped:
                        collected.append(line_stripped)
            else:
                collected.append(spec.strip())

    if spec_file and spec_file.exists():
        try:
            with spec_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line_stripped = line.strip()
                    if line_stripped:
                        collected.append(line_stripped)
        except OSError as exc:
            raise click.FileError(str(spec_file), hint=f"Cannot read spec file: {exc}")

    if not collected:
        return []

    # Import here to avoid circular imports
    from tdoc_crawler.specs.normalization import expand_spec_ranges_batch

    try:
        expanded = expand_spec_ranges_batch(collected)
    except ValueError as e:
        raise click.UsageError(str(e))

    return expanded


def build_limits(
    limit_tdocs: int | None,
    limit_meetings: int | None,
    limit_meetings_per_wg: int | None,
    limit_wgs: int | None,
) -> CrawlLimits:
    """Build CrawlLimits configuration from individual parameters."""
    return CrawlLimits(
        limit_tdocs=limit_tdocs,
        limit_meetings=limit_meetings,
        limit_meetings_per_wg=limit_meetings_per_wg,
        limit_wgs=limit_wgs,
    )


def infer_working_groups_from_ids(ids: Iterable[str]) -> list[WorkingGroup]:
    """Infer working groups from TDoc IDs based on first character."""
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


def resolve_meeting_id(database: TDocDatabase, meeting_name: str) -> int | None:
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
    # Query all meetings from database
    config = MeetingQueryConfig(
        cache_dir=database.db_path.parent,
        working_groups=None,
        subgroups=None,
        limit=None,
        order=SortOrder.DESC,
        include_without_files=True,
    )
    all_meetings = database.query_meetings(config)

    def _match_name(candidate: str, cached: str | None) -> bool:
        """Check if candidate matches cached name via fuzzy matching."""
        if not cached:
            return False
        candidate_lower = candidate.lower()
        cached_lower = cached.lower()

        # Exact match
        if candidate_lower == cached_lower:
            return True
        # Candidate is prefix/suffix of cached or vice versa
        return (
            cached_lower.startswith(candidate_lower)
            or cached_lower.endswith(candidate_lower)
            or candidate_lower.startswith(cached_lower)
            or candidate_lower.endswith(cached_lower)
        )

    # Try matches with original and normalized names
    normalized = normalize_portal_meeting_name(meeting_name)
    candidates = [meeting_name]
    if normalized != meeting_name:
        candidates.append(normalized)

    for candidate in candidates:
        for meeting in all_meetings:
            if _match_name(candidate, meeting.short_name):
                return meeting.meeting_id

    return None


def launch_file(path: Path) -> None:
    """Launch file in system's default application."""
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


def resolve_http_cache_config(cache_ttl: int | None = None, cache_refresh_on_access: bool | None = None) -> HttpCacheConfig:
    """Resolve HTTP cache configuration from CLI parameters and environment variables.

    Args:
        cache_ttl: TTL for cache entries (CLI parameter)
        cache_refresh_on_access: Whether to refresh TTL on access (CLI parameter)

    Returns:
        HttpCacheConfig instance with resolved values
    """
    # Check CLI parameters first, then environment variables, then defaults
    if cache_ttl is not None:
        ttl = cache_ttl
    else:
        env_ttl = os.getenv("HTTP_CACHE_TTL")
        ttl = int(env_ttl) if env_ttl else 7200

    # Handle refresh on access - check CLI param, then env var, then default
    if cache_refresh_on_access is not None:
        refresh_on_access = cache_refresh_on_access
    else:
        env_refresh = os.getenv("HTTP_CACHE_REFRESH_ON_ACCESS", "").lower()
        refresh_on_access = env_refresh in ("true", "1", "yes", "on", "t", "y") if env_refresh else True

    return HttpCacheConfig(ttl=ttl, refresh_ttl_on_access=refresh_on_access)
