"""TDoc database operations."""

import fnmatch
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, date, datetime

from tdoc_crawler.database.meetings import MeetingDatabase
from tdoc_crawler.database.oxyde_models import (
    MeetingAgendaItem,
    MeetingMetadata,
    TDocMetadata,
    TDocWorkItem,
    WorkItemCrRecord,
    WorkItemRecord,
    WorkItemSpecRecord,
)
from tdoc_crawler.database.tags import item_ids_for_tag_groups, parse_tag_groups
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models import WorkingGroup
from tdoc_crawler.models.base import SortKey, TagKind, TDocFieldValue
from tdoc_crawler.models.subworking_groups import CODE_INDEX
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.utils.agenda import ancestor_agenda_numbers
from tdoc_crawler.utils.misc import utc_now
from tdoc_crawler.utils.normalization import normalize_tdoc_id
from tdoc_crawler.workitems.models import WorkItem, WorkItemCr, WorkItemDetails

SQLITE_MAX_VARS = 999

DEFAULT_BULK_BATCH_SIZE = 40

_logger = get_logger(__name__)


class TDocDatabase(MeetingDatabase):
    """Unified database operations for TDocs and Meetings.

    This class provides a unified interface for both TDoc and Meeting operations
    by inheriting from MeetingDatabase. This maintains backward compatibility
    with code that expects a single database interface.
    """

    # ------------------------------------------------------------------
    # TDoc operations
    # ------------------------------------------------------------------
    async def upsert_tdoc(self, metadata: TDocMetadata) -> tuple[bool, bool]:
        """Insert or update a TDoc record.

        If ``tbid`` is not set on the metadata, resolves it from the
        associated meeting record.

        Args:
            metadata: TDoc metadata to insert or update

        Returns:
            Tuple of (created, changed) booleans
        """
        record = self._prepare_tdoc(metadata)
        if not record.tbid:
            record = await self._resolve_tbid(record)
        existing = await self._get_tdoc(record.tdoc_id)
        now = utc_now()

        if existing is None:
            created_record = self._clone_tdoc(
                record,
                {
                    "date_updated": now,
                    "date_created": record.date_created or record.date_retrieved,
                },
            )
            await TDocMetadata.objects.create(instance=created_record)
            return True, False

        if record.date_created is None and existing.date_created is not None:
            record = self._clone_tdoc(record, {"date_created": existing.date_created})

        changed = self._tdoc_changed(existing, record)
        updated_record = self._clone_tdoc(record, {"date_updated": now})
        await updated_record.save()
        return False, changed

    async def bulk_upsert_tdocs(
        self,
        tdocs: Iterable[TDocMetadata],
        progress_callback: Callable[[float, float], None] | None = None,
        batch_size: int = DEFAULT_BULK_BATCH_SIZE,
    ) -> tuple[int, int]:
        """Bulk upsert TDocs with optional progress callback.

        Splits records into new vs existing, then uses ``bulk_create`` for
        inserts and ``bulk_update`` for updates instead of one-by-one queries.

        Args:
            tdocs: Iterable of TDoc metadata to upsert
            progress_callback: Optional callback to call after each batch.
                Takes (completed, total) as float parameters.
            batch_size: Number of records per batch. Automatically reduced
                if it would exceed SQLite's variable limit.

        Returns:
            Tuple of (inserted_count, updated_count)
        """
        tdocs_list = list(tdocs)
        if not tdocs_list:
            return 0, 0

        total = float(len(tdocs_list))

        prepared: list[TDocMetadata] = []
        for metadata in tdocs_list:
            record = self._prepare_tdoc(metadata)
            if not record.tbid:
                record = await self._resolve_tbid(record)
            prepared.append(record)

        all_ids = [record.tdoc_id for record in prepared]
        # Chunked to respect SQLite's host-variable limit (SQLITE_MAX_VARS);
        # a single tdoc_id__in query with thousands of IDs fails outright.
        existing_ids: set[str] = set()
        for i in range(0, len(all_ids), SQLITE_MAX_VARS):
            chunk = all_ids[i : i + SQLITE_MAX_VARS]
            existing_ids.update(record.tdoc_id for record in await TDocMetadata.objects.filter(tdoc_id__in=chunk).all())

        now = utc_now()
        to_create: list[TDocMetadata] = []
        to_update: list[TDocMetadata] = []
        for record in prepared:
            if record.tdoc_id not in existing_ids:
                to_create.append(self._clone_tdoc(record, {"date_updated": now, "date_created": record.date_created or record.date_retrieved}))
            else:
                to_update.append(self._clone_tdoc(record, {"date_updated": now}))

        update_fields = _get_updatable_fields(TDocMetadata)
        n_cols = len(TDocMetadata.model_fields)
        max_batch = SQLITE_MAX_VARS // n_cols
        if batch_size > max_batch:
            _logger.warning("batch_size reduced from %d to %d (SQLITE_MAX_VARS=%d, columns=%d)", batch_size, max_batch, SQLITE_MAX_VARS, n_cols)
            batch_size = max_batch

        for i in range(0, len(to_create), batch_size):
            await TDocMetadata.objects.bulk_create(to_create[i : i + batch_size])

        for i in range(0, len(to_update), batch_size):
            await TDocMetadata.objects.bulk_update(to_update[i : i + batch_size], fields=update_fields)

        if progress_callback:
            progress_callback(total, total)

        return len(to_create), len(to_update)

    async def query_tdocs(self, config: TDocQueryConfig) -> list[TDocMetadata]:
        """Query TDocs with filtering and sorting.

        Pushes tdoc_id and working_group (via denormalized tbid) filters to
        SQL WHERE via Oxyde ORM. Meeting date filters and glob pattern filters
        still require in-memory processing because they span multiple tables
        or use fnmatch.

        Sort order: meeting start_date, then tdoc_id (case-insensitive).
        Direction controlled by ``config.order``.

        Args:
            config: Query configuration with filters and options

        Returns:
            List of matching TDoc metadata
        """
        qs = TDocMetadata.objects

        if config.tdoc_ids:
            lookup = [normalize_tdoc_id(value) for value in config.tdoc_ids]
            qs = qs.filter(tdoc_id__in=lookup)

        if config.working_groups:
            allowed_tbids = [wg.tbid for wg in config.working_groups]
            qs = qs.filter(tbid__in=allowed_tbids)

        subgroup_prefixes: tuple[str, ...] = ()

        if config.subgroups:
            allowed_subtbs = [CODE_INDEX[code.upper()].subtb for code in config.subgroups if code.upper() in CODE_INDEX]
            meetings = await MeetingMetadata.objects.filter(subtb__in=allowed_subtbs).all()
            meeting_ids = [meeting.meeting_id for meeting in meetings]
            if meeting_ids:
                qs = qs.filter(meeting_id__in=meeting_ids)
            else:
                # Meetings were never crawled (TDoc-only crawl leaves the
                # meetings table empty), so resolve sub-working groups from the
                # TDoc ID prefix instead of returning nothing.
                subgroup_prefixes = tuple(code.upper() for code in config.subgroups)

        if config.work_items:
            links = await TDocWorkItem.objects.filter(wi_id__in=[wi.upper() for wi in config.work_items]).all()
            linked_ids = sorted({link.tdoc_id for link in links})
            if not linked_ids:
                return []
            qs = qs.filter(tdoc_id__in=linked_ids)

        if config.spec_numbers:
            qs = qs.filter(spec_number__in=list(config.spec_numbers))

        records = await qs.all()

        if not records:
            return []

        if subgroup_prefixes:
            records = [record for record in records if record.tdoc_id.upper().startswith(subgroup_prefixes)]

        need_meeting_map = config.meeting_start_date is not None or config.meeting_end_date is not None

        meeting_map = {meeting.meeting_id: meeting for meeting in await self._table_rows(MeetingMetadata)} if need_meeting_map else {}

        if need_meeting_map:
            records = self._filter_by_meeting_dates(records, meeting_map, config.meeting_start_date, config.meeting_end_date)

        records = self._filter_by_retrieved_dates(records, config.start_date, config.end_date)

        agenda_map = await self._load_meeting_agenda_map(records) if (config.agenda_pattern or config.agenda_pattern_exclude) else {}
        records = self._apply_pattern_filters(records, config, agenda_map)

        if config.tag:
            groups = parse_tag_groups(config.tag)
            matching = await item_ids_for_tag_groups(groups, TagKind.TDOC)
            records = [record for record in records if record.tdoc_id in matching]

        if not meeting_map:
            meeting_map = {meeting.meeting_id: meeting for meeting in await self._table_rows(MeetingMetadata)}
        descending = config.order.value.lower() == "desc"
        fallback = date.max if descending else date.min
        records.sort(key=self._sort_key(config, meeting_map, fallback), reverse=descending)

        if config.limit is not None:
            records = records[: config.limit]

        return records

    async def get_existing_tdoc_ids(self, working_groups: Iterable[WorkingGroup] | None = None) -> set[str]:
        """Get set of existing TDoc IDs, optionally filtered by working group.

        Uses the denormalized ``tbid`` field on TDocMetadata to filter
        without joining the meetings table.

        Args:
            working_groups: Optional list of working groups to filter by

        Returns:
            Set of TDoc IDs
        """
        if not working_groups:
            records = await self._table_rows(TDocMetadata)
            return {record.tdoc_id for record in records}

        allowed_tbids = [wg.tbid for wg in working_groups]
        records = await TDocMetadata.objects.filter(tbid__in=allowed_tbids).all()
        return {record.tdoc_id for record in records}

    async def store_tdoc_work_items(self, work_items: dict[str, list[str]]) -> None:
        """Replace the stored work item references of the given TDocs.

        Clears any previous links for these TDocs (a re-crawl can drop a
        reference), rewrites the links from the document list, and refreshes
        the work item catalogue with counts.

        Args:
            work_items: Mapping of TDoc ID to the work item IDs it references
        """
        if not work_items:
            return

        tdoc_ids = sorted(tdoc_id.upper() for tdoc_id in work_items)
        for i in range(0, len(tdoc_ids), SQLITE_MAX_VARS):
            await TDocWorkItem.objects.filter(tdoc_id__in=tdoc_ids[i : i + SQLITE_MAX_VARS]).delete()

        links = [
            TDocWorkItem(link_id=f"{tdoc_id.upper()}|{wi_id.upper()}", tdoc_id=tdoc_id.upper(), wi_id=wi_id.upper())
            for tdoc_id, wi_ids in work_items.items()
            for wi_id in wi_ids
        ]
        for i in range(0, len(links), DEFAULT_BULK_BATCH_SIZE):
            await TDocWorkItem.objects.bulk_create(links[i : i + DEFAULT_BULK_BATCH_SIZE])

        await self._refresh_work_item_catalog({link.wi_id for link in links})

    @staticmethod
    async def store_meeting_agenda_items(agenda_by_meeting: Mapping[int, Mapping[str, str]]) -> int:
        """Replace the stored parent agenda items of the given meetings.

        Args:
            agenda_by_meeting: Mapping of meeting ID to its agenda items
                (agenda number to text)

        Returns:
            Number of stored agenda items
        """
        if not agenda_by_meeting:
            return 0

        meeting_ids = sorted(meeting_id for meeting_id in agenda_by_meeting if meeting_id)
        for i in range(0, len(meeting_ids), SQLITE_MAX_VARS):
            await MeetingAgendaItem.objects.filter(meeting_id__in=meeting_ids[i : i + SQLITE_MAX_VARS]).delete()

        items = [
            MeetingAgendaItem(
                link_id=f"{meeting_id}|{number}",
                meeting_id=meeting_id,
                agenda_nbr=number,
                agenda_text=text,
            )
            for meeting_id, agenda_items in agenda_by_meeting.items()
            for number, text in agenda_items.items()
        ]
        for i in range(0, len(items), DEFAULT_BULK_BATCH_SIZE):
            await MeetingAgendaItem.objects.bulk_create(items[i : i + DEFAULT_BULK_BATCH_SIZE])

        _logger.debug("Stored %d agenda items for %d meeting(s)", len(items), len(meeting_ids))
        return len(items)

    @staticmethod
    async def list_work_items(
        *,
        working_group: WorkingGroup | None = None,
        release: str | None = None,
        status: str | None = None,
        parent_wi_id: str | None = None,
        lead_body: str | None = None,
    ) -> list[WorkItemRecord]:
        """List work items, optionally limited by working group, release, status, parent or lead body."""
        records = await WorkItemRecord.objects.all()
        if release:
            records = [record for record in records if (record.release or "").lower() == release.lower()]
        if status:
            records = [record for record in records if (record.status or "").lower() == status.lower()]
        if parent_wi_id:
            parent = parent_wi_id.upper()
            records = [record for record in records if (record.parent_wi_id or "").upper() == parent]
        if lead_body:
            needle = lead_body.strip().upper()
            records = [record for record in records if needle in (record.lead_body or "").upper()]
        if working_group is None:
            return sorted(records, key=lambda record: (-record.tdoc_count, record.wi_id))

        links = await TDocWorkItem.objects.all()
        tdocs = await TDocMetadata.objects.filter(tbid=working_group.tbid).all()
        allowed = {tdoc.tdoc_id.upper() for tdoc in tdocs}
        wi_ids = {link.wi_id for link in links if link.tdoc_id.upper() in allowed}
        return sorted(
            (record for record in records if record.wi_id in wi_ids),
            key=lambda record: (-record.tdoc_count, record.wi_id),
        )

    @staticmethod
    async def list_work_item_specs(wi_id: str) -> list[str]:
        """Return the specification numbers a work item impacts, sorted."""
        links = await WorkItemSpecRecord.objects.filter(wi_id=wi_id.upper()).all()
        return sorted({link.spec_number for link in links})

    @staticmethod
    async def store_work_items(work_items: Sequence[WorkItem]) -> int:
        """Upsert work item catalogue rows from DynaReport per-group lists.

        The catalogue rows keep the TDoc counts computed from document lists
        and the enriched status/parent fields; only the per-group list
        attributes are replaced. A ``lead_body`` already present is merged
        (comma separated) so work items led by several groups keep all of
        them.

        Args:
            work_items: Work items parsed from the per-group lists

        Returns:
            Number of work items stored
        """
        if not work_items:
            return 0

        now = utc_now()
        existing = {record.wi_id: record for record in await WorkItemRecord.objects.all()}
        new_records: list[WorkItemRecord] = []
        updated_records: list[WorkItemRecord] = []
        seen: set[str] = set()

        for item in work_items:
            if item.wi_id in seen:
                continue
            seen.add(item.wi_id)
            record = existing.get(item.wi_id)
            if record is None:
                record = WorkItemRecord(wi_id=item.wi_id)
                new_records.append(record)
            elif (
                record.uid,
                record.title,
                record.release,
                record.level,
                record.lead_body,
                record.parent_uid,
            ) == (item.uid, item.title, item.release, item.level, item.lead_body, item.parent_uid):
                continue
            else:
                updated_records.append(record)

            record.uid = item.uid
            record.title = item.title
            record.release = item.release
            record.level = item.level
            record.parent_uid = item.parent_uid
            record.lead_body = _merge_lead_bodies(record.lead_body, item.lead_body)
            record.updated_at = now

        for i in range(0, len(new_records), DEFAULT_BULK_BATCH_SIZE):
            await WorkItemRecord.objects.bulk_create(new_records[i : i + DEFAULT_BULK_BATCH_SIZE])
        for record in updated_records:
            await record.save()

        await TDocDatabase._resolve_parent_wi_ids()

        return len(new_records) + len(updated_records)

    @staticmethod
    async def store_work_item_details(
        wi_id: str,
        details: WorkItemDetails,
        spec_numbers: Sequence[str],
        change_requests: Sequence[WorkItemCr],
    ) -> bool:
        """Store enrichment data of one work item from the portal pages.

        Updates status, release, WI level, title, parent UID and the
        parent work item ID (resolved through the catalogue UIDs), and
        replaces the specification and change-request links of the work
        item. Creates a minimal catalogue row for unknown work item IDs.

        Args:
            wi_id: Work item ID (acronym)
            details: Parsed WorkItemDetails.aspx payload
            spec_numbers: Specification numbers from the WiSpec page
            change_requests: Change requests from the WiCr page

        Returns:
            True if the stored row changed
        """
        wi_id = wi_id.upper()
        record = await WorkItemRecord.objects.filter(wi_id=wi_id).first()
        if record is None:
            record = WorkItemRecord(wi_id=wi_id)
            await WorkItemRecord.objects.create(instance=record)

        before = (
            record.uid,
            record.title,
            record.status,
            record.release,
            record.level,
            record.parent_uid,
            record.parent_wi_id,
        )

        record.uid = details.uid
        if details.title:
            record.title = details.title
        if details.status:
            record.status = details.status
        if details.release:
            record.release = details.release
        if details.level is not None:
            record.level = details.level
        if details.parent_uid is not None:
            record.parent_uid = details.parent_uid
        record.updated_at = utc_now()

        changed = (
            record.uid,
            record.title,
            record.status,
            record.release,
            record.level,
            record.parent_uid,
            record.parent_wi_id,
        ) != before
        if changed:
            await record.save()

        await TDocDatabase._resolve_parent_wi_ids()

        await WorkItemSpecRecord.objects.filter(wi_id=wi_id).delete()
        spec_links = [WorkItemSpecRecord(link_id=f"{wi_id}|{spec_number}", wi_id=wi_id, spec_number=spec_number) for spec_number in dict.fromkeys(spec_numbers)]
        for i in range(0, len(spec_links), DEFAULT_BULK_BATCH_SIZE):
            await WorkItemSpecRecord.objects.bulk_create(spec_links[i : i + DEFAULT_BULK_BATCH_SIZE])

        await WorkItemCrRecord.objects.filter(wi_id=wi_id).delete()
        cr_links = [
            WorkItemCrRecord(
                link_id=TDocDatabase._cr_link_id(item, wi_id),
                wi_id=wi_id,
                spec_number=item.spec_number,
                cr_number=item.cr_number,
                cr_revision=item.cr_revision,
                cr_title=item.cr_title,
            )
            for item in change_requests
        ]
        for i in range(0, len(cr_links), DEFAULT_BULK_BATCH_SIZE):
            await WorkItemCrRecord.objects.bulk_create(cr_links[i : i + DEFAULT_BULK_BATCH_SIZE])

        return changed

    @staticmethod
    async def list_work_item_crs(wi_id: str) -> list[WorkItemCrRecord]:
        """Return the change requests of a work item, sorted."""
        links = await WorkItemCrRecord.objects.filter(wi_id=wi_id.upper()).all()
        return sorted(links, key=lambda link: (link.spec_number, link.cr_number, link.cr_revision or ""))

    @staticmethod
    async def select_work_items_for_enrichment(
        work_item_ids: Sequence[str] | None = None,
        *,
        limit: int | None = None,
        include_all: bool = False,
    ) -> list[WorkItemRecord]:
        """Select the work items to enrich from the portal pages.

        Defaults to the work items referenced by crawled TDocs plus the ones
        never enriched (no status yet), most TDoc references first.

        Args:
            work_item_ids: Explicit work item IDs; overrides the default selection
            limit: Cap on the number of selected work items
            include_all: Include every catalogue row, not only linked/unenriched

        Returns:
            Selected work item records
        """
        if work_item_ids:
            wanted = [wi_id.upper() for wi_id in work_item_ids]
            records = []
            for wi_id in dict.fromkeys(wanted):
                record = await WorkItemRecord.objects.filter(wi_id=wi_id).first()
                if record is None:
                    _logger.warning("Work item %s is not in the catalogue; enriching anyway", wi_id)
                    record = WorkItemRecord(wi_id=wi_id)
                records.append(record)
            return records

        linked = {link.wi_id for link in await TDocWorkItem.objects.all()}
        records = await WorkItemRecord.objects.all()
        selection = [record for record in records if include_all or record.status is None or record.wi_id in linked]
        selection.sort(key=lambda record: (0 if record.wi_id in linked else 1, -record.tdoc_count, record.wi_id))
        return selection[:limit] if limit is not None else selection

    def _sort_key(
        self,
        config: TDocQueryConfig,
        meeting_map: dict[int, MeetingMetadata],
        fallback: date,
    ) -> Callable[[TDocMetadata], tuple]:
        """Return a sort-key callable for the configured ``sort_key``.

        ``reservation_date`` / ``uploaded_at`` may be ``None``; falling back to
        the opposite source date keeps genuinely-recent docs ordered sensibly.
        """
        if config.sort_key is SortKey.RESERVATION_DATE:
            return lambda record: (record.reservation_date or record.uploaded_at or fallback,)
        if config.sort_key is SortKey.UPLOADED_AT:
            return lambda record: (record.uploaded_at or record.reservation_date or fallback,)
        if config.sort_key is SortKey.TDOC_ID:
            return lambda record: (record.tdoc_id.upper(),)
        # Default: meeting start_date, then tdoc_id (case-insensitive)
        return lambda record: (
            self._meeting_start_date(record, meeting_map, fallback),
            record.tdoc_id.upper(),
        )

    def _apply_pattern_filters(
        self,
        records: list[TDocMetadata],
        config: TDocQueryConfig,
        agenda_map: Mapping[tuple[int, str], str] | None = None,
    ) -> list[TDocMetadata]:
        """Apply all supported include/exclude glob filters."""
        agenda_items = agenda_map or {}
        filtered = records
        filtered = self._filter_by_pattern(filtered, config.source_pattern, lambda record: record.source, exclude=False)
        filtered = self._filter_by_pattern(filtered, config.source_pattern_exclude, lambda record: record.source, exclude=True)
        filtered = self._filter_by_pattern(filtered, config.title_pattern, lambda record: record.title, exclude=False)
        filtered = self._filter_by_pattern(filtered, config.title_pattern_exclude, lambda record: record.title, exclude=True)
        filtered = self._filter_by_pattern(
            filtered,
            config.agenda_pattern,
            lambda record: _agenda_search_text(record, agenda_items),
            exclude=False,
        )
        return self._filter_by_pattern(
            filtered,
            config.agenda_pattern_exclude,
            lambda record: _agenda_search_text(record, agenda_items),
            exclude=True,
        )

    async def _resolve_tbid(self, record: TDocMetadata) -> TDocMetadata:
        """Resolve tbid from the associated meeting and return updated record."""
        if record.meeting_id is None:
            return record
        meeting = await MeetingMetadata.objects.filter(meeting_id=record.meeting_id).first()
        if meeting is None or meeting.tbid is None:
            return record
        return self._clone_tdoc(record, {"tbid": meeting.tbid})

    @staticmethod
    async def _load_meeting_agenda_map(records: Sequence[TDocMetadata]) -> dict[tuple[int, str], str]:
        """Load the stored agenda items of the meetings the records belong to."""
        meeting_ids = sorted({record.meeting_id for record in records if record.meeting_id})
        if not meeting_ids:
            return {}

        agenda_map: dict[tuple[int, str], str] = {}
        for i in range(0, len(meeting_ids), SQLITE_MAX_VARS):
            rows = await MeetingAgendaItem.objects.filter(meeting_id__in=meeting_ids[i : i + SQLITE_MAX_VARS]).all()
            for row in rows:
                agenda_map[(row.meeting_id, row.agenda_nbr)] = row.agenda_text
        return agenda_map

    @staticmethod
    async def _refresh_work_item_catalog(wi_ids: set[str]) -> None:
        """Insert missing work item records and refresh the whole TDoc-count catalogue.

        Counts are recomputed over all links. Catalogue rows are kept even
        without links — they may come from the DynaReport lists
        (``work-items crawl``), so only the count is reset to zero.
        """
        if not wi_ids:
            return

        now = utc_now()
        ordered = sorted(wi_ids)
        existing: set[str] = set()
        for i in range(0, len(ordered), SQLITE_MAX_VARS):
            chunk = ordered[i : i + SQLITE_MAX_VARS]
            existing.update(record.wi_id for record in await WorkItemRecord.objects.filter(wi_id__in=chunk).all())

        missing = [WorkItemRecord(wi_id=wi_id, updated_at=now) for wi_id in ordered if wi_id not in existing]
        if missing:
            await WorkItemRecord.objects.bulk_create(missing)

        counts: dict[str, int] = {}
        for link in await TDocWorkItem.objects.all():
            counts[link.wi_id] = counts.get(link.wi_id, 0) + 1

        for record in await WorkItemRecord.objects.all():
            count = counts.get(record.wi_id, 0)
            if record.tdoc_count != count:
                record.tdoc_count = count
                record.updated_at = now
                await record.save()

    @staticmethod
    def _cr_link_id(item: WorkItemCr, wi_id: str) -> str:
        revision = item.cr_revision or "-"
        return f"{wi_id}|{item.spec_number}|{item.cr_number}|{revision}"

    @staticmethod
    async def _resolve_parent_wi_ids() -> None:
        """Fill ``parent_wi_id`` from ``parent_uid`` via the catalogue UIDs."""
        records = await WorkItemRecord.objects.all()
        by_uid = {record.uid: record.wi_id for record in records if record.uid is not None}
        for record in records:
            if record.parent_uid is None:
                continue
            parent_wi_id = by_uid.get(record.parent_uid)
            if parent_wi_id is not None and record.parent_wi_id != parent_wi_id:
                record.parent_wi_id = parent_wi_id
                await record.save()

    @staticmethod
    async def _get_tdoc(tdoc_id: str) -> TDocMetadata | None:
        """Get a TDoc by ID."""
        return await TDocMetadata.objects.filter(tdoc_id=tdoc_id.upper()).first()

    @staticmethod
    def _meeting_start_date(record: TDocMetadata, meeting_map: dict[int, MeetingMetadata], fallback: date) -> date:
        """Return the meeting start_date for sorting, or fallback if unavailable."""
        if not record.meeting_id:
            return fallback
        meeting = meeting_map.get(record.meeting_id)
        if meeting is None or meeting.start_date is None:
            return fallback
        return meeting.start_date

    @staticmethod
    def _filter_by_retrieved_dates(
        records: list[TDocMetadata],
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> list[TDocMetadata]:
        """Filter records by retrieval datetime bounds."""

        def _normalized_bound(value: datetime, bound: datetime) -> tuple[datetime, datetime]:
            if value.tzinfo is None and bound.tzinfo is not None:
                return value.replace(tzinfo=UTC), bound
            if value.tzinfo is not None and bound.tzinfo is None:
                return value, bound.replace(tzinfo=UTC)
            return value, bound

        filtered = records
        if start_date is not None:
            filtered = [record for record in filtered if record.date_retrieved and (nb := _normalized_bound(record.date_retrieved, start_date))[0] >= nb[1]]
        if end_date is not None:
            filtered = [record for record in filtered if record.date_retrieved and (nb := _normalized_bound(record.date_retrieved, end_date))[0] <= nb[1]]
        return filtered

    @staticmethod
    def _filter_by_meeting_dates(
        records: list[TDocMetadata],
        meeting_map: dict[int, MeetingMetadata],
        meeting_start_date: date | None,
        meeting_end_date: date | None,
    ) -> list[TDocMetadata]:
        """Filter records by start/end date of the related meeting."""
        filtered = records
        if meeting_start_date is not None:
            filtered = [
                record
                for record in filtered
                if (meeting := meeting_map.get(record.meeting_id or -1)) and meeting.start_date and meeting.start_date >= meeting_start_date
            ]
        if meeting_end_date is not None:
            filtered = [
                record
                for record in filtered
                if (meeting := meeting_map.get(record.meeting_id or -1)) and meeting.end_date and meeting.end_date <= meeting_end_date
            ]
        return filtered

    @staticmethod
    def _filter_by_pattern(
        records: list[TDocMetadata],
        values: list[str] | None,
        value_getter: Callable[[TDocMetadata], str | None],
        exclude: bool,
    ) -> list[TDocMetadata]:
        """Apply case-insensitive glob filter to a selected text field.

        Patterns without glob metacharacters (``*``, ``?``, ``[``) are wrapped
        in ``*...*`` so a bare ``ATIAS`` substring-matches rather than failing
        the literal ``fnmatch`` comparison.
        """
        if not values:
            return records
        patterns = [TDocDatabase._normalize_glob(value).lower() for value in values]
        if exclude:
            return [
                record
                for record in records
                if not value_getter(record) or not any(fnmatch.fnmatch(str(value_getter(record)).lower(), pattern) for pattern in patterns)
            ]
        return [
            record for record in records if value_getter(record) and any(fnmatch.fnmatch(str(value_getter(record)).lower(), pattern) for pattern in patterns)
        ]

    @staticmethod
    def _normalize_glob(value: str) -> str:
        """Wrap bare patterns in ``*...*`` so they substring-match by default."""
        if any(ch in value for ch in "*?[]"):
            return value
        return f"*{value}*"

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _prepare_tdoc(metadata: TDocMetadata) -> TDocMetadata:
        """Prepare TDoc metadata for insertion (set defaults).

        Oxyde's ``bulk_create`` uses ``exclude_none=True``, so ``None`` fields
        are dropped from the INSERT payload.  If some rows in a batch have a
        field set while others drop it, oxyde raises ``Missing column``.  We
        normalise nullable fields that vary across data sources to non-``None``
        defaults so every row has a consistent set of columns.
        """
        updates: dict[str, TDocFieldValue] = {}
        if metadata.date_retrieved is None:
            updates["date_retrieved"] = utc_now()
        if metadata.status is None:
            updates["status"] = ""
        if metadata.url is None:
            updates["url"] = ""
        if metadata.is_revision_of is None:
            updates["is_revision_of"] = ""
        if metadata.date_created is None:
            updates["date_created"] = metadata.date_retrieved or utc_now()
        if metadata.reservation_date is None:
            updates["reservation_date"] = metadata.date_retrieved or utc_now()
        if metadata.uploaded_at is None:
            updates["uploaded_at"] = metadata.date_retrieved or utc_now()
        if metadata.tbid is None:
            updates["tbid"] = 0
        for field in ("spec_number", "release", "cr_number", "cr_category"):
            if getattr(metadata, field) is None:
                updates[field] = ""
        if updates:
            return TDocDatabase._clone_tdoc(metadata, updates)
        return metadata

    @staticmethod
    def _tdoc_changed(current: TDocMetadata, candidate: TDocMetadata) -> bool:
        """Check if TDoc metadata has changed."""
        for field in TDocMetadata.__annotations__:
            if field == "date_updated":
                continue
            if getattr(current, field, None) != getattr(candidate, field, None):
                return True
        return False

    @staticmethod
    def _clone_tdoc(metadata: TDocMetadata, updates: dict[str, TDocFieldValue]) -> TDocMetadata:
        """Create a new TDocMetadata instance with updates applied."""
        data = {field: getattr(metadata, field, None) for field in TDocMetadata.__annotations__}
        data.update(updates)
        return TDocMetadata(**data)


def _agenda_search_text(record: TDocMetadata, agenda_map: Mapping[tuple[int, str], str]) -> str:
    """Return the agenda text of a record including its parent agenda items.

    Parent agenda items are matched as well, so a document of agenda item
    ``4.5`` also matches the text of its parent agenda item ``4``.
    """
    parts = [record.agenda_item_text or ""]
    for ancestor in ancestor_agenda_numbers(str(record.agenda_item_nbr)):
        text = agenda_map.get((record.meeting_id, ancestor))
        if text:
            parts.append(text)
    return " | ".join(part for part in parts if part)


def _merge_lead_bodies(current: str | None, incoming: str | None) -> str | None:
    """Merge lead body codes into a comma-separated unique list."""
    parts: list[str] = []
    for value in (current, incoming):
        if not value:
            continue
        for part in value.split(","):
            cleaned = part.strip().upper()
            if cleaned and cleaned not in parts:
                parts.append(cleaned)
    return ",".join(parts) or None


def _get_updatable_fields(model_type: type) -> list[str]:
    return [name for name, f in model_type.model_fields.items() if not getattr(f, "db_pk", False)]


__all__ = ["TDocDatabase"]
