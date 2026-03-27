"""Tests for crawler module."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup
from packaging.version import Version

from tdoc_crawler.constants.patterns import EXCLUDED_DIRS, TDOC_PATTERN
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.meetings.models import MeetingMetadata
from tdoc_crawler.models import WorkingGroup
from tdoc_crawler.models.subworking_groups import CODE_INDEX
from tdoc_crawler.parsers.meetings import parse_meeting_row, parse_single_date
from tdoc_crawler.tdocs.models import TDocCrawlConfig, TDocMetadata, TDocQueryConfig
from tdoc_crawler.tdocs.operations import TDocCrawler


class TestTDocCrawler:
    """Tests for TDocCrawler class."""

    @pytest.mark.asyncio
    async def test_crawler_initialization(self, test_db_path: Path) -> None:
        """Ensure crawler stores the provided database instance."""
        async with TDocDatabase(test_db_path) as database:
            crawler = TDocCrawler(database)
            assert crawler.database is database

    def test_excluded_dirs(self) -> None:
        """Ensure excluded directory registry contains expected entries."""
        assert {"Inbox", "Draft", "Drafts", "Agenda", "Invitation", "Report"}.issubset(EXCLUDED_DIRS)

    def test_tdoc_pattern(self) -> None:
        """Verify TDoc filename regex matches expected inputs."""
        assert TDOC_PATTERN.search("R1-2301234.zip")
        assert TDOC_PATTERN.search("S4-2301890.zip")
        assert TDOC_PATTERN.search("C1-2300456.zip")
        assert TDOC_PATTERN.search("r1-2301234.ZIP")
        assert TDOC_PATTERN.search("S1-2300456.txt")
        assert TDOC_PATTERN.search("r3-2300456.TXT")
        assert not TDOC_PATTERN.search("README.txt")
        assert not TDOC_PATTERN.search("data.csv")

    @patch("tdoc_crawler.tdocs.operations.crawl.fetch_meeting_document_list_subinterpreter")
    @pytest.mark.asyncio
    async def test_crawl_connection_failure(
        self,
        mock_fetch: MagicMock,
        test_db_path: Path,
    ) -> None:
        """Handle document list fetch failures gracefully."""
        mock_fetch.side_effect = OSError("Connection refused")

        async with TDocDatabase(test_db_path) as database:
            meeting = _create_test_meeting()
            _ = await database.upsert_meeting(meeting)

            crawler = TDocCrawler(database)
            config = TDocCrawlConfig(
                working_groups=[WorkingGroup.RAN],
                subgroups=None,
                meeting_ids=None,
                start_date=None,
                end_date=None,
                incremental=False,
                force_revalidate=False,
                workers=1,
                overall_timeout=None,
                timeout=1,
                max_retries=3,
                target_ids=None,
            )
            result = await crawler.crawl(config)

        assert result.processed == 0
        assert result.inserted == 0
        assert result.updated == 0
        assert result.errors

    @patch("tdoc_crawler.tdocs.operations.crawl.fetch_meeting_document_list_subinterpreter")
    @pytest.mark.asyncio
    async def test_crawl_collects_tdocs(
        self,
        mock_fetch: MagicMock,
        test_db_path: Path,
    ) -> None:
        """Collect TDocs from document list and persist them to the database."""
        tdoc = TDocMetadata(
            tdoc_id="R1-2301234",
            meeting_id=12345,
            title="Test Contribution",
            source="Test Corp",
            contact="J. Doe",
            agenda_item_nbr=Version("1.0"),
            url=None,
            tdoc_type="unknown",
            for_purpose="unknown",
            agenda_item_text="Unknown",
            status=None,
            is_revision_of=None,
            date_created=None,
            validated=False,
            validation_failed=False,
            file_size=2048,
        )
        mock_fetch.return_value = json.dumps([tdoc.model_dump_json()])

        async with TDocDatabase(test_db_path) as database:
            meeting = _create_test_meeting()
            _ = await database.upsert_meeting(meeting)

            crawler = TDocCrawler(database)
            config = TDocCrawlConfig(
                working_groups=[WorkingGroup.RAN],
                subgroups=None,
                meeting_ids=None,
                start_date=None,
                end_date=None,
                incremental=False,
                force_revalidate=False,
                workers=1,
                overall_timeout=10,
                timeout=30,
                max_retries=3,
                target_ids=None,
            )
            result = await crawler.crawl(config)
            assert result.processed == 1
            assert result.inserted == 1
            assert result.updated == 0
            assert not result.errors

            stored = await database.query_tdocs(TDocQueryConfig())
            assert len(stored) == 1
            assert stored[0].tdoc_id == "R1-2301234"
            assert stored[0].file_size == 2048

    @patch("tdoc_crawler.tdocs.operations.crawl.fetch_meeting_document_list_subinterpreter")
    @pytest.mark.asyncio
    async def test_crawl_targets_specific_ids(
        self,
        mock_fetch: MagicMock,
        test_db_path: Path,
    ) -> None:
        """Respect target identifiers by only persisting requested TDocs."""
        tdoc1 = TDocMetadata(
            tdoc_id="R1-2301234",
            meeting_id=12345,
            title="Wanted Contribution",
            source="Test Corp",
            contact="J. Doe",
            agenda_item_nbr=Version("1.0"),
            url=None,
            tdoc_type="unknown",
            for_purpose="unknown",
            agenda_item_text="Unknown",
            status=None,
            is_revision_of=None,
            date_created=None,
            validated=False,
            validation_failed=False,
            file_size=None,
        )
        tdoc2 = TDocMetadata(
            tdoc_id="R1-2305678",
            meeting_id=12345,
            title="Unwanted Contribution",
            source="Other Corp",
            contact="A. Smith",
            agenda_item_nbr=Version("2.0"),
            url=None,
            tdoc_type="unknown",
            for_purpose="unknown",
            agenda_item_text="Unknown",
            status=None,
            is_revision_of=None,
            date_created=None,
            validated=False,
            validation_failed=False,
            file_size=None,
        )
        mock_fetch.return_value = json.dumps(
            [
                tdoc1.model_dump_json(),
                tdoc2.model_dump_json(),
            ]
        )

        async with TDocDatabase(test_db_path) as database:
            meeting = _create_test_meeting()
            _ = await database.upsert_meeting(meeting)

            crawler = TDocCrawler(database)
            config = TDocCrawlConfig(
                working_groups=[WorkingGroup.RAN],
                subgroups=None,
                meeting_ids=None,
                start_date=None,
                end_date=None,
                incremental=False,
                force_revalidate=False,
                workers=1,
                overall_timeout=10,
                timeout=5,
                max_retries=3,
                target_ids=["R1-2301234"],
            )
            result = await crawler.crawl(config)

            assert result.processed == 1
            assert result.inserted == 1
            assert result.updated == 0
            stored = await database.query_tdocs(TDocQueryConfig())
            assert {record.tdoc_id for record in stored} == {"R1-2301234"}


def _create_test_meeting() -> MeetingMetadata:
    """Create a reusable test meeting for TDocCrawler tests."""
    return MeetingMetadata(
        meeting_id=12345,
        tbid=373,
        subtb=379,
        short_name="RAN1#98",
        title="RAN1 Meeting #98",
        start_date=date(2024, 1, 15),
        end_date=date(2024, 1, 19),
        location="Paris, France",
        files_url="https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/RAN1_98/Docs/",
        portal_url="https://portal.3gpp.org/Home.aspx#/meeting?MtgId=12345",
        tdoc_count=0,
    )


class TestMeetingCrawler:
    """Tests for MeetingCrawler class."""

    def test_parse_single_date(self, test_db_path: Path) -> None:
        """Verify single date parsing from text."""
        _ = test_db_path
        # Regular hyphen-minus (U+002D)
        assert parse_single_date("2025-10-20") == date(2025, 10, 20)
        assert parse_single_date("Meeting on 2025-10-20") == date(2025, 10, 20)
        # Non-breaking hyphen (U+2011) - intentionally testing Unicode characters
        assert parse_single_date("2027\u201109\u201120") == date(2027, 9, 20)
        # En dash (U+2013) - intentionally testing Unicode characters
        assert parse_single_date("2026\u201303\u201315") == date(2026, 3, 15)
        # Empty/invalid cases
        assert parse_single_date("") is None
        assert parse_single_date("No date here") is None

    def test_parse_meeting_row_with_separate_date_columns(self, test_db_path: Path) -> None:
        """Verify meeting row parsing with start and end dates in separate columns."""
        html = """
        <tr>
            <td><a href="https://portal.3gpp.org/Home.aspx#/meeting?MtgId=12345">SA4#134</a></td>
            <td>Meeting Title</td>
            <td>Paris, France</td>
            <td>2025-10-20</td>
            <td>2025-10-24</td>
            <td>Info</td>
            <td><a href="https://www.3gpp.org/ftp/tsg_sa/WG4_Codec/TSGS4_134/Docs/">Files</a></td>
            <td>Extra</td>
        </tr>
        """
        soup = BeautifulSoup(html, "lxml")
        row = soup.find("tr")
        assert row is not None
        cells = row.find_all("td")

        # Create get_subtb callback for subtb lookup
        def get_subtb(subgroup_code: str) -> int | None:
            record = CODE_INDEX.get(subgroup_code.upper())
            return record.subtb if record else None

        meeting = parse_meeting_row(cells, WorkingGroup.SA, "S4", get_subtb=get_subtb)

        assert meeting.meeting_id == 12345
        assert meeting.title == "Meeting Title"
        assert meeting.start_date == date(2025, 10, 20)
        assert meeting.end_date == date(2025, 10, 24)
        assert meeting.location == "Paris, France"
        assert meeting.tbid == WorkingGroup.SA.tbid
        assert meeting.tdoc_count == 0


if __name__ == "__main__":
    pass
# end of file
