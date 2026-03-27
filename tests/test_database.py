"""Tests for database module."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from packaging.version import Version

from tdoc_crawler.database import DatabaseError, TDocDatabase
from tdoc_crawler.meetings.models import MeetingMetadata, MeetingQueryConfig
from tdoc_crawler.models import SortOrder, WorkingGroup
from tdoc_crawler.tdocs.models import TDocMetadata, TDocQueryConfig


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
                url="https://www.3gpp.org/updated/r1-2301234.zip",
                meeting_id=12345,
                file_size=512000,
                title="Updated Title",
                source="Updated Source",
                contact="Updated Contact",
                tdoc_type="Updated Type",
                for_purpose="Updated Purpose",
                agenda_item_nbr=Version("7.2"),
                agenda_item_text="Updated agenda",
                status="revised",
                is_revision_of=None,
                date_created=None,
                date_retrieved=datetime(2023, 1, 17),
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
