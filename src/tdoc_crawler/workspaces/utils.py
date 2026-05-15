"""Workspace utility functions.

Includes checkout operations and release resolution for workspaces.
"""

from __future__ import annotations

from pathlib import Path

import niquests as requests

from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.config.workspace_registry import WorkspaceRegistry
from tdoc_crawler.database.oxyde_models import TDocMetadata
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.database.tdocs import TDocDatabase
from tdoc_crawler.logging import get_logger
from tdoc_crawler.specs.operations.checkout import (
    build_default_spec_sources,
    checkout_specs_async,
)
from tdoc_crawler.tdocs.operations.checkout import checkout_tdoc
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec
from tdoc_crawler.utils.normalization import (
    normalize_release_version,
    normalize_spec_number,
    normalize_tdoc_id,
)

_logger = get_logger(__name__)


def _get_registry() -> WorkspaceRegistry:
    """Get the workspace registry singleton."""
    return WorkspaceRegistry.load()


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


async def resolve_spec_release_from_db(
    spec_number: str,
    requested_release: str,
    db_file: Path | None = None,
    *,
    auto_crawl: bool = False,
) -> tuple[str, list[str]]:
    """Resolve a short release string to a full version from the spec database.

    Given a requested release like "19" or "19.1", finds the closest
    matching version from the database (e.g., "19.0.0") and returns it
    along with any version codes. If "latest" is requested, returns the
    most recent version available in the database.

    Args:
        spec_number: Spec number (e.g., "26.260").
        requested_release: Release version (e.g., "16", "17.0.0", or "latest").
        db_file: Optional path to database file. If None, uses PathConfig default.
        auto_crawl: If True, crawl spec metadata from 3GPP when DB has no version info.

    Returns:
        Tuple of (resolved_version, version_codes) where:
        - resolved_version: Full version designation (e.g., "19.0.0")
        - version_codes: List of version codes for the resolved release (may be empty).
    """
    resolved = requested_release
    version_codes: list[str] = []

    # Normalize spec number to dotted format (e.g., "26260" -> "26.260")
    normalized_spec = normalize_spec_number(spec_number)

    # Handle "latest" - find the most recent version from database
    if requested_release.lower() == "latest":
        db_path = db_file if db_file is not None else PathConfig().db_file
        if db_path is not None and db_path.exists():
            try:
                async with SpecDatabase(db_path) as db:
                    versions = await db.get_spec_versions(normalized_spec)
                    if versions:
                        # Sort versions and pick the latest (assuming format like "19.1.0")
                        # Sort by splitting into parts and comparing numerically
                        def version_sort_key(v: object) -> tuple[int, ...]:
                            v_str = str(v.version) if hasattr(v, "version") else ""
                            parts = v_str.split(".") if v_str else []
                            return tuple(int(p) if p.isdigit() else 0 for p in parts)

                        latest = max(versions, key=version_sort_key)
                        resolved = str(latest.version)
                        if "-" in resolved:
                            version_codes.append(resolved.split("-", 1)[1])
                        return resolved, version_codes
            except (OSError, ValueError) as exc:
                _logger.debug(
                    "Could not resolve 'latest' for spec %s: %s",
                    spec_number,
                    exc,
                )
        if auto_crawl and resolved.lower() in ("latest", requested_release.lower()):
            resolved, version_codes = await _auto_crawl_and_resolve(
                normalized_spec,
                requested_release,
                db_path=db_path,
                db_file=db_file,
            )
        return resolved, version_codes

    # Normal release resolution (not "latest")
    db_path = db_file if db_file is not None else PathConfig().db_file
    if db_path is None or not db_path.exists():
        if auto_crawl:
            return await _auto_crawl_and_resolve(
                normalized_spec,
                requested_release,
                db_path=db_path,
                db_file=db_file,
            )
        return resolved, version_codes

    try:
        async with SpecDatabase(db_path) as db:
            versions = await db.get_spec_versions(normalized_spec)
            if versions:
                requested_normalized = normalize_release_version(requested_release)
                requested_major = requested_normalized.split(".")[0] if "." in requested_normalized else requested_release
                matching = [v for v in versions if v.version and str(v.version).split(".")[0] == requested_major]

                if matching:
                    resolved = str(matching[0].version)
                    version_codes.extend(str(v.version).split("-", 1)[1] for v in matching if "-" in str(v.version))
            elif auto_crawl:
                return await _auto_crawl_and_resolve(
                    normalized_spec,
                    requested_release,
                    db=db,
                    db_path=db_path,
                    db_file=db_file,
                )
    except (OSError, ValueError) as exc:
        _logger.debug(
            "Could not resolve release '%s' for spec %s: %s",
            requested_release,
            spec_number,
            exc,
        )

    return resolved, version_codes


async def _auto_crawl_and_resolve(
    normalized_spec: str,
    requested_release: str,
    db: SpecDatabase | None = None,
    db_path: Path | None = None,
    db_file: Path | None = None,
) -> tuple[str, list[str]]:
    """Crawl spec metadata from 3GPP, store versions, then retry resolution."""
    try:
        sources = build_default_spec_sources()
        effective_db = db_path if db_path is not None else PathConfig().db_file
        if effective_db is None:
            return requested_release, []
        if db is not None:
            await db.crawl_specs([normalized_spec], requested_release, sources)
        else:
            async with SpecDatabase(effective_db) as inner_db:
                await inner_db.crawl_specs([normalized_spec], requested_release, sources)
        return await resolve_spec_release_from_db(
            normalized_spec,
            requested_release,
            db_file=db_file,
            auto_crawl=False,
        )
    except Exception as exc:
        _logger.debug("Auto-crawl failed for spec %s: %s", normalized_spec, exc)
        return requested_release, []


async def checkout_tdoc_to_workspace(
    tdoc_id: str,
    checkout_base: Path,
    db_file: Path | None = None,
) -> Path | None:
    """Checkout a TDoc and return its checkout path.

    Uses a fallback chain to resolve TDoc metadata:
    1. Check local database for existing metadata
    2. Try WhatTheSpec API (unauthenticated)

    Args:
        tdoc_id: TDoc identifier.
        checkout_base: Base checkout directory.
        db_file: Optional path to database file.

    Returns:
        Path to the checked out TDoc folder, or None if checkout failed.
    """
    normalized_id = normalize_tdoc_id(tdoc_id)
    if normalized_id is None:
        return None

    # Check if already checked out
    existing = resolve_tdoc_checkout_path(normalized_id, checkout_base)
    if existing is not None:
        # Verify the folder has actual document files
        has_files = any(
            f.is_file() and f.parent.name != ".ai" and not any(part == ".ai" for part in f.relative_to(existing).parts) for f in existing.rglob("*")
        )
        if has_files:
            _logger.debug("TDoc %s already checked out at %s", normalized_id, existing)
            return existing
        _logger.info(
            "TDoc %s folder exists but has no document files, re-downloading...",
            normalized_id,
        )

    # Resolve metadata: Step 1 — database
    metadata: TDocMetadata | None = None
    db_path = db_file if db_file is not None else PathConfig().db_file
    if db_path is not None and db_path.exists():
        try:
            async with TDocDatabase(db_path) as db:
                metadata = await db._get_tdoc(normalized_id)
        except (OSError, ValueError) as exc:
            _logger.debug("Database lookup failed for %s: %s", normalized_id, exc)

    # Resolve metadata: Step 2 — WhatTheSpec
    if metadata is None:
        try:
            metadata = resolve_via_whatthespec(normalized_id)
            if metadata is not None:
                _logger.info("Resolved TDoc %s via WhatTheSpec API", normalized_id)
        except (OSError, ValueError, requests.RequestException) as exc:
            _logger.debug("WhatTheSpec lookup failed for %s: %s", normalized_id, exc)

    if metadata is None:
        _logger.warning("Could not resolve TDoc %s via any source", normalized_id)
        return None

    # Checkout the TDoc
    try:
        checkout_path = checkout_tdoc(metadata, checkout_base)
        if checkout_path is not None and checkout_path.exists():
            _logger.info("Checked out TDoc %s to %s", normalized_id, checkout_path)
            return checkout_path
        _logger.warning("Checkout returned invalid path for TDoc %s", normalized_id)
        return None
    except (FileNotFoundError, OSError, ValueError) as exc:
        _logger.warning("Error checking out TDoc %s: %s", normalized_id, exc)
        return None


async def checkout_spec_to_workspace(
    spec_number: str,
    checkout_base: Path,
    release: str = "latest",
    db_file: Path | None = None,
) -> Path | None:
    """Checkout a spec and return its checkout path.

    Auto-crawls if spec not in database.

    Args:
        spec_number: Spec number (e.g., "26260" for TS 26.260).
        checkout_base: Base checkout directory.
        release: Spec release version (e.g., "19", "19.0.0") or "latest".
        db_file: Optional path to database file.

    Returns:
        Path to the checked out spec folder, or None if checkout failed.
    """
    normalized = normalize_spec_number(spec_number)
    undotted = normalized.replace(".", "")  # e.g., "26.260" -> "26260"
    requested_release = release.strip()

    db_path = db_file if db_file is not None else PathConfig().db_file

    resolved_release, version_codes = await resolve_spec_release_from_db(
        normalized,
        requested_release,
        db_file=db_path,
    )

    # First check if already checked out with the SAME release version
    specs_dir = checkout_base / "Specs"
    if specs_dir.exists():
        for spec_dir in specs_dir.rglob("*"):
            if not spec_dir.is_dir():
                continue
            dir_name = spec_dir.name
            # Check if this directory matches our spec
            if normalized not in dir_name and undotted not in dir_name:
                continue
            # Enforce release-aware cache reuse when version codes are known
            if version_codes and not any(vc in dir_name for vc in version_codes):
                continue
            _logger.debug(
                "Spec %s (release %s) already checked out at %s",
                spec_number,
                requested_release,
                spec_dir,
            )
            return spec_dir

    # Need to checkout — auto-crawl if not in database
    try:
        if db_path is not None and db_path.exists():
            async with SpecDatabase(db_path) as db:
                versions = await db.get_spec_versions(normalized)
                if not versions:
                    _logger.info("Spec %s not in database, auto-crawling...", normalized)
                    sources = build_default_spec_sources()
                    await db.crawl_specs([normalized], resolved_release, sources)

        # Use checkout_specs_async to download the spec files
        async with SpecDatabase(db_path) as db:
            checkout_paths = await checkout_specs_async(
                [normalized],
                checkout_base,
                db,
                release=resolved_release,
                doc_only=False,
            )
            if checkout_paths:
                return checkout_paths[0]

        _logger.warning("Checkout failed for spec %s (release %s)", normalized, requested_release)
        return None
    except (FileNotFoundError, OSError, ValueError) as exc:
        _logger.warning("Error checking out spec %s: %s", normalized, exc)
        return None


__all__ = [
    "checkout_spec_to_workspace",
    "checkout_tdoc_to_workspace",
    "resolve_spec_release_from_db",
    "resolve_tdoc_checkout_path",
]
