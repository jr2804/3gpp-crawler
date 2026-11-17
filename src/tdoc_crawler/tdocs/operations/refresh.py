"""Complete metadata refresh for TDocs of recently started meetings.

A refresh re-reads the authoritative 3GPP document lists for every meeting
that started within a configurable lookback window, including meetings that
have already concluded (3GPP/ETSI still publish editorial updates). Unlike an
incremental crawl, it re-processes TDocs that are already in the database so
changed titles, agenda allocations, work-item links and URLs are detected.

The document list is the only source that carries every metadata field
(including ``spec_number``/``release``/``cr_number``/``cr_category``), so the
core of the refresh is a full ``TDocCrawler`` pass with ``incremental=False``.
Additional steps repair URLs whose published filename changed (spaces or
case differences) and build a per-meeting change report.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

from tdoc_crawler.database.oxyde_models import TDocMetadata
from tdoc_crawler.logging import get_logger
from tdoc_crawler.tdocs.models import TDocCrawlConfig
from tdoc_crawler.tdocs.operations.checkout import _resolve_corrected_url
from tdoc_crawler.tdocs.operations.crawl import TDocCrawler
from tdoc_crawler.utils.json_types import JSONObject

if TYPE_CHECKING:
    from tdoc_crawler.database import TDocDatabase
    from tdoc_crawler.models import WorkingGroup

logger = get_logger(__name__)

# Fields worth reporting as changes. Local bookkeeping fields
# (date_updated, date_retrieved, validated, validation_failed, file_size)
# are deliberately excluded — they change on every re-upsert and are not
# metadata coming from 3GPP.
COMPARED_FIELDS: tuple[str, ...] = (
    "tdoc_id",
    "meeting_id",
    "tbid",
    "title",
    "url",
    "source",
    "contact",
    "tdoc_type",
    "for_purpose",
    "agenda_item_nbr",
    "agenda_item_text",
    "status",
    "is_revision_of",
    "spec_number",
    "release",
    "cr_number",
    "cr_category",
    "date_created",
    "reservation_date",
    "uploaded_at",
)

type UrlResolver = Callable[[TDocMetadata], str | None]


def _as_text(value: object) -> str:
    """Normalize a field value for comparison and reporting."""
    if value is None:
        return ""
    return str(value)


@dataclass(slots=True, frozen=True)
class FieldChange:
    """One metadata field that changed during a refresh."""

    field: str
    old: str
    new: str

    def as_dict(self) -> JSONObject:
        return {"field": self.field, "old": self.old, "new": self.new}


@dataclass(slots=True, frozen=True)
class TDocChange:
    """Change report for a single TDoc."""

    tdoc_id: str
    url_repaired: bool = False
    field_changes: tuple[FieldChange, ...] = ()

    def as_dict(self) -> JSONObject:
        return {
            "tdoc_id": self.tdoc_id,
            "url_repaired": self.url_repaired,
            "fields": [change.as_dict() for change in self.field_changes],
        }


@dataclass(slots=True, frozen=True)
class MeetingRefreshSummary:
    """Changes found for one meeting in the refresh window."""

    meeting_id: int
    short_name: str
    tdocs_before: int
    tdocs_after: int
    added: tuple[str, ...]
    changed: tuple[TDocChange, ...]
    unchanged: int
    absent_from_list: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.changed or self.absent_from_list)

    def as_dict(self) -> JSONObject:
        return {
            "meeting_id": self.meeting_id,
            "meeting": self.short_name,
            "tdocs_before": self.tdocs_before,
            "tdocs_after": self.tdocs_after,
            "added": list(self.added),
            "changed": [change.as_dict() for change in self.changed],
            "unchanged": self.unchanged,
            "absent_from_list": list(self.absent_from_list),
            "errors": list(self.errors),
        }


@dataclass(slots=True, frozen=True)
class RefreshResult:
    """Summary of a complete metadata refresh run."""

    lookback_days: int
    start_date: date
    meetings_scanned: int
    meetings_with_changes: int
    tdocs_processed: int
    tdocs_added: int
    tdocs_changed: int
    tdocs_unchanged: int
    urls_repaired: int
    meetings: tuple[MeetingRefreshSummary, ...]
    errors: tuple[str, ...]

    @property
    def has_changes(self) -> bool:
        return any(meeting.has_changes for meeting in self.meetings)

    def as_dict(self) -> JSONObject:
        return {
            "lookback_days": self.lookback_days,
            "start_date": self.start_date.isoformat(),
            "meetings_scanned": self.meetings_scanned,
            "meetings_with_changes": self.meetings_with_changes,
            "tdocs_processed": self.tdocs_processed,
            "tdocs_added": self.tdocs_added,
            "tdocs_changed": self.tdocs_changed,
            "tdocs_unchanged": self.tdocs_unchanged,
            "urls_repaired": self.urls_repaired,
            "meetings": [meeting.as_dict() for meeting in self.meetings],
            "errors": list(self.errors),
        }


def diff_tdoc(before: TDocMetadata, after: TDocMetadata) -> tuple[FieldChange, ...]:
    """Return the meaningful metadata fields that differ between two records."""
    changes: list[FieldChange] = []
    for name in COMPARED_FIELDS:
        old_value = _as_text(getattr(before, name, None))
        new_value = _as_text(getattr(after, name, None))
        if old_value != new_value:
            changes.append(FieldChange(field=name, old=old_value, new=new_value))
    return tuple(changes)


def _repair_urls(
    tdocs: Iterable[TDocMetadata],
    resolve_url: UrlResolver,
    workers: int,
) -> dict[str, str]:
    """Resolve corrected URLs concurrently; return {tdoc_id: corrected_url}."""
    records = list(tdocs)
    if not records:
        return {}

    repairs: dict[str, str] = {}
    worker_count = min(max(1, workers), 8)
    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        futures = {pool.submit(resolve_url, record): record for record in records}
        for future in as_completed(futures):
            record = futures[future]
            try:
                corrected = future.result()
            except (OSError, ValueError) as exc:
                logger.debug("URL resolution failed for %s: %s", record.tdoc_id, exc)
                continue
            if corrected and corrected != record.url:
                repairs[record.tdoc_id] = corrected
    return repairs


async def refresh_tdocs(
    database: TDocDatabase,
    *,
    lookback_days: int = 14,
    working_groups: list[WorkingGroup] | None = None,
    subgroups: list[str] | None = None,
    workers: int = 4,
    timeout: int = 30,
    max_retries: int = 3,
    repair_urls: bool = True,
    resolve_url: UrlResolver = _resolve_corrected_url,
    progress_callback: Callable[[float, float], None] | None = None,
    today: date | None = None,
) -> RefreshResult:
    """Re-fetch complete metadata for TDocs of meetings in the lookback window.

    Args:
        database: Open database used for snapshots and upserts.
        lookback_days: Include meetings that started within this many days.
        working_groups: Restrict to these groups (default: all RAN/SA/CT).
        subgroups: Optional sub-working-group filter.
        workers: Parallel workers for the document-list crawl and URL repair.
        timeout: Per-request HTTP timeout in seconds.
        max_retries: Retry attempts for failed meetings.
        repair_urls: Resolve and persist corrected download URLs.
        resolve_url: URL resolver (injectable for tests).
        progress_callback: Optional (completed, total) crawl progress callback.
        today: Override for ``date.today()`` in tests.

    Returns:
        A :class:`RefreshResult` with per-meeting change details.
    """
    if lookback_days < 1:
        msg = "lookback_days must be at least 1"
        raise ValueError(msg)

    start_date = (today or date.today()) - timedelta(days=lookback_days)
    config = TDocCrawlConfig(
        working_groups=working_groups,
        subgroups=subgroups,
        incremental=False,
        start_date=start_date,
        workers=workers,
        timeout=timeout,
        max_retries=max_retries,
    )

    crawler = TDocCrawler(database)
    meetings = await crawler.get_meetings_to_crawl(config)
    meeting_ids = [meeting.meeting_id for meeting in meetings]

    before_records = await database.query_tdocs_by_meeting_ids(meeting_ids)
    before = {record.tdoc_id: record for record in before_records}

    crawl_result = await crawler.crawl(config, progress_callback=progress_callback)

    after_records = await database.query_tdocs_by_meeting_ids(meeting_ids)
    after = {record.tdoc_id: record for record in after_records}

    repaired: dict[str, str] = {}
    if repair_urls and after_records:
        repaired = _repair_urls(after_records, resolve_url, workers)
        for tdoc_id, corrected_url in repaired.items():
            await database.update_tdoc_url(tdoc_id, corrected_url)
        if repaired:
            # Reload so the change report reflects persisted URLs.
            after_records = await database.query_tdocs_by_meeting_ids(meeting_ids)
            after = {record.tdoc_id: record for record in after_records}

    meeting_summaries: list[MeetingRefreshSummary] = []
    for meeting in meetings:
        meeting_before = {record.tdoc_id: record for record in before_records if record.meeting_id == meeting.meeting_id}
        meeting_after = {record.tdoc_id: record for record in after_records if record.meeting_id == meeting.meeting_id}

        added = tuple(sorted(set(meeting_after) - set(meeting_before)))
        absent = tuple(sorted(set(meeting_before) - set(meeting_after)))
        changed: list[TDocChange] = []
        unchanged = 0
        for tdoc_id in sorted(set(meeting_before) & set(meeting_after)):
            field_changes = diff_tdoc(meeting_before[tdoc_id], meeting_after[tdoc_id])
            url_repaired = tdoc_id in repaired
            if field_changes or url_repaired:
                changed.append(TDocChange(tdoc_id=tdoc_id, url_repaired=url_repaired, field_changes=field_changes))
            else:
                unchanged += 1

        short_name = meeting.short_name or str(meeting.meeting_id)
        meeting_errors = tuple(error for error in crawl_result.errors if short_name in error)

        meeting_summaries.append(
            MeetingRefreshSummary(
                meeting_id=meeting.meeting_id,
                short_name=short_name,
                tdocs_before=len(meeting_before),
                tdocs_after=len(meeting_after),
                added=added,
                changed=tuple(changed),
                unchanged=unchanged,
                absent_from_list=absent,
                errors=meeting_errors,
            )
        )

    return RefreshResult(
        lookback_days=lookback_days,
        start_date=start_date,
        meetings_scanned=len(meetings),
        meetings_with_changes=sum(1 for summary in meeting_summaries if summary.has_changes),
        tdocs_processed=crawl_result.processed,
        tdocs_added=len(set(after) - set(before)),
        tdocs_changed=sum(len(summary.changed) for summary in meeting_summaries),
        tdocs_unchanged=sum(summary.unchanged for summary in meeting_summaries),
        urls_repaired=len(repaired),
        meetings=tuple(meeting_summaries),
        errors=tuple(crawl_result.errors),
    )


__all__ = [
    "COMPARED_FIELDS",
    "FieldChange",
    "MeetingRefreshSummary",
    "RefreshResult",
    "TDocChange",
    "diff_tdoc",
    "refresh_tdocs",
]
