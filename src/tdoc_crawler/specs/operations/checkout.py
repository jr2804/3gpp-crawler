"""Spec checkout operations for downloading specification documents.

This module provides functionality to download 3GPP specification documents
from various sources and extract them to a local checkout folder.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import cast

from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.specs.downloads import SpecDownloads
from tdoc_crawler.specs.sources.base import FunctionSpecSource, SpecSource
from tdoc_crawler.specs.sources.threegpp import fetch_threegpp_metadata
from tdoc_crawler.specs.sources.whatthespec import fetch_whatthespec_metadata
from tdoc_crawler.utils.normalization import normalize_spec_number, resolve_release_to_full_version


async def resolve_spec_release(
    spec_number: str,
    release: str,
    *,
    auto_crawl: bool = True,
    cache_manager_name: str | None = None,
) -> str:
    """Resolve a release selector to a concrete version string for a spec.

    Queries the spec database for available versions and resolves the release
    selector (e.g., ``"latest"``, ``"17"``) to a full 3-part version string.

    If no versions are found and *auto_crawl* is ``True``, triggers a metadata
    crawl from 3GPP sources before retrying the resolution.

    Args:
        spec_number: Spec number in any format (e.g., ``"26.260"``, ``"26260"``).
        release: Release selector (e.g., ``"latest"``, ``"17"``, ``"17.1.0"``).
        auto_crawl: Crawl spec metadata when not in database.
        cache_manager_name: Optional cache manager name for HTTP caching.

    Returns:
        Full 3-part version string (e.g., ``"19.0.0"``).

    Raises:
        ValueError: If no matching version can be resolved.
    """
    normalized = normalize_spec_number(spec_number)
    db_file = PathConfig().db_file

    async def _get_versions() -> list[str]:
        async with SpecDatabase(db_file) as db:
            versions = await db.get_spec_versions(normalized)
        return [v.version for v in versions]

    versions = await _get_versions()

    if not versions and auto_crawl:
        sources = build_default_spec_sources(cache_manager_name=cache_manager_name)
        async with SpecDatabase(db_file) as db:
            results = await db.crawl_specs([normalized], release, sources)
        for result in results:
            if result.status == "stored" and result.latest_version:
                versions = await _get_versions()
                break

    if not versions:
        raise ValueError(f"No versions found for spec {normalized} (release={release})")

    return resolve_release_to_full_version(release, versions)


def clear_checkout_specs(checkout_dir: Path) -> int:
    """Clear spec checkout entries from the checkout directory.

    Args:
        checkout_dir: Base checkout directory

    Returns:
        Number of entries removed (always 1 if Specs directory existed)
    """
    specs_dir = checkout_dir / "Specs"
    if not specs_dir.exists():
        return 0
    shutil.rmtree(specs_dir)
    return 1


def build_default_spec_sources(cache_manager_name: str | None = None) -> list[SpecSource]:
    """Build the default list of spec sources.

    Args:
        cache_manager_name: Optional cache manager name for HTTP caching

    Returns:
        List of SpecSource instances for fetching spec metadata
    """
    return [
        cast("SpecSource", FunctionSpecSource("3gpp", fetch_threegpp_metadata, fetcher_kwargs={"cache_manager_name": cache_manager_name})),
        cast("SpecSource", FunctionSpecSource("whatthespec", fetch_whatthespec_metadata, fetcher_kwargs={"cache_manager_name": cache_manager_name})),
    ]


def checkout_specs(
    spec_numbers: list[str],
    checkout_dir: Path,
    database: SpecDatabase,
    release: str = "latest",
    doc_only: bool = False,
    cache_manager_name: str | None = None,
) -> list[Path]:
    """Checkout spec documents to the checkout directory.

    Args:
        spec_numbers: List of spec numbers to checkout
        checkout_dir: Base checkout directory
        database: SpecDatabase instance for metadata lookup
        release: Release version to checkout
        doc_only: If True, download only document files instead of full zip
        cache_manager_name: Optional cache manager name for HTTP caching

    Returns:
        List of paths to checked out specs
    """
    sources = build_default_spec_sources(cache_manager_name=cache_manager_name)
    downloader = SpecDownloads(database)
    return downloader.checkout_specs(spec_numbers, doc_only, checkout_dir, release, sources=sources)


async def checkout_specs_async(
    spec_numbers: list[str],
    checkout_dir: Path,
    database: SpecDatabase,
    release: str = "latest",
    doc_only: bool = False,
    cache_manager_name: str | None = None,
) -> list[Path]:
    """Async variant of checkout_specs for async call paths."""
    sources = build_default_spec_sources(cache_manager_name=cache_manager_name)
    downloader = SpecDownloads(database)
    return await downloader.checkout_specs_async(spec_numbers, doc_only, checkout_dir, release, sources=sources)


__all__ = [
    "build_default_spec_sources",
    "checkout_specs",
    "checkout_specs_async",
    "clear_checkout_specs",
    "resolve_spec_release",
]
