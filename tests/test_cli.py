"""Tests for CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from tdoc_crawler.cli import app
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import TDocMetadata

runner = CliRunner()


class TestCrawlCommand:
    """Tests for crawl command."""

    @patch("tdoc_crawler.cli.TDocCrawler")
    @patch("tdoc_crawler.cli.TDocDatabase")
    def test_crawl_basic(
        self,
        mock_db_class: MagicMock,
        mock_crawler_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test basic crawl command execution."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.log_crawl_start.return_value = 1

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
            ["crawl", "--cache-dir", str(test_cache_dir), "--limit-tdocs", "10"],
        )

        assert result.exit_code == 0
        assert "Processed 10 TDocs" in result.stdout
        mock_crawler.crawl.assert_called_once()

    @patch("tdoc_crawler.cli.TDocCrawler")
    @patch("tdoc_crawler.cli.TDocDatabase")
    def test_crawl_with_working_group_filter(
        self,
        mock_db_class: MagicMock,
        mock_crawler_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test crawl with specific working group."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.log_crawl_start.return_value = 1

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
            ["crawl", "--cache-dir", str(test_cache_dir), "--working-group", "RAN"],
        )

        assert result.exit_code == 0
        mock_crawler.crawl.assert_called_once()


class TestCrawlMeetingsCommand:
    """Tests for crawl-meetings command."""

    @patch("tdoc_crawler.cli.MeetingCrawler")
    @patch("tdoc_crawler.cli.TDocDatabase")
    def test_crawl_meetings_basic(
        self,
        mock_db_class: MagicMock,
        mock_crawler_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test basic crawl-meetings command execution."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.log_crawl_start.return_value = 1

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
        assert "Processed 20 meetings" in result.stdout


class TestQueryCommand:
    """Tests for query command."""

    @patch("tdoc_crawler.cli.TDocDatabase")
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
            ["query", "--cache-dir", str(test_cache_dir)],
        )

        assert result.exit_code == 0
        assert "No TDocs found" in result.stdout

    @patch("tdoc_crawler.cli.TDocDatabase")
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
            ["query", "--cache-dir", str(test_cache_dir), "--output", "table"],
        )

        assert result.exit_code == 0
        assert "R1-2301234" in result.stdout

    @patch("tdoc_crawler.cli.TDocDatabase")
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
            ["query", "--cache-dir", str(test_cache_dir), "--output", "json"],
        )

        assert result.exit_code == 0
        assert "R1-2301234" in result.stdout
        assert "tdoc_id" in result.stdout

    @patch("tdoc_crawler.cli.TDocDatabase")
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
            ["query", "R1-2301234", "--cache-dir", str(test_cache_dir)],
        )

        assert result.exit_code == 0


class TestQueryMeetingsCommand:
    """Tests for query-meetings command."""

    @patch("tdoc_crawler.cli.TDocDatabase")
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


class TestStatsCommand:
    """Tests for stats command."""

    def test_stats_basic(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
    ) -> None:
        """Test stats command execution."""
        with TDocDatabase(test_db_path) as db:
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

    @patch("tdoc_crawler.cli._launch_file")
    @patch("tdoc_crawler.cli._prepare_tdoc_file")
    @patch("tdoc_crawler.cli.TDocDatabase")
    def test_open_existing_tdoc(
        self,
        mock_db_class: MagicMock,
        mock_prepare: MagicMock,
        mock_launch: MagicMock,
        test_cache_dir: Path,
        sample_tdocs: list[TDocMetadata],
    ) -> None:
        """Test open command for existing TDoc."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_tdocs.return_value = sample_tdocs[:1]

        mock_file = test_cache_dir / "test.pdf"
        mock_prepare.return_value = mock_file

        result = runner.invoke(
            app,
            ["open", "R1-2301234", "--cache-dir", str(test_cache_dir)],
        )

        assert result.exit_code == 0
        mock_prepare.assert_called_once()
        mock_launch.assert_called_once()

    @patch("tdoc_crawler.cli.TDocDatabase")
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
