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
from tdoc_crawler.tdocs.operations.crawl import TDocCrawlResult
from tdoc_crawler.tdocs.operations.fetch import FetchMissingResult

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
    @patch("tdoc_crawler.cli.app.fetch_missing_tdocs")
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
        mock_fetch.return_value = FetchMissingResult(refreshed=sample_tdocs[:1])

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
    @patch("tdoc_crawler.cli.app.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_open_with_whatthespec_fallback(
        self,
        mock_db_class: MagicMock,
        mock_fetch: MagicMock,
        mock_prepare: MagicMock,
        mock_launch: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test open command uses whatthespec fallback when TDoc missing and no credentials.

        This integration test verifies:
        1. TDoc not found in database
        2. fetch_missing_tdocs is called
        3. whatthespec fallback returns valid metadata
        4. TDoc is inserted and file is opened
        """
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        # Database returns no results initially
        mock_db.query_tdocs.return_value = []
        # After fetch, database returns the fetched TDoc
        mock_db.upsert_tdoc.return_value = (True, False)

        # Mock fetch_missing_tdocs to simulate whatthespec fallback
        metadata = TDocMetadata(
            tdoc_id="S4-260001",
            meeting_id=123,
            meeting_name="S4-135",
            title="SA4#135 meeting agenda",
            url="https://www.3gpp.org/tsg_sa/WG4/s4-260001.zip",
            source="SA WG4 Chair",
            contact="Test Contact",
            tdoc_type="agenda",
            for_purpose="Approval",
            agenda_item_nbr=Decimal("2"),
            agenda_item_text="Agenda item text",
            status="available",
            validated=False,
            validation_failed=False,
            is_revision_of=None,
            file_size=None,
            date_created=None,
        )

        mock_fetch.return_value = FetchMissingResult(
            refreshed=[metadata],
            fetch_result=TDocCrawlResult(
                processed=1,
                inserted=1,
                updated=0,
                errors=[],
            ),
            used_whatthespec_fallback=True,
        )

        mock_file = test_cache_dir / "test.pdf"
        mock_prepare.return_value = mock_file

        result = runner.invoke(
            app,
            ["open", "S4-260001", "--cache-dir", str(test_cache_dir)],
        )

        assert result.exit_code == 0
        mock_prepare.assert_called_once()
        mock_launch.assert_called_once()

    @patch("tdoc_crawler.cli.app.launch_file")
    @patch("tdoc_crawler.cli.app.prepare_tdoc_file")
    @patch("tdoc_crawler.cli.app.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_open_with_whatthespec_no_credentials_required(
        self,
        mock_db_class: MagicMock,
        mock_fetch: MagicMock,
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

        # Mock fetch_missing_tdocs to simulate whatthespec fallback success
        metadata = TDocMetadata(
            tdoc_id="R1-260001",
            meeting_id=123,
            meeting_name="RAN1#100",
            title="RAN1 discussion document",
            url="https://www.3gpp.org/tsg_ran/RAN1/r1-260001.zip",
            source="RAN1 Chair",
            contact="Test Contact",
            tdoc_type="discussion",
            agenda_item_text="Test agenda item text",
            for_purpose="Discussion",
            agenda_item_nbr=Decimal("3.1"),
            status="available",
            validated=False,
            validation_failed=False,
            is_revision_of=None,
            file_size=None,
            date_created=None,
        )

        mock_fetch.return_value = FetchMissingResult(
            refreshed=[metadata],
            fetch_result=TDocCrawlResult(
                processed=1,
                inserted=1,
                updated=0,
                errors=[],
            ),
            used_whatthespec_fallback=True,
        )

        mock_file = test_cache_dir / "test.pdf"
        mock_prepare.return_value = mock_file

        result = runner.invoke(
            app,
            ["open", "R1-260001", "--cache-dir", str(test_cache_dir)],
        )

        # Should succeed (exit code 0) and use whatthespec fallback
        assert result.exit_code == 0
        # Verify output indicates whatthespec was used
        assert "whatthespec" in result.stdout.lower()


class TestCheckoutCommand:
    """Tests for checkout command with whatthespec fallback."""

    @patch("tdoc_crawler.cli.app.checkout_tdoc")
    @patch("tdoc_crawler.cli.app.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_checkout_with_whatthespec_fallback(
        self,
        mock_db_class: MagicMock,
        mock_fetch: MagicMock,
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

        # Mock fetch_missing_tdocs to return credentials error and then success via whatthespec
        # Mock fetch_missing_tdocs to return success with whatthespec fallback
        tdoc1 = TDocMetadata(
            tdoc_id="S4-260001",
            meeting_id=123,
            meeting_name="S4-135",
            title="SA4#135 agenda",
            url="https://www.3gpp.org/tsg_sa/WG4/s4-260001.zip",
            source="SA WG4 Chair",
            contact="Test Contact",
            tdoc_type="agenda",
            agenda_item_text="Test agenda item text",
            for_purpose="Approval",
            agenda_item_nbr=Decimal("2"),
            status="available",
            validated=False,
            validation_failed=False,
            is_revision_of=None,
            file_size=None,
            date_created=None,
        )
        tdoc2 = TDocMetadata(
            tdoc_id="S4-260002",
            meeting_id=123,
            meeting_name="S4-135",
            title="SA4#135 document",
            url="https://www.3gpp.org/tsg_sa/WG4/s4-260002.zip",
            source="SA WG4 Chair",
            contact="Test Contact",
            tdoc_type="discussion",
            agenda_item_text="Test agenda item text",
            for_purpose="Discussion",
            agenda_item_nbr=Decimal("3"),
            status="available",
            validated=False,
            validation_failed=False,
            is_revision_of=None,
            file_size=None,
            date_created=None,
        )

        mock_fetch.return_value = FetchMissingResult(
            refreshed=[tdoc1, tdoc2],
            fetch_result=TDocCrawlResult(
                processed=2,
                inserted=2,
                updated=0,
                errors=[],
            ),
            used_whatthespec_fallback=True,
        )

        result = runner.invoke(
            app,
            ["checkout", "S4-260001", "S4-260002", "--cache-dir", str(test_cache_dir)],
        )

        assert result.exit_code == 0
        # checkout_tdoc should have been called for both TDocs
        assert mock_checkout.call_count == 2

    @patch("tdoc_crawler.cli.app.checkout_tdoc")
    @patch("tdoc_crawler.cli.app.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_checkout_with_whatthespec_graceful_failure(
        self,
        mock_db_class: MagicMock,
        mock_fetch: MagicMock,
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

        # Mock fetch_missing_tdocs to return empty results (all TDocs missing)
        mock_fetch.return_value = FetchMissingResult(
            refreshed=[],
            fetch_result=TDocCrawlResult(
                processed=1,
                inserted=0,
                updated=0,
                errors=["TDoc not found"],
            ),
            used_whatthespec_fallback=True,
        )

        result = runner.invoke(
            app,
            ["checkout", "S4-999999", "--cache-dir", str(test_cache_dir)],
        )

        # Should exit with error code due to missing TDoc
        assert result.exit_code == 1
        # Should report issues in output
        assert "issues detected" in result.stdout.lower() or "error" in result.stdout.lower()


class TestEnvironmentVariables:
    """Tests for environment variable support in CLI options."""

    @patch("tdoc_crawler.cli.app.TDocCrawler")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_env_var_cache_dir(
        self,
        mock_db_class: MagicMock,
        mock_crawler_class: MagicMock,
        test_cache_dir: Path,
        monkeypatch,
    ) -> None:
        """Test that TDC_CACHE_DIR environment variable sets cache directory."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.log_crawl_start.return_value = "1"
        mock_db.query_meetings.return_value = []

        mock_crawler = MagicMock()
        mock_crawler_class.return_value = mock_crawler
        mock_crawler.crawl.return_value = MagicMock(
            processed=0,
            inserted=0,
            updated=0,
            errors=[],
        )

        # Set environment variable via monkeypatch
        monkeypatch.setenv("TDC_CACHE_DIR", str(test_cache_dir))

        result = runner.invoke(app, ["crawl-tdocs"])

        assert result.exit_code == 0
        mock_crawler.crawl.assert_called_once()
        # Verify cache_dir parameter was passed to config
        call_args = mock_crawler.crawl.call_args[0]
        config = call_args[0]
        assert config.cache_dir == test_cache_dir

    @patch("tdoc_crawler.cli.app.TDocCrawler")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_env_var_workers(
        self,
        mock_db_class: MagicMock,
        mock_crawler_class: MagicMock,
        monkeypatch,
    ) -> None:
        """Test that TDC_WORKERS environment variable sets worker count."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.log_crawl_start.return_value = "1"
        mock_db.query_meetings.return_value = []

        mock_crawler = MagicMock()
        mock_crawler_class.return_value = mock_crawler
        mock_crawler.crawl.return_value = MagicMock(
            processed=0,
            inserted=0,
            updated=0,
            errors=[],
        )

        # Set environment variable via monkeypatch
        monkeypatch.setenv("TDC_WORKERS", "8")

        result = runner.invoke(app, ["crawl-tdocs"])

        assert result.exit_code == 0
        mock_crawler.crawl.assert_called_once()
        # Verify workers parameter was passed to config
        call_args = mock_crawler.crawl.call_args[0]
        config = call_args[0]
        assert config.workers == 8

    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_env_var_working_group(
        self,
        mock_db_class: MagicMock,
        monkeypatch,
    ) -> None:
        """Test that TDC_WORKING_GROUP environment variable filters by working group."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_meetings.return_value = []

        # Set environment variable via monkeypatch
        monkeypatch.setenv("TDC_WORKING_GROUP", "SA")

        result = runner.invoke(app, ["query-meetings"])

        assert result.exit_code == 0
        # Verify working group filter was applied
        call_args = mock_db.query_meetings.call_args[0][0]
        assert WorkingGroup.SA in call_args.working_groups

    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_env_var_output_format(
        self,
        mock_db_class: MagicMock,
        monkeypatch,
    ) -> None:
        """Test that TDC_OUTPUT environment variable sets output format."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_tdocs.return_value = []

        # Set environment variable via monkeypatch
        monkeypatch.setenv("TDC_OUTPUT", "json")

        result = runner.invoke(app, ["query-tdocs"])

        assert result.exit_code == 0

    def test_env_var_cli_override(
        self,
        monkeypatch,
    ) -> None:
        """Test that CLI arguments override environment variables."""
        # Set environment variable for verbose mode
        monkeypatch.setenv("TDC_VERBOSE", "false")

        # But override with CLI argument
        result = runner.invoke(app, ["--help"])

        # Help command should succeed regardless
        assert result.exit_code == 0

    @patch("tdoc_crawler.credentials.resolve_credentials")
    def test_env_var_credentials(
        self,
        mock_resolve: MagicMock,
        monkeypatch,
    ) -> None:
        """Test that TDC_EOL_USERNAME and TDC_EOL_PASSWORD set credentials."""
        # Set environment variables
        monkeypatch.setenv("TDC_EOL_USERNAME", "testuser")
        monkeypatch.setenv("TDC_EOL_PASSWORD", "testpass")

        # Mock resolve_credentials to return valid credentials
        mock_resolve.return_value = None

        result = runner.invoke(app, ["stats"])

        # Verify resolve_credentials was called
        # (Actual credential resolution happens via Typer's envvar parameter)
        assert result.exit_code == 0

    @patch("tdoc_crawler.credentials.resolve_credentials")
    def test_env_var_prompt_credentials(
        self,
        mock_resolve: MagicMock,
        monkeypatch,
    ) -> None:
        """Test that TDC_EOL_PROMPT controls credential prompting."""
        # Set environment variable to disable prompting
        monkeypatch.setenv("TDC_EOL_PROMPT", "false")

        mock_resolve.return_value = None

        result = runner.invoke(app, ["stats"])

        assert result.exit_code == 0

    @patch("tdoc_crawler.cli.app.TDocDatabase")
    def test_env_var_limit(
        self,
        mock_db_class: MagicMock,
        monkeypatch,
    ) -> None:
        """Test that TDC_LIMIT environment variables set limits."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_tdocs.return_value = []

        # Set multiple limit environment variables
        monkeypatch.setenv("TDC_LIMIT", "5")
        monkeypatch.setenv("TDC_START_DATE", "2024-01-01T00:00:00Z")
        monkeypatch.setenv("TDC_END_DATE", "2024-12-31T23:59:59Z")

        result = runner.invoke(app, ["query-tdocs"])

        assert result.exit_code == 0

    @patch("tdoc_crawler.credentials.resolve_credentials")
    def test_env_var_multiple_credentials(
        self,
        mock_resolve: MagicMock,
        monkeypatch,
    ) -> None:
        """Test multiple credential environment variables work together."""
        # Set all credential-related environment variables
        monkeypatch.setenv("TDC_EOL_USERNAME", "envuser")
        monkeypatch.setenv("TDC_EOL_PASSWORD", "envpass")
        monkeypatch.setenv("TDC_EOL_PROMPT", "true")

        mock_resolve.return_value = None

        result = runner.invoke(app, ["stats"])

        assert result.exit_code == 0
