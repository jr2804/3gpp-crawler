"""Re-run main-document classification for stored TDocs.

``tdoc open`` records which file it picked and which selector produced that
choice. This operation replays the classification for TDocs that already
have a checkout, without downloading anything, so a changed heuristic or a
newly configured decision model can be applied in bulk.

Manual user choices are protected: TDocs whose selector is ``manual`` or
that carry a stored override are skipped unless ``include_manual`` is set,
in which case the override is removed and the configured selector decides.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tdoc_crawler.config.settings import CheckoutConfig
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.main_files import (
    clear_main_file_override,
    list_main_file_records,
    save_main_file_record,
)
from tdoc_crawler.database.oxyde_models import MainFileRecord, TDocMetadata
from tdoc_crawler.models.main_files import MainFileSelection, MainFileSelector, ReclassifyStatus
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.tdocs.operations.checkout import get_checkout_path
from tdoc_crawler.tdocs.operations.main_file import resolve_main_file
from tdoc_crawler.utils.normalization import normalize_tdoc_id


@dataclass(frozen=True)
class ReclassifyOutcome:
    """Result of re-classifying one TDoc."""

    tdoc_id: str
    status: ReclassifyStatus
    message: str = ""
    selection: MainFileSelection | None = None


async def reclassify_tdocs(
    *,
    db_file: Path,
    checkout_dir: Path,
    checkout_config: CheckoutConfig,
    tdoc_ids: list[str] | None = None,
    include_manual: bool = False,
) -> list[ReclassifyOutcome]:
    """Re-run main-file classification on stored TDocs with a checkout.

    Args:
        db_file: Path to the metadata database.
        checkout_dir: Root directory containing extracted TDoc archives.
        checkout_config: Main-document selection settings.
        tdoc_ids: Specific TDocs to re-classify; None means every stored
            classification.
        include_manual: Also re-classify TDocs with a manual selector or a
            stored override, deleting that override. Destructive.

    Returns:
        One outcome per requested TDoc, in request order.
    """
    async with TDocDatabase(db_file) as database:
        records = {record.tdoc_id: record for record in await list_main_file_records()}
        targets = [normalize_tdoc_id(tdoc_id) for tdoc_id in tdoc_ids] if tdoc_ids else sorted(records)

        if not targets:
            return []

        metadata_rows = await database.query_tdocs(TDocQueryConfig(tdoc_ids=targets))
        metadata_by_id: dict[str, TDocMetadata] = {row.tdoc_id: row for row in metadata_rows}

        outcomes: list[ReclassifyOutcome] = []
        for tdoc_id in targets:
            outcome = await _reclassify_one(
                database,
                tdoc_id,
                records.get(tdoc_id),
                metadata_by_id.get(tdoc_id),
                checkout_dir=checkout_dir,
                checkout_config=checkout_config,
                include_manual=include_manual,
            )
            outcomes.append(outcome)

        return outcomes


async def _reclassify_one(
    database: TDocDatabase,
    tdoc_id: str,
    record: MainFileRecord | None,
    metadata: TDocMetadata | None,
    *,
    checkout_dir: Path,
    checkout_config: CheckoutConfig,
    include_manual: bool,
) -> ReclassifyOutcome:
    """Re-classify a single TDoc, honoring manual user choices."""
    if record is None:
        return ReclassifyOutcome(tdoc_id, ReclassifyStatus.MISSING, "no stored classification")

    selector = record.selector
    override = await database.get_main_file_override(tdoc_id)
    if not include_manual and (selector == MainFileSelector.MANUAL or override is not None):
        return ReclassifyOutcome(tdoc_id, ReclassifyStatus.SKIPPED, "manual choice protected (use --include-manual)")

    if metadata is None:
        return ReclassifyOutcome(tdoc_id, ReclassifyStatus.MISSING, "TDoc metadata not in database")

    extract_dir = get_checkout_path(metadata, checkout_dir)
    if not extract_dir.is_dir():
        return ReclassifyOutcome(tdoc_id, ReclassifyStatus.MISSING, "TDoc is not checked out")

    if include_manual and checkout_config.selector is MainFileSelector.MANUAL:
        return ReclassifyOutcome(tdoc_id, ReclassifyStatus.SKIPPED, "configured selector is manual")

    try:
        selection = resolve_main_file(
            extract_dir,
            tdoc_id,
            title=metadata.title,
            config=checkout_config,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        return ReclassifyOutcome(tdoc_id, ReclassifyStatus.FAILED, str(exc))

    if include_manual and override is not None:
        await clear_main_file_override(tdoc_id)

    await save_main_file_record(
        tdoc_id,
        member_path=selection.relative_path,
        source=selection.source.value,
        selector=checkout_config.selector.value,
        confidence=selection.confidence,
    )
    return ReclassifyOutcome(tdoc_id, ReclassifyStatus.UPDATED, selection=selection)


__all__ = ["ReclassifyOutcome", "reclassify_tdocs"]
