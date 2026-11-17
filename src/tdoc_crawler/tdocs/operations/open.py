"""Resolve the main document of a TDoc archive.

Shared by the CLI ``open`` command and the MCP ``get_tdoc_main_file`` tool:
ensure the TDoc metadata exists in the database, download and extract the
archive, then resolve its main document. Launching the file is a CLI-only
concern and stays outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import niquests as requests

from tdoc_crawler.config.settings import CheckoutConfig, ExtractConfig
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.main_files import save_main_file_record
from tdoc_crawler.database.oxyde_models import TDocMetadata
from tdoc_crawler.models.main_files import MainFileSelection, MainFileSelector
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.tdocs.operations.checkout import prepare_tdoc_selection
from tdoc_crawler.tdocs.operations.fetch import fetch_missing_tdocs
from tdoc_crawler.utils.normalization import normalize_tdoc_id


@dataclass(frozen=True)
class TDocOpenResult:
    """Outcome of resolving a TDoc archive's main document."""

    metadata: TDocMetadata
    selection: MainFileSelection
    fetch_errors: tuple[str, ...] = ()


class TDocNotFoundError(LookupError):
    """Raised when a TDoc is neither stored nor retrievable from the portal."""


async def resolve_tdoc_main_file(
    tdoc_id: str,
    *,
    db_file: Path,
    checkout_dir: Path,
    checkout_config: CheckoutConfig,
    full_metadata: bool = False,
    use_whatthespec: bool = False,
    session: requests.Session | None = None,
    extract_config: ExtractConfig | None = None,
) -> TDocOpenResult:
    """Ensure a TDoc is stored, extract it, and resolve its main document.

    Args:
        tdoc_id: TDoc identifier (normalized before lookup).
        db_file: Path to the metadata database.
        checkout_dir: Root directory for TDoc archives.
        checkout_config: Main-document selection settings.
        full_metadata: If True, fetch full metadata from the portal.
        use_whatthespec: If True, always use WhatTheSpec for missing TDocs.
        session: Optional HTTP session to reuse.
        extract_config: Extraction settings; defaults to ``ExtractConfig()``.

    Returns:
        The TDoc metadata and the resolved main-document selection.

    Raises:
        TDocNotFoundError: If the TDoc cannot be found or fetched.
        FileNotFoundError: If the stored override or the archive is invalid.
        OSError: If the archive cannot be written.
        ValueError: If the TDoc metadata is unusable.
    """
    normalized_id = normalize_tdoc_id(tdoc_id)
    query_config = TDocQueryConfig(tdoc_ids=[normalized_id])

    async with TDocDatabase(db_file) as database:
        results = await database.query_tdocs(query_config)
        fetch_result = await fetch_missing_tdocs(
            database,
            query_config,
            results,
            full_metadata=full_metadata,
            use_whatthespec=use_whatthespec,
            session=session,
            url_only_first=True,
        )

        fetch_errors: tuple[str, ...] = ()
        if fetch_result.fetch_result is not None and fetch_result.fetch_result.errors:
            fetch_errors = tuple(str(error) for error in fetch_result.fetch_result.errors)

        refreshed = fetch_result.refreshed
        if not refreshed:
            msg = f"TDoc {normalized_id} not found"
            raise TDocNotFoundError(msg)

        metadata = refreshed[0]
        override = await database.get_main_file_override(normalized_id)

    selection = prepare_tdoc_selection(
        metadata,
        checkout_dir,
        override_member=override.member_path if override is not None else None,
        config=checkout_config,
        session=session,
        extract=extract_config,
    )

    selector = MainFileSelector.MANUAL if override is not None else checkout_config.selector
    async with TDocDatabase(db_file):
        await save_main_file_record(
            metadata.tdoc_id,
            member_path=selection.relative_path,
            source=selection.source.value,
            selector=selector.value,
            confidence=selection.confidence,
        )

    return TDocOpenResult(metadata=metadata, selection=selection, fetch_errors=fetch_errors)
