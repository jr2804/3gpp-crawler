"""Work item operations: WG code expansion, enrichment and list comparison."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from tdoc_crawler.config.settings import HttpConfig
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.oxyde_models import WorkItemRecord
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models import WorkingGroup
from tdoc_crawler.models.subworking_groups import SubWorkingGroup
from tdoc_crawler.utils.normalization import normalize_subgroup_alias
from tdoc_crawler.workitems.models import LeadBodyCoverage, WorkItemCr, WorkItemDetails
from tdoc_crawler.workitems.sources.dynareport import (
    WorkItemSourceError,
    fetch_work_item_crs,
    fetch_work_item_details,
    fetch_work_item_list_entries,
    fetch_work_item_specs,
    work_item_session,
)

_logger = get_logger(__name__)


@dataclass(slots=True)
class EnrichSummary:
    """Outcome of a work item enrichment run."""

    enriched: int = 0
    skipped: int = 0
    failed: int = 0
    specs_found: int = 0
    crs_found: int = 0
    parents_found: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class WorkItemListComparison:
    """Result of comparing the catalogue against the global work item list."""

    rows: list[LeadBodyCoverage]
    list_entries: int
    matched: int
    missing_from_db: int
    missing_from_list: int


def normalize_wg_codes(codes: Sequence[str] | None) -> list[str]:
    """Normalize lead body codes, keeping historical codes the enum lacks.

    Known subgroup aliases are canonicalized (``SA4`` → ``S4``); anything
    else (e.g. the historical ``GP``, ``T1``, ``SMG`` lead bodies) is kept
    as an uppercased code so those lists stay reachable.
    """
    if not codes:
        return []
    normalized: list[str] = []
    for code in codes:
        try:
            canonical = normalize_subgroup_alias(code).name
        except ValueError:
            canonical = str(code).strip().upper()
        if canonical and canonical not in normalized:
            normalized.append(canonical)
    return normalized


def expand_area_codes(working_groups: Sequence[WorkingGroup] | None) -> list[str]:
    """Expand working group areas into their sub-working group codes.

    ``SA`` becomes ``["SP", "S1", ..., "S6"]``, ``RAN`` ``["RP", "R1", ...,
    "R6"]``, ``CT`` ``["CP", "C1", ..., "C6"]``.
    """
    if not working_groups:
        return []
    wanted = set(working_groups)
    return [member.name for member in SubWorkingGroup if WorkingGroup.from_literal(member.name[0]) in wanted]


def enrich_work_items(
    db_path: Path,
    work_item_ids: Sequence[str] | None = None,
    *,
    limit: int | None = None,
    include_all: bool = False,
    timeout: int = 60,
    http_config: HttpConfig | None = None,
    http_cache_file: Path | None = None,
    store: Callable[[str, WorkItemDetails, Sequence[str], Sequence[WorkItemCr]], bool] | None = None,
    progress: Callable[[str], None] | None = None,
) -> EnrichSummary:
    """Enrich work items from the portal details, spec and CR pages.

    Fetches over one cached session and stores per work item via
    :meth:`TDocDatabase.store_work_item_details`.

    Args:
        db_path: SQLite database file of the crawler
        work_item_ids: Explicit work item IDs; default selection when empty
        limit: Cap on the number of enriched work items
        include_all: Enrich every catalogue row, not only linked/unenriched
        timeout: Request timeout in seconds
        http_config: Optional HTTP configuration
        http_cache_file: Optional explicit HTTP cache database
        store: Override for the storage callable (injectable for tests)
        progress: Optional callable invoked with each completed work item ID

    Returns:
        Summary of the run
    """

    async def _select() -> list[WorkItemRecord]:
        async with TDocDatabase(db_path) as database:
            return await database.select_work_items_for_enrichment(
                work_item_ids,
                limit=limit,
                include_all=include_all,
            )

    records = asyncio.run(_select())
    summary = EnrichSummary()
    persist = store or (lambda wi_id, details, specs, crs: _default_store(wi_id, details, specs, crs, db_path))

    with work_item_session(http_config=http_config, http_cache_file=http_cache_file) as session:
        for record in records:
            wi_id = record.wi_id
            if record.uid is None:
                summary.skipped += 1
                summary.errors.append(f"{wi_id}: no UID in the catalogue; run 'work-items crawl' first")
                continue
            try:
                details = fetch_work_item_details(record.uid, timeout=timeout, http_config=http_config, http_cache_file=http_cache_file, session=session)
                specs = fetch_work_item_specs(record.uid, timeout=timeout, http_config=http_config, http_cache_file=http_cache_file, session=session)
                crs = fetch_work_item_crs(record.uid, timeout=timeout, http_config=http_config, http_cache_file=http_cache_file, session=session)
            except WorkItemSourceError as exc:
                summary.failed += 1
                summary.errors.append(f"{wi_id}: {exc}")
                continue

            persist(wi_id, details, specs, crs)
            summary.enriched += 1
            summary.specs_found += len(specs)
            summary.crs_found += len(crs)
            if details.parent_uid is not None:
                summary.parents_found += 1
            if progress is not None:
                progress(wi_id)

    return summary


def _default_store(wi_id: str, details: WorkItemDetails, specs: Sequence[str], crs: Sequence[WorkItemCr], db_path: Path) -> bool:
    """Store enrichment results with a short-lived database connection."""

    async def _store() -> bool:
        async with TDocDatabase(db_path) as database:
            return await database.store_work_item_details(wi_id, details, specs, crs)

    return asyncio.run(_store())


def compare_work_item_list(
    db_path: Path,
    *,
    timeout: int = 120,
    http_config: HttpConfig | None = None,
    http_cache_file: Path | None = None,
    fetch_entries: Callable[..., list[tuple[int, str, str]]] | None = None,
) -> WorkItemListComparison:
    """Compare the local catalogue against the global DynaReport work item list.

    The global list lags behind for work items without published
    specifications, so catalogue-only entries are expected for in-flight
    work items, while list entries missing from the catalogue point at lead
    bodies that were not crawled.
    """

    async def _load() -> dict[int, WorkItemRecord]:
        async with TDocDatabase(db_path):
            records = await WorkItemRecord.objects.all()
            return {record.uid: record for record in records if record.uid is not None}

    if fetch_entries is None:
        fetch_entries = fetch_work_item_list_entries
    entries = fetch_entries(timeout=timeout, http_config=http_config, http_cache_file=http_cache_file)
    by_uid = asyncio.run(_load())

    list_uids = {uid for uid, _code, _lead_body in entries}
    per_lead_body: dict[str, dict[str, int]] = {}
    matched_uids: set[int] = set()
    for uid, _code, lead_body in entries:
        bucket = per_lead_body.setdefault(lead_body, {"list": 0, "matched": 0})
        bucket["list"] += 1
        if uid in by_uid:
            bucket["matched"] += 1
            matched_uids.add(uid)

    rows: list[LeadBodyCoverage] = [
        {
            "lead_body": lead_body,
            "list": counts["list"],
            "in_catalogue": counts["matched"],
            "missing": counts["list"] - counts["matched"],
        }
        for lead_body, counts in sorted(per_lead_body.items())
    ]
    return WorkItemListComparison(
        rows=rows,
        list_entries=len(entries),
        matched=len(matched_uids),
        missing_from_db=len(entries) - len(matched_uids),
        missing_from_list=sum(1 for uid in by_uid if uid not in list_uids),
    )


__all__ = [
    "EnrichSummary",
    "WorkItemListComparison",
    "compare_work_item_list",
    "enrich_work_items",
    "expand_area_codes",
    "normalize_wg_codes",
]
