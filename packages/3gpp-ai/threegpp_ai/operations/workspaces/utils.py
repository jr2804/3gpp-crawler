"""Workspace utility functions."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import niquests as requests
from tdoc_crawler.config.settings import ThreeGPPConfig
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.logging import get_logger
from tdoc_crawler.specs.operations.checkout import build_default_spec_sources, checkout_specs_async
from tdoc_crawler.tdocs.models import TDocMetadata
from tdoc_crawler.tdocs.operations.checkout import checkout_tdoc
from tdoc_crawler.tdocs.sources.portal import PortalSource
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec
from tdoc_crawler.utils.normalization import normalize_spec_number, resolve_release_to_full_version

from threegpp_ai.operations.workspace_registry import WorkspaceRegistry

_logger = get_logger(__name__)


def _get_registry() -> WorkspaceRegistry:
    """Get the workspace registry singleton."""
    return WorkspaceRegistry.load()


def delete_ai_folder(ai_path: Path) -> int:
    """Delete an .ai folder and return count of deleted items.

    Args:
        ai_path: Path to the .ai folder.

    Returns:
        Count of items deleted.
    """
    if not ai_path.exists() or not ai_path.is_dir():
        return 0

    count = 0
    try:
        for item in ai_path.rglob("*"):
            if item.is_file():
                item.unlink()
                count += 1
        # Remove .ai folder itself
        ai_path.rmdir()
        count += 1
        _logger.debug("Deleted .ai folder: %s", ai_path)
    except Exception as e:
        _logger.warning("Failed to delete .ai folder %s: %s", ai_path, e)
    return count


def resolve_tdoc_checkout_path(tdoc_id: str, checkout_base: Path) -> Path | None:
    """Resolve a TDoc ID to its checkout path.

    The checkout path follows the 3GPP FTP structure:
    <checkout_base>/<group>/<meeting>/Docs/<tdoc_id>/

    Args:
        tdoc_id: TDoc identifier (e.g., "S4-251971")
        checkout_base: Base checkout directory

    Returns:
        Path to the TDoc checkout folder if found, None otherwise
    """
    # Search for the TDoc in the checkout directory
    # The structure is: <checkout_base>/*/*/Docs/<tdoc_id>/
    for docs_dir in checkout_base.rglob("Docs"):
        tdoc_path = docs_dir / tdoc_id
        if tdoc_path.exists() and tdoc_path.is_dir():
            return tdoc_path
    return None


async def resolve_spec_release_from_db(spec_number: str, requested_release: str, db_file: Path | None = None) -> tuple[str, list[str]]:
    """Resolve a short release string to a full release designation and return version codes.

    Args:
        spec_number: Spec number (e.g., "26.260")
        requested_release: Release version (e.g., "16", "17.0.0")
        db_file: Optional path to database file

    Returns:
        Tuple of (resolved_release, version_codes) where:
        - resolved_release: Full release designation (e.g., "Rel-16")
        - version_codes: List of version codes (e.g., ["h00", "i10"]) for the resolved release
    """
    resolved = requested_release
    version_codes: list[str] = []
    try:
        config = ThreeGPPConfig.from_settings()
        db_path = db_file if db_file is not None else config.path.db_file
        async with SpecDatabase(db_path) as db:
            versions = await db.get_spec_versions(spec_number)
            if versions:
                available_releases = [entry.release for entry in versions if entry.release]
                if available_releases:
                    resolved = resolve_release_to_full_version(requested_release, available_releases)
                    # Extract version codes for the resolved release
                    for entry in versions:
                        if resolved is not None and entry.release != resolved:
                            continue
                        if "-" in entry.version:
                            version_code = entry.version.split("-", 1)[1]
                            version_codes.append(version_code)
    except (OSError, ValueError, sqlite3.Error) as exc:
        _logger.debug("Could not resolve release '%s' for %s: %s", requested_release, spec_number, exc)
    return resolved, version_codes


async def _resolve_tdoc_metadata(tdoc_id: str, db_file: Path | None = None) -> TDocMetadata | None:
    """Resolve TDoc metadata via fallback chain: Database → WhatTheSpec → 3GPP Portal.

    Args:
        tdoc_id: TDoc identifier.
        db_file: Optional database file for metadata lookup.

    Returns:
        TDocMetadata if found, None otherwise.
    """
    metadata: TDocMetadata | None = None

    # Step 1: Check database for existing metadata
    if db_file is not None and db_file.exists():
        try:
            async with TDocDatabase(db_file) as db:
                metadata = await db._get_tdoc(tdoc_id)
                if metadata and metadata.url:
                    _logger.debug(f"Found TDoc {tdoc_id} in database with URL")
        except (OSError, ValueError, sqlite3.Error) as e:
            _logger.debug(f"Database lookup failed for {tdoc_id}: {e}")

    # Step 2: Try WhatTheSpec API if not found in database
    if metadata is None:
        _logger.debug(f"Trying WhatTheSpec API for {tdoc_id}")
        try:
            metadata = resolve_via_whatthespec(tdoc_id)
            if metadata:
                _logger.info(f"Resolved TDoc {tdoc_id} via WhatTheSpec API")
        except (OSError, ValueError, requests.RequestException) as e:
            _logger.debug(f"WhatTheSpec lookup failed for {tdoc_id}: {e}")

    # Step 3: Try 3GPP Portal as final fallback (requires credentials)
    if metadata is None:
        _logger.debug(f"Trying 3GPP Portal for {tdoc_id}")
        try:
            config = ThreeGPPConfig.from_settings()
            if config.credentials.is_valid:
                source = PortalSource(config.credentials)
                metadata = await source.get_tdoc_metadata(tdoc_id)
                if metadata:
                    _logger.info(f"Resolved TDoc {tdoc_id} via 3GPP Portal")
        except (OSError, ValueError, requests.RequestException) as e:
            _logger.debug(f"Portal lookup failed for {tdoc_id}: {e}")

    return metadata


def _checkout_tdoc_if_needed(tdoc_id: str, metadata: TDocMetadata, checkout_base: Path) -> Path | None:
    """Checkout a TDoc if not already checked out.

    Args:
        tdoc_id: TDoc identifier.
        metadata: Resolved TDoc metadata.
        checkout_base: Base checkout directory.

    Returns:
        Path to the checked out TDoc folder, or None if checkout failed.
    """
    # Check if already checked out with actual files
    existing_path = resolve_tdoc_checkout_path(tdoc_id, checkout_base)
    if existing_path:
        # Check if folder has actual document files (not just .ai subfolder)
        has_files = any(
            f.is_file() and f.parent.name != ".ai" and not any(part == ".ai" for part in f.relative_to(existing_path).parts) for f in existing_path.rglob("*")
        )
        if has_files:
            _logger.info(f"TDoc {tdoc_id} already checked out at {existing_path}")
            return existing_path

        # Log what was found for debugging
        all_items = list(existing_path.iterdir())
        _logger.info(
            f"TDoc {tdoc_id} folder exists but has no document files at {existing_path} "
            f"(found: {len(all_items)} items: {[i.name for i in all_items]}), re-downloading..."
        )

    # Checkout the TDoc - returns Path directly or raises exception
    try:
        checkout_path = checkout_tdoc(metadata, checkout_base)
        if checkout_path and checkout_path.exists():
            _logger.info(f"Checked out TDoc {tdoc_id} to {checkout_path}")
            return checkout_path

        _logger.warning(f"Checkout returned invalid path for TDoc {tdoc_id}")
        return None
    except FileNotFoundError as e:
        _logger.warning(f"TDoc {tdoc_id} not found: {e}")
        return None
    except (OSError, ValueError) as e:
        _logger.warning(f"Error checking out TDoc {tdoc_id}: {e}")
        return None


async def checkout_tdoc_to_workspace(
    tdoc_id: str,
    checkout_base: Path,
    workspace: str | None,
    db_file: Path | None = None,
) -> Path | None:
    """Checkout a TDoc and add it to a workspace.

    Uses a fallback chain to resolve TDoc metadata:
    1. Check if already checked out to disk
    2. Check local database for existing metadata with URL
    3. Try WhatTheSpec API (unauthenticated)
    4. Try 3GPP Portal (requires credentials)

    Args:
        tdoc_id: TDoc identifier.
        checkout_base: Base checkout directory.
        workspace: Workspace name.
        db_file: Optional path to database file for metadata lookup.

    Returns:
        Path to the checked out TDoc folder, or None if checkout failed.
    """
    # Resolve metadata via fallback chain
    metadata = await _resolve_tdoc_metadata(tdoc_id, db_file)
    if metadata is None:
        return None

    # Checkout the TDoc
    return _checkout_tdoc_if_needed(tdoc_id, metadata, checkout_base)


async def checkout_spec_to_workspace(
    spec_number: str,
    checkout_base: Path,
    workspace: str | None,
    release: str = "latest",
    db_file: Path | None = None,
) -> Path | None:
    """Checkout a spec and add it to a workspace.

    Args:
        spec_number: Spec number (e.g., "26260" for 26.260)
        checkout_base: Base checkout directory
        workspace: Workspace name
        release: Spec release version (e.g., "16.3.0", "17.0.0") or "latest"
        db_file: Optional path to database file for spec lookup. If None, uses
                CacheManager to resolve the default database path.

    Returns:
        Path to the checked out spec folder, or None if checkout failed
    """
    # Normalize spec number for consistent directory naming
    normalized = normalize_spec_number(spec_number)
    undotted = normalized.replace(".", "")  # e.g., "26.260" -> "26260"
    requested_release = release.strip()
    config = ThreeGPPConfig.from_settings()
    db_path = db_file if db_file is not None else config.path.db_file
    resolved_release, version_codes = await resolve_spec_release_from_db(spec_number, requested_release, db_file=db_file)

    # First check if already checked out with the SAME release version
    specs_dir = checkout_base / "Specs"
    if specs_dir.exists():
        for spec_dir in specs_dir.rglob("*"):
            if not spec_dir.is_dir():
                continue
            dir_name = spec_dir.name
            if normalized not in dir_name and undotted not in dir_name:
                continue
            if version_codes and not any(vc in dir_name for vc in version_codes):
                continue
            _logger.debug("Spec %s (release %s) already checked out at %s", spec_number, requested_release, spec_dir)
            return spec_dir

    # Need to checkout the spec - auto-crawl if not in database
    try:
        async with SpecDatabase(db_path) as db:
            versions = await db.get_spec_versions(normalized)
            if not versions:
                _logger.info("Spec %s not found in database, auto-crawling...", normalized)
                sources = build_default_spec_sources()
                await db.crawl_specs([normalized], resolved_release, sources)
                versions = await db.get_spec_versions(normalized)
                if not versions:
                    _logger.warning("Spec %s not found after crawl - spec may not exist", normalized)
                    return None

            checkout_paths = await checkout_specs_async(
                spec_numbers=[spec_number],
                checkout_dir=checkout_base,
                database=db,
                release=resolved_release,
            )

            if checkout_paths and checkout_paths[0] and checkout_paths[0].exists():
                _logger.info(f"Checked out spec {spec_number} (release {resolved_release}) to {checkout_paths[0]}")
                return checkout_paths[0]

            _logger.warning(f"Failed to checkout spec {spec_number} (release {resolved_release})")
            return None

    except (OSError, ValueError, sqlite3.Error) as e:
        _logger.warning(f"Error checking out spec {spec_number} (release {resolved_release}): {e}")
        return None


def ensure_ai_subfolder(checkout_path: Path) -> Path:
    """Ensure the .ai subfolder exists for processed outputs.

    Args:
        checkout_path: Path to the checked out document folder

    Returns:
        Path to the .ai subfolder
    """
    ai_folder = checkout_path / ".ai"
    ai_folder.mkdir(parents=True, exist_ok=True)
    return ai_folder
