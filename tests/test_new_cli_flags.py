"""Tests for the new CLI flags functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from tdoc_crawler.cli.app import app
from tdoc_crawler.models import TDocMetadata


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_database() -> Mock:
    """Create a mock database for testing."""
    return Mock()


@pytest.fixture
def sample_tdoc_metadata() -> TDocMetadata:
    """Create sample TDoc metadata for testing."""
    return TDocMetadata(
        tdoc_id="S4-260001",
        url="https://www.example.com/S4-260001.zip",
        title="Sample TDoc",
        meeting_id=123,
        source="Sample Source",
        contact="Sample Contact",
        agenda_item_nbr=1,
        date="2026-01-01",
        revision_of="",
        technical_committee="SA",
        working_group="S4",
        type="LS",
        status="Published",
        referenced_documents=[],
        filename="S4-260001.zip",
        size=1024,
        validated=True,
        validation_failed=False,
    )


class TestNewCliFlags:
    """Test the new CLI flags functionality."""

    @patch("tdoc_crawler.cli.app.database_path")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    @patch("tdoc_crawler.cli.fetching.maybe_fetch_missing_tdocs")
    def test_open_with_full_metadata_flag(
        self,
        mock_fetch: Mock,
        mock_database_class: Mock,
        mock_database_path: Mock,
        runner: CliRunner,
        sample_tdoc_metadata: TDocMetadata,
    ) -> None:
        """Test open command with --full-metadata flag."""
        # Setup mocks
        mock_db_instance = Mock()
        mock_database_class.return_value.__enter__.return_value = mock_db_instance
        mock_database_path.return_value = Path("/tmp/test.db")

        mock_db_instance.query_tdocs.return_value = [sample_tdoc_metadata]
        mock_fetch.return_value = [sample_tdoc_metadata]

        # Run command with --full-metadata flag
        result = runner.invoke(app, ["open", "S4-260001", "--full-metadata"])

        # Verify success
        assert result.exit_code == 0

        # Verify maybe_fetch_missing_tdocs was called with correct parameters
        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args
        assert call_args[1]["full_metadata"] is True
        assert call_args[1]["use_whatthespec"] is False

    @patch("tdoc_crawler.cli.app.database_path")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    @patch("tdoc_crawler.cli.fetching.maybe_fetch_missing_tdocs")
    def test_open_with_whatthespec_flag(
        self,
        mock_fetch: Mock,
        mock_database_class: Mock,
        mock_database_path: Mock,
        runner: CliRunner,
        sample_tdoc_metadata: TDocMetadata,
    ) -> None:
        """Test open command with --use-whatthespec flag."""
        # Setup mocks
        mock_db_instance = Mock()
        mock_database_class.return_value.__enter__.return_value = mock_db_instance
        mock_database_path.return_value = Path("/tmp/test.db")

        mock_db_instance.query_tdocs.return_value = [sample_tdoc_metadata]
        mock_fetch.return_value = [sample_tdoc_metadata]

        # Run command with --use-whatthespec flag
        result = runner.invoke(app, ["open", "S4-260001", "--use-whatthespec"])

        # Verify success
        assert result.exit_code == 0

        # Verify maybe_fetch_missing_tdocs was called with correct parameters
        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args
        assert call_args[1]["full_metadata"] is False
        assert call_args[1]["use_whatthespec"] is True

    @patch("tdoc_crawler.cli.app.database_path")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    @patch("tdoc_crawler.cli.fetching.maybe_fetch_missing_tdocs")
    def test_open_with_both_flags(
        self,
        mock_fetch: Mock,
        mock_database_class: Mock,
        mock_database_path: Mock,
        runner: CliRunner,
        sample_tdoc_metadata: TDocMetadata,
    ) -> None:
        """Test open command with both --full-metadata and --use-whatthespec flags."""
        # Setup mocks
        mock_db_instance = Mock()
        mock_database_class.return_value.__enter__.return_value = mock_db_instance
        mock_database_path.return_value = Path("/tmp/test.db")

        mock_db_instance.query_tdocs.return_value = [sample_tdoc_metadata]
        mock_fetch.return_value = [sample_tdoc_metadata]

        # Run command with both flags
        result = runner.invoke(app, ["open", "S4-260001", "--full-metadata", "--use-whatthespec"])

        # Verify success
        assert result.exit_code == 0

        # Verify maybe_fetch_missing_tdocs was called with correct parameters
        # use_whatthespec should take precedence
        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args
        assert call_args[1]["full_metadata"] is False  # Overridden by use_whatthespec
        assert call_args[1]["use_whatthespec"] is True

    @patch("tdoc_crawler.cli.app.database_path")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    @patch("tdoc_crawler.cli.fetching.maybe_fetch_missing_tdocs")
    def test_checkout_with_full_metadata_flag(
        self,
        mock_fetch: Mock,
        mock_database_class: Mock,
        mock_database_path: Mock,
        runner: CliRunner,
        sample_tdoc_metadata: TDocMetadata,
    ) -> None:
        """Test checkout command with --full-metadata flag."""
        # Setup mocks
        mock_db_instance = Mock()
        mock_database_class.return_value.__enter__.return_value = mock_db_instance
        mock_database_path.return_value = Path("/tmp/test.db")

        mock_db_instance.query_tdocs.return_value = [sample_tdoc_metadata]
        mock_fetch.return_value = [sample_tdoc_metadata]

        # Run command with --full-metadata flag
        result = runner.invoke(app, ["checkout", "S4-260001", "--full-metadata"])

        # Verify success
        assert result.exit_code == 0

        # Verify maybe_fetch_missing_tdocs was called with correct parameters
        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args
        assert call_args[1]["full_metadata"] is True
        assert call_args[1]["use_whatthespec"] is False

    @patch("tdoc_crawler.cli.app.database_path")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    @patch("tdoc_crawler.cli.fetching.maybe_fetch_missing_tdocs")
    def test_checkout_with_whatthespec_flag(
        self,
        mock_fetch: Mock,
        mock_database_class: Mock,
        mock_database_path: Mock,
        runner: CliRunner,
        sample_tdoc_metadata: TDocMetadata,
    ) -> None:
        """Test checkout command with --use-whatthespec flag."""
        # Setup mocks
        mock_db_instance = Mock()
        mock_database_class.return_value.__enter__.return_value = mock_db_instance
        mock_database_path.return_value = Path("/tmp/test.db")

        mock_db_instance.query_tdocs.return_value = [sample_tdoc_metadata]
        mock_fetch.return_value = [sample_tdoc_metadata]

        # Run command with --use-whatthespec flag
        result = runner.invoke(app, ["checkout", "S4-260001", "--use-whatthespec"])

        # Verify success
        assert result.exit_code == 0

        # Verify maybe_fetch_missing_tdocs was called with correct parameters
        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args
        assert call_args[1]["full_metadata"] is False
        assert call_args[1]["use_whatthespec"] is True

    @patch("tdoc_crawler.cli.app.database_path")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    @patch("tdoc_crawler.cli.fetching.maybe_fetch_missing_tdocs")
    def test_default_behavior_unchanged(
        self,
        mock_fetch: Mock,
        mock_database_class: Mock,
        mock_database_path: Mock,
        runner: CliRunner,
        sample_tdoc_metadata: TDocMetadata,
    ) -> None:
        """Test that default behavior is unchanged when no flags are provided."""
        # Setup mocks
        mock_db_instance = Mock()
        mock_database_class.return_value.__enter__.return_value = mock_db_instance
        mock_database_path.return_value = Path("/tmp/test.db")

        mock_db_instance.query_tdocs.return_value = [sample_tdoc_metadata]
        mock_fetch.return_value = [sample_tdoc_metadata]

        # Run command without any new flags
        result = runner.invoke(app, ["open", "S4-260001"])

        # Verify success
        assert result.exit_code == 0

        # Verify maybe_fetch_missing_tdocs was called with default parameters
        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args
        assert call_args[1]["full_metadata"] is False
        assert call_args[1]["use_whatthespec"] is False
