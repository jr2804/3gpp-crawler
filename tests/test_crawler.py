"""Tests for crawler module."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup

from tdoc_crawler.crawlers import EXCLUDED_DIRS, TDOC_PATTERN, MeetingCrawler, TDocCrawler
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import QueryConfig, TDocCrawlConfig, WorkingGroup


class TestTDocCrawler:
    """Tests for TDocCrawler class."""

    def test_crawler_initialization(self, test_db_path: Path) -> None:
        """Ensure crawler stores the provided database instance."""

        with TDocDatabase(test_db_path) as database:
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

    @patch("tdoc_crawler.crawlers.tdocs.requests.Session")
    def test_crawl_connection_failure(
        self,
        mock_session_class: MagicMock,
        test_db_path: Path,
    ) -> None:
        """Handle HTTP connection failures gracefully."""

        mock_session = MagicMock()
        mock_session.get.side_effect = OSError("Connection refused")
        mock_session_class.return_value = mock_session

        with TDocDatabase(test_db_path) as database:
            crawler = TDocCrawler(database)
            config = TDocCrawlConfig(
                cache_dir=test_db_path.parent,
                working_groups=[WorkingGroup.RAN],
                incremental=False,
                max_retries=1,
                timeout=1,
                verbose=False,
            )
            result = crawler.crawl(config)

        assert result.processed == 0
        assert result.inserted == 0
        assert result.updated == 0
        assert result.errors

    @patch("tdoc_crawler.crawlers.tdocs.requests.Session")
    def test_crawl_collects_tdocs(
        self,
        mock_session_class: MagicMock,
        test_db_path: Path,
    ) -> None:
        """Collect TDocs and persist them to the database."""
        from tdoc_crawler.models import MeetingMetadata

        # Mock HTML directory listing
        html_content = """
        <html><body>
        <a href="R1-2301234.zip">R1-2301234.zip</a> 2048 bytes
        </body></html>
        """

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.text = html_content
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response
        mock_session.close.return_value = None
        mock_session_class.return_value = mock_session

        with TDocDatabase(test_db_path) as database:
            # Add a sample meeting with files_url
            meeting = MeetingMetadata(
                meeting_id=12345,
                tbid=373,  # RAN
                subtb=379,  # RAN1
                working_group=WorkingGroup.RAN,
                subgroup="R1",
                short_name="RAN1#98",
                title="RAN1 Meeting #98",
                start_date=date(2024, 1, 15),
                end_date=date(2024, 1, 19),
                location="Paris, France",
                files_url="https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/RAN1_98/Docs/",
                portal_url="https://portal.3gpp.org/Home.aspx#/meeting?MtgId=12345",
            )
            database.upsert_meeting(meeting)

            crawler = TDocCrawler(database)
            config = TDocCrawlConfig(
                cache_dir=test_db_path.parent,
                working_groups=[WorkingGroup.RAN],
                incremental=False,
                max_retries=3,
                timeout=30,
                verbose=False,
            )
            result = crawler.crawl(config)
            assert result.processed == 1
            assert result.inserted == 1
            assert result.updated == 0
            assert not result.errors

            stored = database.query_tdocs(QueryConfig(cache_dir=test_db_path.parent))
            assert len(stored) == 1
            assert stored[0].tdoc_id == "R1-2301234"
            assert stored[0].file_size == 2048

    @patch("tdoc_crawler.crawlers.tdocs.requests.Session")
    def test_crawl_targets_specific_ids(
        self,
        mock_session_class: MagicMock,
        test_db_path: Path,
    ) -> None:
        """Respect target identifiers by only persisting requested TDocs."""
        from tdoc_crawler.models import MeetingMetadata

        # Mock HTML directory listing with multiple files
        html_content = """
        <html><body>
        <a href="R1-2301234.zip">R1-2301234.zip</a> 2048 bytes<br>
        <a href="R1-2305678.zip">R1-2305678.zip</a> 4096 bytes
        </body></html>
        """

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.text = html_content
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response
        mock_session.close.return_value = None
        mock_session_class.return_value = mock_session

        with TDocDatabase(test_db_path) as database:
            # Add a sample meeting with files_url
            meeting = MeetingMetadata(
                meeting_id=12345,
                tbid=373,  # RAN
                subtb=379,  # RAN1
                working_group=WorkingGroup.RAN,
                subgroup="R1",
                short_name="RAN1#98",
                title="RAN1 Meeting #98",
                start_date=date(2024, 1, 15),
                end_date=date(2024, 1, 19),
                location="Paris, France",
                files_url="https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/RAN1_98/Docs/",
                portal_url="https://portal.3gpp.org/Home.aspx#/meeting?MtgId=12345",
            )
            database.upsert_meeting(meeting)

            crawler = TDocCrawler(database)
            config = TDocCrawlConfig(
                cache_dir=test_db_path.parent,
                working_groups=[WorkingGroup.RAN],
                incremental=False,
                max_retries=1,
                timeout=5,
                verbose=False,
                target_ids=["R1-2301234"],
            )
            result = crawler.crawl(config)

            assert result.processed == 1
            assert result.inserted == 1
            assert result.updated == 0
            stored = database.query_tdocs(QueryConfig(cache_dir=test_db_path.parent))
            assert {record.tdoc_id for record in stored} == {"R1-2301234"}


class TestMeetingCrawler:
    """Tests for MeetingCrawler class."""

    def test_parse_single_date(self, test_db_path: Path) -> None:
        """Verify single date parsing from text."""

        with TDocDatabase(test_db_path) as database:
            crawler = MeetingCrawler(database)
            # Regular hyphen-minus (U+002D)
            assert crawler._parse_single_date("2025-10-20") == date(2025, 10, 20)
            assert crawler._parse_single_date("Meeting on 2025-10-20") == date(2025, 10, 20)
            # Non-breaking hyphen (U+2011) - intentionally testing Unicode characters
            assert crawler._parse_single_date("2027\u201109\u201120") == date(2027, 9, 20)
            # En dash (U+2013) - intentionally testing Unicode characters
            assert crawler._parse_single_date("2026\u201303\u201315") == date(2026, 3, 15)
            # Empty/invalid cases
            assert crawler._parse_single_date("") is None
            assert crawler._parse_single_date("No date here") is None

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

        with TDocDatabase(test_db_path) as database:
            crawler = MeetingCrawler(database)
            meeting = crawler._parse_meeting_row(cells, WorkingGroup.SA, "SA4")

            assert meeting.meeting_id == 12345
            assert meeting.short_name == "SA4#134"
            assert meeting.title == "Meeting Title"
            assert meeting.start_date == date(2025, 10, 20)
            assert meeting.end_date == date(2025, 10, 24)
            assert meeting.location == "Paris, France"
            assert meeting.working_group == WorkingGroup.SA
            assert meeting.subgroup == "SA4"


if __name__ == "__main__":
    pass
# end of file
