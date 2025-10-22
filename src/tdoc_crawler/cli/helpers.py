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
from tdoc_crawler.models import (
    CrawlLimits,
    PortalCredentials,
    TDocMetadata,
    WorkingGroup,
)

console = Console()
_logger = logging.getLogger(__name__)

DEFAULT_DATABASE_FILENAME = "tdoc_crawler.db"
DOWNLOAD_TIMEOUT = 60
ALLOWED_DOWNLOAD_SCHEMES = ("ftp://", "http://", "https://")


def parse_working_groups(values: list[str] | None) -> list[WorkingGroup]:
    """Parse and normalize working group names, expanding plenary aliases."""
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
    # Try exact match first (case-insensitive)
    cursor = database.connection.execute(
        "SELECT meeting_id FROM meetings WHERE short_name = ? COLLATE NOCASE",
        (meeting_name,),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    # Try normalized name
    normalized = normalize_portal_meeting_name(meeting_name)
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
