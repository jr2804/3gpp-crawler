"""Tests for database module."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from tdoc_crawler.database import DatabaseError, TDocDatabase
from tdoc_crawler.models import MeetingMetadata, MeetingQueryConfig, QueryConfig, SortOrder, TDocMetadata, WorkingGroup


class TestTDocDatabase:
    """Tests for TDocDatabase class."""

    def _query_all(self, cache_dir: Path) -> QueryConfig:
        return QueryConfig(cache_dir=cache_dir)

    def test_database_initialization(self, test_db_path: Path) -> None:
        """Initialize database and create schema."""

        db = TDocDatabase(test_db_path)
        assert test_db_path.parent.exists()

        with db:
            assert test_db_path.parent.exists()

        assert test_db_path.exists()

    def test_upsert_tdoc(self, test_db_path: Path, sample_tdocs: list[TDocMetadata]) -> None:
        """Insert a TDoc record and validate persistence."""

        with TDocDatabase(test_db_path) as db:
            created, changed = db.upsert_tdoc(sample_tdocs[0])
            assert created is True
            assert changed is False

            results = db.query_tdocs(self._query_all(test_db_path.parent))
            assert len(results) == 1
            assert results[0].tdoc_id == "R1-2301234"

    def test_case_insensitive_query(self, test_db_path: Path, sample_tdocs: list[TDocMetadata]) -> None:
        """Ensure TDoc IDs are matched case-insensitively."""

        with TDocDatabase(test_db_path) as db:
            db.upsert_tdoc(sample_tdocs[0])

            results = db.query_tdocs(QueryConfig(cache_dir=test_db_path.parent, tdoc_ids=["r1-2301234"]))
            assert len(results) == 1
            assert results[0].tdoc_id == "R1-2301234"

            results = db.query_tdocs(QueryConfig(cache_dir=test_db_path.parent, tdoc_ids=["R1-2301234"]))
            assert len(results) == 1

    def test_query_by_working_group(self, test_db_path: Path, sample_tdocs: list[TDocMetadata]) -> None:
        """Filter by working group."""

        with TDocDatabase(test_db_path) as db:
            for tdoc in sample_tdocs:
                db.upsert_tdoc(tdoc)

            ran_results = db.query_tdocs(QueryConfig(cache_dir=test_db_path.parent, working_groups=[WorkingGroup.RAN]))
            assert len(ran_results) == 2
            assert all(result.working_group is WorkingGroup.RAN for result in ran_results)

            sa_results = db.query_tdocs(QueryConfig(cache_dir=test_db_path.parent, working_groups=[WorkingGroup.SA]))
            assert len(sa_results) == 1
            assert sa_results[0].working_group is WorkingGroup.SA

    def test_query_with_limit(self, test_db_path: Path, sample_tdocs: list[TDocMetadata]) -> None:
        """Respect limit parameter when querying TDocs."""

        with TDocDatabase(test_db_path) as db:
            for tdoc in sample_tdocs:
                db.upsert_tdoc(tdoc)

            results = db.query_tdocs(QueryConfig(cache_dir=test_db_path.parent, limit=2))
            assert len(results) == 2

    def test_query_with_date_range(self, test_db_path: Path, sample_tdocs: list[TDocMetadata]) -> None:
        """Apply start and end date filters."""

        with TDocDatabase(test_db_path) as db:
            for tdoc in sample_tdocs:
                db.upsert_tdoc(tdoc)

            start = datetime(2023, 1, 15)
            end = datetime(2023, 1, 20)
            results = db.query_tdocs(QueryConfig(cache_dir=test_db_path.parent, start_date=start, end_date=end))
            assert len(results) == 3

            start = datetime(2023, 1, 20)
            results = db.query_tdocs(QueryConfig(cache_dir=test_db_path.parent, start_date=start))
            assert not results

    def test_get_statistics(self, test_db_path: Path, sample_tdocs: list[TDocMetadata]) -> None:
        """Compute summary statistics for stored TDocs."""

        with TDocDatabase(test_db_path) as db:
            for tdoc in sample_tdocs:
                db.upsert_tdoc(tdoc)

            stats = db.get_statistics()
            assert stats["total_tdocs"] == 3
            assert stats["by_working_group"]["RAN"] == 2
            assert stats["by_working_group"]["SA"] == 1

    def test_crawl_logging(self, test_db_path: Path) -> None:
        """Persist crawl run metadata."""

        with TDocDatabase(test_db_path) as db:
            crawl_id = db.log_crawl_start("tdoc", [WorkingGroup.RAN], incremental=True)
            assert crawl_id > 0

            db.log_crawl_end(crawl_id, items_added=2, items_updated=1, errors_count=0)

    def test_update_existing_tdoc(self, test_db_path: Path, sample_tdocs: list[TDocMetadata]) -> None:
        """Update metadata for existing TDocs."""

        with TDocDatabase(test_db_path) as db:
            db.upsert_tdoc(sample_tdocs[0])
            updated_tdoc = TDocMetadata(
                tdoc_id="R1-2301234",
                url="ftp://ftp.3gpp.org/updated/r1-2301234.zip",
                working_group=WorkingGroup.RAN,
                subgroup="RAN1",
                meeting="RAN1#99",
                meeting_id=None,
                file_size=512000,
                document_type=None,
                checksum=None,
                source_path="/tsg_ran/RAN1/R1-2301234.zip",
                date_created=None,
                date_retrieved=datetime(2023, 1, 17),
            )
            created, changed = db.upsert_tdoc(updated_tdoc)
            assert created is False
            assert changed is True

            results = db.query_tdocs(self._query_all(test_db_path.parent))
            assert len(results) == 1
            assert results[0].meeting == "RAN1#99"
            assert results[0].file_size == 512000

    def test_get_existing_tdoc_ids(self, test_db_path: Path, sample_tdocs: list[TDocMetadata]) -> None:
        """Return existing TDoc identifiers for incremental crawls."""

        with TDocDatabase(test_db_path) as db:
            for tdoc in sample_tdocs:
                db.upsert_tdoc(tdoc)

            existing = db.get_existing_tdoc_ids()
            assert existing == {"R1-2301234", "R2-2301567", "S4-2301890"}
            ran_existing = db.get_existing_tdoc_ids([WorkingGroup.RAN])
            assert ran_existing == {"R1-2301234", "R2-2301567"}

    def test_meeting_upsert_and_query(self, test_db_path: Path) -> None:
        """Persist and query meeting metadata."""

        meeting = MeetingMetadata(
            meeting_id=12345,
            working_group=WorkingGroup.RAN,
            subgroup="RAN1",
            short_name="RAN1#98",
            title="RAN1 Meeting 98",
            start_date=date(2024, 5, 1),
            end_date=date(2024, 5, 5),
            location="Somewhere",
            files_url="https://www.3gpp.org/ftp/tsg_ran/RAN1/RAN1_98/Docs/",
            portal_url="https://portal.3gpp.org/Home.aspx#/meeting?MtgId=12345",
        )

        with TDocDatabase(test_db_path) as db:
            created, changed = db.upsert_meeting(meeting)
            assert created is True
            assert changed is False

            queried = db.query_meetings(
                MeetingQueryConfig(
                    cache_dir=test_db_path.parent,
                    working_groups=None,
                    limit=None,
                    order=SortOrder.DESC,
                    include_without_files=False,
                )
            )
            assert len(queried) == 1
            assert queried[0].meeting_id == 12345

    def test_get_existing_meeting_ids(self, test_db_path: Path) -> None:
        """Retrieve meeting identifiers for incremental meeting crawls."""

        meeting = MeetingMetadata(
            meeting_id=6789,
            working_group=WorkingGroup.SA,
            subgroup="SA4",
            short_name="SA4#134",
            title=None,
            start_date=date(2024, 4, 10),
            end_date=date(2024, 4, 15),
            location="Online",
            files_url="https://www.3gpp.org/ftp/tsg_sa/SA4/SA4_134/Docs/",
            portal_url="https://portal.3gpp.org/Home.aspx#/meeting?MtgId=6789",
        )

        with TDocDatabase(test_db_path) as db:
            db.upsert_meeting(meeting)
            existing = db.get_existing_meeting_ids()
            assert existing == {6789}
            filtered = db.get_existing_meeting_ids([WorkingGroup.SA])
            assert filtered == {6789}

    def test_context_manager(self, test_db_path: Path) -> None:
        """Raise when accessing connection outside active context."""

        db = TDocDatabase(test_db_path)
        with db:
            assert db.connection is not None

        with pytest.raises(DatabaseError):
            _ = db.connection


if __name__ == "__main__":
    pass
# end of file
