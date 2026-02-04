"""Tests for CLI commands."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from conftest import insert_sample_meetings
from typer.testing import CliRunner

from tdoc_crawler.cli import app
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import TDocMetadata, WorkingGroup

runner = CliRunner()


class TestCrawlCommand:
    """Tests for crawl command."""

    @patch("tdoc_crawler.cli.app.TDocCrawler")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_crawl_basic(
        self,
        mock_db_class: MagicMock,
        mock_crawler_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test basic crawl command execution."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.log_crawl_start.return_value = "1"
        mock_db.query_meetings.return_value = []  # Return empty list for progress bar

        mock_crawler = MagicMock()
        mock_crawler_class.return_value = mock_crawler
        mock_crawler.crawl.return_value = MagicMock(
            processed=10,
            inserted=10,
            updated=0,
            errors=[],
        )

        result = runner.invoke(
            app,
            ["crawl-tdocs", "--cache-dir", str(test_cache_dir), "--limit-tdocs", "10"],
        )

        assert result.exit_code == 0
        # Check for key output parts (ANSI codes may be present)
        assert "Processed" in result.stdout
        assert "10" in result.stdout
        assert "TDocs" in result.stdout
        mock_crawler.crawl.assert_called_once()

    @patch("tdoc_crawler.cli.app.TDocCrawler")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_crawl_with_working_group_filter(
        self,
        mock_db_class: MagicMock,
        mock_crawler_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test crawl with specific working group."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.log_crawl_start.return_value = "1"

        mock_crawler = MagicMock()
        mock_crawler_class.return_value = mock_crawler
        mock_crawler.crawl.return_value = MagicMock(
            processed=5,
            inserted=5,
            updated=0,
            errors=[],
        )

        result = runner.invoke(
            app,
            ["crawl-tdocs", "--cache-dir", str(test_cache_dir), "--working-group", "RAN"],
        )

        assert result.exit_code == 0
        mock_crawler.crawl.assert_called_once()


class TestCrawlMeetingsCommand:
    """Tests for crawl-meetings command."""

    @patch("tdoc_crawler.cli.app.MeetingCrawler")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_crawl_meetings_basic(
        self,
        mock_db_class: MagicMock,
        mock_crawler_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test basic crawl-meetings command execution."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.log_crawl_start.return_value = "1"

        mock_crawler = MagicMock()
        mock_crawler_class.return_value = mock_crawler
        mock_crawler.crawl.return_value = MagicMock(
            processed=20,
            inserted=20,
            updated=0,
            errors=[],
        )

        result = runner.invoke(
            app,
            [
                "crawl-meetings",
                "--cache-dir",
                str(test_cache_dir),
                "--no-prompt-credentials",
            ],
        )

        assert result.exit_code == 0
        # Check for key output parts (ANSI codes may be present)
        assert "Processed" in result.stdout
        assert "20" in result.stdout
        assert "meetings" in result.stdout


class TestQueryCommand:
    """Tests for query command."""

    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_query_no_results(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test query command with no results."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_tdocs.return_value = []

        result = runner.invoke(
            app,
            ["query-tdocs", "--cache-dir", str(test_cache_dir)],
        )

        assert result.exit_code == 0
        assert "No TDocs found" in result.stdout

    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_query_with_results_table(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
        sample_tdocs: list[TDocMetadata],
    ) -> None:
        """Test query with results in table format."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_tdocs.return_value = sample_tdocs

        result = runner.invoke(
            app,
            ["query-tdocs", "--cache-dir", str(test_cache_dir), "--output", "table"],
        )

        assert result.exit_code == 0
        assert "R1-2301234" in result.stdout

    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_query_json_format(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
        sample_tdocs: list[TDocMetadata],
    ) -> None:
        """Test query with JSON output format."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_tdocs.return_value = sample_tdocs[:1]

        result = runner.invoke(
            app,
            ["query-tdocs", "--cache-dir", str(test_cache_dir), "--output", "json"],
        )

        assert result.exit_code == 0
        assert "R1-2301234" in result.stdout
        assert "tdoc_id" in result.stdout

    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_query_specific_tdoc(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
        sample_tdocs: list[TDocMetadata],
    ) -> None:
        """Test query for specific TDoc IDs."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_tdocs.return_value = sample_tdocs[:1]

        result = runner.invoke(
            app,
            ["query-tdocs", "R1-2301234", "--cache-dir", str(test_cache_dir)],
        )

        assert result.exit_code == 0


class TestQueryMeetingsCommand:
    """Tests for query-meetings command."""

    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_query_meetings_no_results(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test query-meetings with no results."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_meetings.return_value = []

        result = runner.invoke(
            app,
            ["query-meetings", "--cache-dir", str(test_cache_dir)],
        )

        assert result.exit_code == 0
        assert "No meetings found" in result.stdout

    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_query_meetings_with_subgroup_filter(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test query-meetings with subgroup filter."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_meetings.return_value = []

        result = runner.invoke(
            app,
            ["query-meetings", "--cache-dir", str(test_cache_dir), "-s", "SA4"],
        )

        assert result.exit_code == 0
        # Verify that query_meetings was called with normalized subgroups (SA4 -> S4)
        call_args = mock_db.query_meetings.call_args[0][0]
        assert call_args.subgroups == ["S4"]

    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_query_meetings_with_subgroup_alias(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test query-meetings with subgroup alias (S4 -> SA4)."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_meetings.return_value = []

        result = runner.invoke(
            app,
            ["query-meetings", "--cache-dir", str(test_cache_dir), "-s", "S4"],
        )

        assert result.exit_code == 0
        # Verify that S4 alias was normalized
        call_args = mock_db.query_meetings.call_args[0][0]
        assert "S4" in call_args.subgroups

    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_query_meetings_with_plenary_alias(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test query-meetings with plenary subgroup alias (RP -> RAN Plenary)."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_meetings.return_value = []

        result = runner.invoke(
            app,
            ["query-meetings", "--cache-dir", str(test_cache_dir), "-s", "RP"],
        )

        assert result.exit_code == 0
        # Verify that RP alias was normalized
        call_args = mock_db.query_meetings.call_args[0][0]
        assert "RP" in call_args.subgroups

    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_query_meetings_with_working_group_alias(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test query-meetings with working group alias (SP -> SA)."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_meetings.return_value = []

        result = runner.invoke(
            app,
            ["query-meetings", "--cache-dir", str(test_cache_dir), "-w", "SP"],
        )

        assert result.exit_code == 0
        # Verify that SP alias was expanded to SA
        call_args = mock_db.query_meetings.call_args[0][0]
        assert WorkingGroup.SA in call_args.working_groups

    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_query_meetings_combined_filters(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test query-meetings with combined working group and subgroup filters."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_meetings.return_value = []

        result = runner.invoke(
            app,
            ["query-meetings", "--cache-dir", str(test_cache_dir), "-w", "SA", "-s", "S4"],
        )

        assert result.exit_code == 0
        # Verify both filters were applied
        call_args = mock_db.query_meetings.call_args[0][0]
        assert WorkingGroup.SA in call_args.working_groups
        assert "S4" in call_args.subgroups


class TestStatsCommand:
    """Tests for stats command."""

    def test_stats_basic(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict],
    ) -> None:
        """Test stats command execution."""
        with TDocDatabase(test_db_path) as db:
            insert_sample_meetings(db, sample_meetings)
            for tdoc in sample_tdocs:
                db.upsert_tdoc(tdoc)

        result = runner.invoke(
            app,
            ["stats", "--cache-dir", str(test_db_path.parent)],
        )

        assert result.exit_code == 0
        assert "Total TDocs" in result.stdout
        assert "3" in result.stdout

    def test_stats_missing_database(
        self,
        test_cache_dir: Path,
    ) -> None:
        """Test stats command with missing database."""
        result = runner.invoke(
            app,
            ["stats", "--cache-dir", str(test_cache_dir)],
        )

        assert result.exit_code == 1
        assert "Database not found" in result.stdout


class TestOpenCommand:
    """Tests for open command."""

    @patch("tdoc_crawler.cli.app.launch_file")
    @patch("tdoc_crawler.cli.app.prepare_tdoc_file")
    @patch("tdoc_crawler.cli.app.maybe_fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_open_existing_tdoc(
        self,
        mock_db_class: MagicMock,
        mock_fetch: MagicMock,
        mock_prepare: MagicMock,
        mock_launch: MagicMock,
        test_cache_dir: Path,
        sample_tdocs: list[TDocMetadata],
    ) -> None:
        """Test open command for existing TDoc."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_tdocs.return_value = sample_tdocs[:1]
        mock_fetch.return_value = sample_tdocs[:1]

        mock_file = test_cache_dir / "test.pdf"
        mock_prepare.return_value = mock_file

        result = runner.invoke(
            app,
            ["open", "R1-2301234", "--cache-dir", str(test_cache_dir)],
        )

        assert result.exit_code == 0
        mock_prepare.assert_called_once()
        mock_launch.assert_called_once()

    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_open_missing_tdoc(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test open command for missing TDoc."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_tdocs.return_value = []

        result = runner.invoke(
            app,
            ["open", "INVALID-ID", "--cache-dir", str(test_cache_dir)],
        )

        assert result.exit_code == 1
        assert "not found" in result.stdout

    @patch("tdoc_crawler.cli.app.launch_file")
    @patch("tdoc_crawler.cli.app.prepare_tdoc_file")
    @patch("tdoc_crawler.cli.fetching._fetch_via_whatthespec")
    @patch("tdoc_crawler.cli.fetching.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_open_with_whatthespec_fallback(
        self,
        mock_db_class: MagicMock,
        mock_fetch_portal: MagicMock,
        mock_whatthespec_fetch: MagicMock,
        mock_prepare: MagicMock,
        mock_launch: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test open command uses whatthespec fallback when TDoc missing and no credentials.

        This integration test verifies:
        1. TDoc not found in database
        2. maybe_fetch_missing_tdocs is called
        3. Portal fetch fails (no credentials)
        4. whatthespec fallback is triggered
        5. whatthespec returns valid metadata
        6. TDoc is inserted and file is opened
        """
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        # Database returns no results initially
        mock_db.query_tdocs.return_value = []
        # After fetch, database returns the fetched TDoc
        mock_db.upsert_tdoc.return_value = (True, False)

        # Mock portal fetch to return credentials error
        mock_fetch_portal.return_value = MagicMock(
            processed=1,
            inserted=0,
            updated=0,
            errors=["Portal credentials required"],
        )

        metadata = TDocMetadata(
            tdoc_id="S4-260001",
            meeting_id=0,
            meeting_name="S4-135",
            title="SA4#135 meeting agenda",
            url="https://www.3gpp.org/tsg_sa/WG4/s4-260001.zip",
            source="SA WG4 Chair",
            contact="Test Contact",
            tdoc_type="agenda",
            for_purpose="Approval",
            agenda_item_nbr=Decimal("2"),
            status="available",
            validated=False,
        )

        def insert_via_fetch(database, cache_dir, missing_ids) -> None:
            """Mock whatthespec fetch that inserts TDoc."""
            database.upsert_tdoc(metadata)

        mock_whatthespec_fetch.side_effect = insert_via_fetch

        mock_file = test_cache_dir / "test.pdf"
        mock_prepare.return_value = mock_file

        # Mock the re-query after fetch to return the TDoc
        # query_tdocs is called 3 times: initial, after portal fetch, after whatthespec
        mock_db.query_tdocs.side_effect = [
            [],  # First call: initial query
            [],  # Second call: after portal fetch fails
            [metadata],  # Third call: after whatthespec succeeds
        ]

        result = runner.invoke(
            app,
            ["open", "S4-260001", "--cache-dir", str(test_cache_dir)],
        )

        assert result.exit_code == 0
        mock_whatthespec_fetch.assert_called_once()
        mock_prepare.assert_called_once()
        mock_launch.assert_called_once()

    @patch("tdoc_crawler.cli.app.launch_file")
    @patch("tdoc_crawler.cli.app.prepare_tdoc_file")
    @patch("tdoc_crawler.cli.fetching._fetch_via_whatthespec")
    @patch("tdoc_crawler.cli.fetching.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_open_with_whatthespec_no_credentials_required(
        self,
        mock_db_class: MagicMock,
        mock_fetch_portal: MagicMock,
        mock_whatthespec_fetch: MagicMock,
        mock_prepare: MagicMock,
        mock_launch: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test open command works without EOL credentials when whatthespec available.

        This integration test verifies:
        1. No EOL credentials set (None)
        2. TDoc not in database
        3. whatthespec resolver provides metadata
        4. TDoc is opened without requiring portal credentials
        """
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_tdocs.return_value = []
        mock_db.upsert_tdoc.return_value = (True, False)

        # Mock portal fetch to return credentials error
        mock_fetch_portal.return_value = MagicMock(
            processed=1,
            inserted=0,
            updated=0,
            errors=["Portal credentials required"],
        )

        metadata = TDocMetadata(
            tdoc_id="R1-260001",
            meeting_id=0,
            meeting_name="RAN1#100",
            title="RAN1 discussion document",
            url="https://www.3gpp.org/tsg_ran/RAN1/r1-260001.zip",
            source="RAN1 Chair",
            contact="Test Contact",
            tdoc_type="discussion",
            for_purpose="Discussion",
            agenda_item_nbr=Decimal("3.1"),
            status="available",
            validated=False,
        )

        def insert_via_fetch(database, cache_dir, missing_ids) -> None:
            database.upsert_tdoc(metadata)

        mock_whatthespec_fetch.side_effect = insert_via_fetch

        mock_file = test_cache_dir / "test.pdf"
        mock_prepare.return_value = mock_file

        # query_tdocs is called 3 times: initial, after portal fetch, after whatthespec
        mock_db.query_tdocs.side_effect = [
            [],  # First call: initial query
            [],  # Second call: after portal fetch fails
            [metadata],  # Third call: after whatthespec succeeds
        ]

        result = runner.invoke(
            app,
            ["open", "R1-260001", "--cache-dir", str(test_cache_dir)],
        )

        # Should succeed (exit code 0) and use whatthespec fallback
        assert result.exit_code == 0
        # Verify whatthespec was called as fallback
        mock_whatthespec_fetch.assert_called_once()
        # Verify output indicates whatthespec was used
        assert "whatthespec fallback" in result.stdout.lower() or "trying whatthespec" in result.stdout.lower()


class TestCheckoutCommand:
    """Tests for checkout command with whatthespec fallback."""

    @patch("tdoc_crawler.cli.app.checkout_tdoc")
    @patch("tdoc_crawler.cli.fetching._fetch_via_whatthespec")
    @patch("tdoc_crawler.cli.fetching.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_checkout_with_whatthespec_fallback(
        self,
        mock_db_class: MagicMock,
        mock_fetch_portal: MagicMock,
        mock_whatthespec_fetch: MagicMock,
        mock_checkout: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test checkout command uses whatthespec fallback for missing TDocs.

        This integration test verifies:
        1. Multiple TDocs requested
        2. TDocs not found in database
        3. Portal fetch fails (no credentials)
        4. whatthespec fallback resolves TDocs
        5. checkout_tdoc called for resolved TDocs
        """
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_tdocs.return_value = []
        mock_db.upsert_tdoc.return_value = (True, False)

        # Mock portal fetch to return credentials error
        mock_fetch_portal.return_value = MagicMock(
            processed=2,
            inserted=0,
            updated=0,
            errors=["Portal credentials required"],
        )

        # Setup metadata for both TDocs
        tdoc1 = TDocMetadata(
            tdoc_id="S4-260001",
            meeting_id=0,
            meeting_name="S4-135",
            title="SA4#135 agenda",
            url="https://www.3gpp.org/tsg_sa/WG4/s4-260001.zip",
            source="SA WG4 Chair",
            contact="Test Contact",
            tdoc_type="agenda",
            for_purpose="Approval",
            agenda_item_nbr=Decimal("2"),
            status="available",
            validated=False,
        )
        tdoc2 = TDocMetadata(
            tdoc_id="S4-260002",
            meeting_id=0,
            meeting_name="S4-135",
            title="SA4#135 document",
            url="https://www.3gpp.org/tsg_sa/WG4/s4-260002.zip",
            source="SA WG4 Chair",
            contact="Test Contact",
            tdoc_type="discussion",
            for_purpose="Discussion",
            agenda_item_nbr=Decimal("3"),
            status="available",
            validated=False,
        )

        def insert_via_fetch(database, cache_dir, missing_ids) -> None:
            for tdoc_id in missing_ids:
                if tdoc_id == "S4-260001":
                    database.upsert_tdoc(tdoc1)
                elif tdoc_id == "S4-260002":
                    database.upsert_tdoc(tdoc2)

        mock_whatthespec_fetch.side_effect = insert_via_fetch
        mock_db.query_tdocs.side_effect = [
            [],  # First call: initial query
            [],  # Second call: after portal fetch fails
            [tdoc1, tdoc2],  # Third call: after whatthespec succeeds
        ]

        result = runner.invoke(
            app,
            ["checkout", "S4-260001", "S4-260002", "--cache-dir", str(test_cache_dir)],
        )

        assert result.exit_code == 0
        # whatthespec should have been called
        mock_whatthespec_fetch.assert_called_once()
        # checkout_tdoc should have been called for both TDocs
        assert mock_checkout.call_count == 2

    @patch("tdoc_crawler.cli.app.checkout_tdoc")
    @patch("tdoc_crawler.cli.fetching._fetch_via_whatthespec")
    @patch("tdoc_crawler.cli.fetching.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_checkout_with_whatthespec_graceful_failure(
        self,
        mock_db_class: MagicMock,
        mock_fetch_portal: MagicMock,
        mock_whatthespec_fetch: MagicMock,
        mock_checkout: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test checkout handles whatthespec failure gracefully.

        This integration test verifies:
        1. whatthespec fetch doesn't insert any TDocs
        2. CLI does NOT crash
        3. CLI reports missing TDocs
        4. Exit code indicates partial failure
        """
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_tdocs.return_value = []

        # Mock portal fetch to return credentials error
        mock_fetch_portal.return_value = MagicMock(
            processed=1,
            inserted=0,
            updated=0,
            errors=["Portal credentials required"],
        )

        # Mock whatthespec to not insert anything (failure case)
        mock_whatthespec_fetch.side_effect = lambda *args, **kwargs: None

        result = runner.invoke(
            app,
            ["checkout", "S4-999999", "--cache-dir", str(test_cache_dir)],
        )

        # Should exit with error code due to missing TDoc
        assert result.exit_code == 1
        # Should report missing TDoc in output
        assert "missing" in result.stdout.lower() or "not found" in result.stdout.lower()
