"""Helper functions for CLI operations."""

from __future__ import annotations

import logging
import os
import posixpath
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

import typer
from rich.console import Console

from tdoc_crawler.crawlers import normalize_subgroup_alias, normalize_working_group_alias
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import CrawlLimits, HttpCacheConfig, MeetingQueryConfig, PortalCredentials, SortOrder, TDocMetadata, WorkingGroup

console = Console()
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


def resolve_credentials(
    username: str | None,
    password: str | None,
    prompt: bool,
) -> PortalCredentials | None:
    """Resolve portal credentials from parameters, environment, or prompt."""
    resolved_username = username or os.getenv("EOL_USERNAME")
    resolved_password = password or os.getenv("EOL_PASSWORD")

    if resolved_username and resolved_password:
        return PortalCredentials(username=resolved_username, password=resolved_password)

    if prompt:
        resolved_username = typer.prompt("EOL username")
        resolved_password = typer.prompt("EOL password", hide_input=True)
        return PortalCredentials(username=resolved_username, password=resolved_password)

    return None


def database_path(cache_dir: Path) -> Path:
    """Get database path from cache directory."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / DEFAULT_DATABASE_FILENAME


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


def normalize_portal_meeting_name(portal_meeting: str) -> str:
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


def download_to_path(url: str, destination: Path) -> None:
    """Download a file from URL to destination path."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    lowered = url.lower()
    if not lowered.startswith(ALLOWED_DOWNLOAD_SCHEMES):
        raise ValueError("unsupported-url-scheme")
    with urlopen(url, timeout=DOWNLOAD_TIMEOUT) as response, destination.open("wb") as target:  # noqa: S310
        shutil.copyfileobj(response, target)


def prepare_tdoc_file(metadata: TDocMetadata, cache_dir: Path) -> Path:
    """Prepare TDoc file for opening (download and extract if needed)."""
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
        download_to_path(metadata.url, zip_path)
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
        download_to_path(metadata.url, target_path)
    return target_path


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
