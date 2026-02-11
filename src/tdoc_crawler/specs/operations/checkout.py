"""Spec checkout operations for downloading specification documents.

This module provides functionality to download 3GPP specification documents
from various sources and extract them to a local checkout folder.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import cast

from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.specs.downloads import SpecDownloads
from tdoc_crawler.specs.sources.base import FunctionSpecSource, SpecSource
from tdoc_crawler.specs.sources.threegpp import fetch_threegpp_metadata
from tdoc_crawler.specs.sources.whatthespec import fetch_whatthespec_metadata


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
    downloader = SpecDownloads(database, cache_manager_name=cache_manager_name)
    return downloader.checkout_specs(spec_numbers, doc_only, checkout_dir, release, sources=sources)


__all__ = [
    "build_default_spec_sources",
    "checkout_specs",
    "clear_checkout_specs",
]
