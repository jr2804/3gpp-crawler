"""Tests for database module."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from tdoc_crawler.database import DatabaseError, TDocDatabase
from tdoc_crawler.database.oxyde_models import MeetingMetadata, TDocMetadata
from tdoc_crawler.meetings.models import MeetingQueryConfig
from tdoc_crawler.models import SortOrder, WorkingGroup
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.workitems import WorkItem, WorkItemCr, WorkItemDetails


@pytest.mark.asyncio
class TestTDocDatabase:
    """Tests for TDocDatabase class."""

    async def test_database_initialization(self, test_db_path: Path) -> None:
        """Initialize database and create schema."""
        db = TDocDatabase(test_db_path)
        assert test_db_path.parent.exists()

        async with db:
            assert test_db_path.parent.exists()

        assert test_db_path.exists()

    async def test_upsert_tdoc(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Insert a TDoc record and validate persistence."""
        async with TDocDatabase(test_db_path) as db:
            await self._insert_sample_meetings(db, sample_meetings)
            created, changed = await db.upsert_tdoc(sample_tdocs[0])
            assert created is True
            assert changed is False

            results = await db.query_tdocs(self._query_all(test_db_path.parent))
            assert len(results) == 1
            assert results[0].tdoc_id == "R1-2301234"

    async def test_case_insensitive_query(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Ensure TDoc IDs are matched case-insensitively."""
        async with TDocDatabase(test_db_path) as db:
            await self._insert_sample_meetings(db, sample_meetings)
            _ = await db.upsert_tdoc(sample_tdocs[0])

            results = await db.query_tdocs(TDocQueryConfig(tdoc_ids=["r1-2301234"]))
            assert len(results) == 1
            assert results[0].tdoc_id == "R1-2301234"

            results = await db.query_tdocs(TDocQueryConfig(tdoc_ids=["R1-2301234"]))
            assert len(results) == 1

    async def test_query_by_working_group(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Filter by working group."""
        async with TDocDatabase(test_db_path) as db:
            await self._insert_sample_meetings(db, sample_meetings)
            for tdoc in sample_tdocs:
                _ = await db.upsert_tdoc(tdoc)

            ran_results = await db.query_tdocs(TDocQueryConfig(working_groups=[WorkingGroup.RAN]))
            assert len(ran_results) == 2

            sa_results = await db.query_tdocs(TDocQueryConfig(working_groups=[WorkingGroup.SA]))
            assert len(sa_results) == 1

    async def test_query_by_subgroup(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Filter by sub-working group through the meeting linkage."""
        async with TDocDatabase(test_db_path) as db:
            await self._insert_sample_meetings(db, sample_meetings)
            for tdoc in sample_tdocs:
                _ = await db.upsert_tdoc(tdoc)

            s4_results = await db.query_tdocs(TDocQueryConfig(subgroups=["S4"]))
            assert [tdoc.tdoc_id for tdoc in s4_results] == ["S4-2301890"]

            ran1_results = await db.query_tdocs(TDocQueryConfig(subgroups=["RAN1"]))
            assert [tdoc.tdoc_id for tdoc in ran1_results] == ["R1-2301234"]

            both = await db.query_tdocs(TDocQueryConfig(subgroups=["R1", "R2"]))
            assert sorted(tdoc.tdoc_id for tdoc in both) == ["R1-2301234", "R2-2301567"]

    async def test_store_tdoc_work_items_and_filter(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Work item links are stored and usable as a query filter."""
        async with TDocDatabase(test_db_path) as db:
            await self._insert_sample_meetings(db, sample_meetings)
            for tdoc in sample_tdocs:
                _ = await db.upsert_tdoc(tdoc)

            await db.store_tdoc_work_items(
                {
                    "R1-2301234": ["ULBC-MED", "FS_ULBC"],
                    "S4-2301890": ["ulbc-med"],
                }
            )

            ulbc = await db.query_tdocs(TDocQueryConfig(work_items=["ULBC-MED"]))
            assert sorted(tdoc.tdoc_id for tdoc in ulbc) == ["R1-2301234", "S4-2301890"]

            fs_ulbc = await db.query_tdocs(TDocQueryConfig(work_items=["fs_ulbc"]))
            assert [tdoc.tdoc_id for tdoc in fs_ulbc] == ["R1-2301234"]

            assert await db.query_tdocs(TDocQueryConfig(work_items=["UNKNOWN-WI"])) == []

    async def test_list_work_items_with_counts(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """The work item catalogue exposes TDoc counts, most-used first."""
        async with TDocDatabase(test_db_path) as db:
            await self._insert_sample_meetings(db, sample_meetings)
            for tdoc in sample_tdocs:
                _ = await db.upsert_tdoc(tdoc)

            await db.store_tdoc_work_items(
                {
                    "R1-2301234": ["ULBC-MED", "FS_ULBC"],
                    "S4-2301890": ["ULBC-MED"],
                }
            )

            records = await db.list_work_items()
            assert [(record.wi_id, record.tdoc_count) for record in records] == [
                ("ULBC-MED", 2),
                ("FS_ULBC", 1),
            ]

            sa_records = await db.list_work_items(working_group=WorkingGroup.SA)
            assert [record.wi_id for record in sa_records] == ["ULBC-MED"]

    async def test_store_tdoc_work_items_replaces_missing_links(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Re-storing a TDoc drops work items that disappeared from its row."""
        async with TDocDatabase(test_db_path) as db:
            await self._insert_sample_meetings(db, sample_meetings)
            for tdoc in sample_tdocs:
                _ = await db.upsert_tdoc(tdoc)

            await db.store_tdoc_work_items({"R1-2301234": ["ULBC-MED", "FS_ULBC"]})
            await db.store_tdoc_work_items({"R1-2301234": ["ULBC-MED"]})

            records = await db.list_work_items()
            assert [(record.wi_id, record.tdoc_count) for record in records] == [
                ("ULBC-MED", 1),
                ("FS_ULBC", 0),
            ]

            query = await db.query_tdocs(TDocQueryConfig(work_items=["FS_ULBC"]))
            assert query == []

    async def test_store_work_items_catalogue(
        self,
        test_db_path: Path,
    ) -> None:
        """DynaReport rows populate the catalogue; enrichment adds hierarchy and links."""
        async with TDocDatabase(test_db_path) as db:
            stored = await db.store_work_items(
                [
                    WorkItem(
                        wi_id="ULBC-MED",
                        uid=1120096,
                        title="Ultra Low Bitrate Speech Codec",
                        release="Rel-20",
                        level=2,
                        lead_body="S4",
                    ),
                    WorkItem(
                        wi_id="5GSAT_PH4",
                        uid=1080054,
                        title="Satellite access - Phase 4",
                        release="Rel-20",
                        level=1,
                        lead_body="SP",
                    ),
                ]
            )

            assert stored == 2

            records = await db.list_work_items(release="rel-20")
            ulbc = next(record for record in records if record.wi_id == "ULBC-MED")
            assert ulbc.uid == 1120096
            assert ulbc.lead_body == "S4"
            assert ulbc.level == 2
            assert ulbc.title == "Ultra Low Bitrate Speech Codec"
            # Enrichment-only fields are untouched by the list crawl.
            assert ulbc.status is None
            assert ulbc.parent_wi_id is None

            assert [record.wi_id for record in await db.list_work_items(release="Rel-19")] == []
            assert [record.wi_id for record in await db.list_work_items(lead_body="s4")] == ["ULBC-MED"]

            enriched = await db.store_work_item_details(
                "ulbc-med",
                WorkItemDetails(
                    uid=1120096,
                    wi_id="ULBC-MED",
                    title="Ultra Low Bitrate Speech Codec",
                    status="PCG approved",
                    release="Rel-20",
                    level=2,
                    parent_uid=1080054,
                    parent_title="Satellite access - Phase 4",
                ),
                spec_numbers=["26.114", "26.965"],
                change_requests=[
                    WorkItemCr(spec_number="26.965", cr_number="2", cr_revision="5", cr_title="ULBC corrections"),
                ],
            )
            assert enriched is True

            assert [record.wi_id for record in await db.list_work_items(status="PCG approved")] == ["ULBC-MED"]
            assert [record.wi_id for record in await db.list_work_items(parent_wi_id="5gsat_ph4")] == ["ULBC-MED"]
            assert await db.list_work_item_specs("ulbc-med") == ["26.114", "26.965"]
            crs = await db.list_work_item_crs("ULBC-MED")
            assert [(cr.spec_number, cr.cr_number, cr.cr_revision) for cr in crs] == [("26.965", "0002", "5")]

    async def test_select_work_items_for_enrichment(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Default selection covers linked and never-enriched work items."""
        async with TDocDatabase(test_db_path) as db:
            await self._insert_sample_meetings(db, sample_meetings)
            for tdoc in sample_tdocs:
                _ = await db.upsert_tdoc(tdoc)
            await db.store_work_items(
                [
                    WorkItem(wi_id="LINKED-WI", uid=1120001, lead_body="S4"),
                    WorkItem(wi_id="NEW-WI", uid=1120002, lead_body="S4"),
                    WorkItem(wi_id="DONE-WI", uid=1120003, lead_body="S4"),
                ]
            )
            await db.store_tdoc_work_items({"R1-2301234": ["LINKED-WI"]})
            await db.store_work_item_details(
                "DONE-WI",
                WorkItemDetails(uid=1120003, wi_id="DONE-WI", status="closed"),
                spec_numbers=[],
                change_requests=[],
            )

            default_ids = [record.wi_id for record in await db.select_work_items_for_enrichment()]
            assert default_ids == ["LINKED-WI", "NEW-WI"]

            all_ids = [record.wi_id for record in await db.select_work_items_for_enrichment(include_all=True)]
            assert all_ids == ["LINKED-WI", "DONE-WI", "NEW-WI"]

            explicit = [record.wi_id for record in await db.select_work_items_for_enrichment(["done-wi"])]
            assert explicit == ["DONE-WI"]

            limited = await db.select_work_items_for_enrichment(include_all=True, limit=2)
            assert [record.wi_id for record in limited] == ["LINKED-WI", "DONE-WI"]

    async def test_store_work_items_keeps_tdoc_counts(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Crawling the DynaReport lists does not wipe TDoc counts from document lists."""
        async with TDocDatabase(test_db_path) as db:
            await self._insert_sample_meetings(db, sample_meetings)
            for tdoc in sample_tdocs:
                _ = await db.upsert_tdoc(tdoc)
            await db.store_tdoc_work_items({"R1-2301234": ["ULBC-MED"]})

            await db.store_work_items([WorkItem(wi_id="ULBC-MED", uid=1120096, title="Ultra Low Bitrate Speech Codec", release="Rel-20")])

            records = await db.list_work_items()
            assert [(record.wi_id, record.tdoc_count) for record in records] == [("ULBC-MED", 1)]

    async def test_query_tdocs_by_spec_number(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """TDocs can be filtered by the specification named in their document list."""
        async with TDocDatabase(test_db_path) as db:
            await self._insert_sample_meetings(db, sample_meetings)
            for tdoc in sample_tdocs:
                _ = await db.upsert_tdoc(tdoc.model_copy(update={"spec_number": "26.114"}))
            _ = await db.upsert_tdoc(sample_tdocs[0].model_copy(update={"tdoc_id": "R1-2309999", "spec_number": "38.211"}))

            matches = await db.query_tdocs(TDocQueryConfig(spec_numbers=["26114"]))
            assert sorted(tdoc.tdoc_id for tdoc in matches) == sorted(tdoc.tdoc_id for tdoc in sample_tdocs)
            assert "R1-2309999" not in {tdoc.tdoc_id for tdoc in matches}

            assert await db.query_tdocs(TDocQueryConfig(spec_numbers=["99.999"])) == []

    async def test_bulk_upsert_mixed_spec_and_cr_columns(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """A batch mixing filled and empty document-list columns must not fail."""
        async with TDocDatabase(test_db_path) as db:
            await self._insert_sample_meetings(db, sample_meetings)
            batch = [
                sample_tdocs[0].model_copy(
                    update={
                        "tdoc_id": "S4-2309001",
                        "spec_number": "26.114",
                        "release": "Rel-19",
                        "cr_number": "0003",
                        "cr_category": "F",
                    }
                ),
                sample_tdocs[0].model_copy(update={"tdoc_id": "S4-2309002"}),
            ]

            inserted, changed = await db.bulk_upsert_tdocs(batch)

            assert inserted == 2
            assert changed == 0

            stored = await db.query_tdocs(TDocQueryConfig(spec_numbers=["26.114"]))
            assert [tdoc.tdoc_id for tdoc in stored] == ["S4-2309001"]
            assert stored[0].cr_number == "0003"
            assert stored[0].cr_category == "F"

    async def test_query_by_unknown_subgroup_returns_nothing(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """An unpopulated subgroup filters everything out instead of raising."""
        async with TDocDatabase(test_db_path) as db:
            await self._insert_sample_meetings(db, sample_meetings)
            for tdoc in sample_tdocs:
                _ = await db.upsert_tdoc(tdoc)

            assert await db.query_tdocs(TDocQueryConfig(subgroups=["C1"])) == []

    async def test_query_with_limit(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Respect limit parameter when querying TDocs."""
        async with TDocDatabase(test_db_path) as db:
            await self._insert_sample_meetings(db, sample_meetings)
            for tdoc in sample_tdocs:
                _ = await db.upsert_tdoc(tdoc)

            results = await db.query_tdocs(TDocQueryConfig(limit=2))
            assert len(results) == 2

    async def test_query_with_date_range(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Apply start and end date filters."""
        async with TDocDatabase(test_db_path) as db:
            await self._insert_sample_meetings(db, sample_meetings)
            for tdoc in sample_tdocs:
                _ = await db.upsert_tdoc(tdoc)

            start = datetime(2023, 1, 15, tzinfo=UTC)
            end = datetime(2023, 1, 20, tzinfo=UTC)
            results = await db.query_tdocs(TDocQueryConfig(start_date=start, end_date=end))
            assert len(results) == 3

            start = datetime(2023, 1, 20, tzinfo=UTC)
            results = await db.query_tdocs(TDocQueryConfig(start_date=start))
            assert not results

    async def test_get_statistics(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Compute summary statistics for stored TDocs."""
        async with TDocDatabase(test_db_path) as db:
            await self._insert_sample_meetings(db, sample_meetings)
            for tdoc in sample_tdocs:
                _ = await db.upsert_tdoc(tdoc)

            stats: dict[str, object] = await db.get_statistics()
            assert isinstance(stats, dict)
            assert stats["total_tdocs"] == 3
            by_wg = stats.get("by_working_group", {})
            assert isinstance(by_wg, dict)
            assert by_wg["RAN"] == 2
            assert by_wg["SA"] == 1

    async def test_crawl_logging(self, test_db_path: Path) -> None:
        """Persist crawl run metadata."""
        async with TDocDatabase(test_db_path) as db:
            crawl_id = await db.log_crawl_start("tdoc", [WorkingGroup.RAN.value], incremental=True)
            assert crawl_id

            await db.log_crawl_end(crawl_id, items_added=2, items_updated=1, errors_count=0)

    async def test_update_existing_tdoc(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Update metadata for existing TDocs."""
        async with TDocDatabase(test_db_path) as db:
            await self._insert_sample_meetings(db, sample_meetings)
            _ = await db.upsert_tdoc(sample_tdocs[0])
            updated_tdoc = TDocMetadata(
                tdoc_id="R1-2301234",
                tbid=373,
                url="https://www.3gpp.org/updated/r1-2301234.zip",
                meeting_id=12345,
                file_size=512000,
                title="Updated Title",
                source="Updated Source",
                contact="Updated Contact",
                tdoc_type="Updated Type",
                for_purpose="Updated Purpose",
                agenda_item_nbr="7.2",
                agenda_item_text="Updated agenda",
                status="revised",
                is_revision_of="",
                date_created=datetime(2023, 1, 15, tzinfo=UTC),
                date_retrieved=datetime(2023, 1, 17, tzinfo=UTC),
                validated=False,
                validation_failed=False,
            )
            created, changed = await db.upsert_tdoc(updated_tdoc)
            assert created is False
            assert changed is True

            results = await db.query_tdocs(self._query_all(test_db_path.parent))
            assert len(results) == 1
            assert results[0].title == "Updated Title"
            assert results[0].file_size == 512000

    async def test_get_existing_tdoc_ids(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Return existing TDoc identifiers for incremental crawls."""
        async with TDocDatabase(test_db_path) as db:
            await self._insert_sample_meetings(db, sample_meetings)
            for tdoc in sample_tdocs:
                _ = await db.upsert_tdoc(tdoc)

            existing = await db.get_existing_tdoc_ids()
            assert existing == {"R1-2301234", "R2-2301567", "S4-2301890"}
            ran_existing = await db.get_existing_tdoc_ids([WorkingGroup.RAN])
            assert ran_existing == {"R1-2301234", "R2-2301567"}

    async def test_meeting_upsert_and_query(self, test_db_path: Path) -> None:
        """Persist and query meeting metadata."""
        meeting = MeetingMetadata(
            meeting_id=12345,
            tbid=373,
            subtb=379,
            short_name="RAN1#98",
            title="RAN1 Meeting 98",
            start_date=date(2024, 5, 1),
            end_date=date(2024, 5, 5),
            location="Somewhere",
            files_url="https://www.3gpp.org/ftp/tsg_ran/RAN1/RAN1_98/Docs/",
            portal_url="https://portal.3gpp.org/Home.aspx#/meeting?MtgId=12345",
            tdoc_count=0,
        )

        async with TDocDatabase(test_db_path) as db:
            created, changed = await db.upsert_meeting(meeting)
            assert created is True
            assert changed is False

            queried = await db.query_meetings(
                MeetingQueryConfig(
                    working_groups=None,
                    subgroups=None,
                    limit=None,
                    order=SortOrder.DESC,
                    include_without_files=False,
                )
            )
            assert len(queried) == 1
            assert queried[0].meeting_id == 12345

    async def test_get_existing_meeting_ids(self, test_db_path: Path) -> None:
        """Retrieve meeting identifiers for incremental meeting crawls."""
        meeting = MeetingMetadata(
            meeting_id=6789,
            tbid=375,
            subtb=387,
            short_name="SA4#134",
            title=None,
            start_date=date(2024, 4, 10),
            end_date=date(2024, 4, 15),
            location="Online",
            files_url="https://www.3gpp.org/ftp/tsg_sa/SA4/SA4_134/Docs/",
            portal_url="https://portal.3gpp.org/Home.aspx#/meeting?MtgId=6789",
            tdoc_count=0,
        )

        async with TDocDatabase(test_db_path) as db:
            _ = await db.upsert_meeting(meeting)
            existing = await db.get_existing_meeting_ids()
            assert existing == {6789}
            filtered = await db.get_existing_meeting_ids([WorkingGroup.SA])
            assert filtered == {6789}

    async def test_context_manager(self, test_db_path: Path) -> None:
        """Raise when accessing connection outside active context."""
        db = TDocDatabase(test_db_path)
        async with db:
            assert db.connection is not None

        with pytest.raises(DatabaseError):
            _ = db.connection

    async def test_schema_mismatch_raises(self, test_db_path: Path) -> None:
        """Out-of-date DB schema must raise DatabaseError('schema-mismatch').

        No migrations by design — callers must regenerate the DB. This test
        replaces the old migration test from #5 since we no longer migrate.
        """
        test_db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(test_db_path) as conn:
            # Simulate an old DB: only the columns that existed before #5.
            conn.execute("CREATE TABLE tdocmetadata (tdoc_id TEXT PRIMARY KEY, title TEXT)")

        with pytest.raises(DatabaseError, match="schema-mismatch"):
            async with TDocDatabase(test_db_path):
                pass

    def _query_all(self, cache_dir: Path) -> TDocQueryConfig:
        _ = cache_dir
        return TDocQueryConfig()

    @staticmethod
    async def _insert_sample_meetings(database: TDocDatabase, meetings: list[dict[str, object]]) -> None:
        for meeting_dict in meetings:
            meeting_id = int(str(meeting_dict.get("meeting_id", 0)))
            tbid = int(str(meeting_dict.get("tbid", 0)))
            subtb_raw = meeting_dict.get("subtb")
            subtb = int(str(subtb_raw)) if subtb_raw is not None else None
            short_name = str(meeting_dict.get("short_name", ""))
            location_raw = meeting_dict.get("location")
            location = str(location_raw) if location_raw else None
            files_url_raw = meeting_dict.get("files_url")
            files_url = str(files_url_raw) if files_url_raw else None
            start_date_raw = meeting_dict.get("start_date")
            end_date_raw = meeting_dict.get("end_date")

            start_date = date.fromisoformat(str(start_date_raw)) if start_date_raw else None
            end_date = date.fromisoformat(str(end_date_raw)) if end_date_raw else None

            meeting_metadata = MeetingMetadata(
                meeting_id=meeting_id,
                tbid=tbid,
                subtb=subtb,
                short_name=short_name,
                title=None,
                start_date=start_date,
                end_date=end_date,
                location=location,
                files_url=files_url,
                portal_url=None,
                tdoc_count=0,
            )

            _result: Any = await database.upsert_meeting(meeting_metadata)
            _ = _result


if __name__ == "__main__":
    pass
# end of file
