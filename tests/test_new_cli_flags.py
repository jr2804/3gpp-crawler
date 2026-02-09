"""Tests for the new CLI flags --full-metadata and --use-whatthespec."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from tdoc_crawler.cli.app import app
from tdoc_crawler.fetching import FetchMissingResult
from tdoc_crawler.models.tdocs import TDocMetadata


@pytest.fixture
def runner() -> CliRunner:
    """Provides a CliRunner for testing."""
    return CliRunner()


@pytest.fixture
def sample_tdoc_metadata() -> TDocMetadata:
    """Provides a sample TDocMetadata object."""
    return TDocMetadata(
        tdoc_id="S4-260001",
        meeting_id=123,
        title="Sample TDoc",
        source="Qualcomm",
        contact="John Doe",
        agenda_item_nbr=Decimal("1.1"),
        url="https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_123/Docs/S4-260001.zip",
        tdoc_type="unknown",
        for_purpose="unknown",
        agenda_item_text="Unknown",
        status=None,
        meeting_name=None,
        is_revision_of=None,
        file_size=None,
        date_created=None,
        validated=False,
        validation_failed=False,
    )


class TestNewCLIFlags:
    """Test suite for new CLI flags in open and checkout commands."""

    @patch("tdoc_crawler.cli.app.database_path")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    @patch("tdoc_crawler.fetching.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.app.prepare_tdoc_file")
    @patch("tdoc_crawler.cli.app.launch_file")
    def test_open_with_full_metadata_flag(
        self,
        mock_launch: Mock,
        mock_prepare: Mock,
        mock_fetch: Mock,
        mock_database_class: Mock,
        mock_database_path: Mock,
        runner: CliRunner,
        sample_tdoc_metadata: TDocMetadata,
        tmp_path: Path,
    ) -> None:
        """Test open command with --full-metadata flag."""
        # Setup mocks
        mock_db_instance = Mock()
        mock_database_class.return_value.__enter__.return_value = mock_db_instance
        mock_database_path.return_value = tmp_path / "test.db"
        mock_db_instance.get_tdoc.return_value = sample_tdoc_metadata
        mock_prepare.return_value = tmp_path / "S4-260001.zip"

        # Execute
        result = runner.invoke(app, ["open", "S4-260001", "--full-metadata"])

        # Verify
        assert result.exit_code == 0
        mock_fetch.assert_called_once()
        args, kwargs = mock_fetch.call_args
        assert kwargs["full_metadata"] is True
        assert kwargs["use_whatthespec"] is False

    @patch("tdoc_crawler.cli.app.database_path")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    @patch("tdoc_crawler.fetching.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.app.prepare_tdoc_file")
    @patch("tdoc_crawler.cli.app.launch_file")
    def test_open_with_whatthespec_flag(
        self,
        mock_launch: Mock,
        mock_prepare: Mock,
        mock_fetch: Mock,
        mock_database_class: Mock,
        mock_database_path: Mock,
        runner: CliRunner,
        sample_tdoc_metadata: TDocMetadata,
        tmp_path: Path,
    ) -> None:
        """Test open command with --use-whatthespec flag."""
        # Setup mocks
        mock_db_instance = Mock()
        mock_database_class.return_value.__enter__.return_value = mock_db_instance
        mock_database_path.return_value = tmp_path / "test.db"
        mock_db_instance.get_tdoc.return_value = sample_tdoc_metadata
        mock_prepare.return_value = tmp_path / "S4-260001.zip"

        # Execute
        result = runner.invoke(app, ["open", "S4-260001", "--use-whatthespec"])

        # Verify
        assert result.exit_code == 0
        mock_fetch.assert_called_once()
        args, kwargs = mock_fetch.call_args
        assert kwargs["use_whatthespec"] is True

    @patch("tdoc_crawler.cli.app.database_path")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    @patch("tdoc_crawler.fetching.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.app.prepare_tdoc_file")
    @patch("tdoc_crawler.cli.app.launch_file")
    def test_open_with_both_flags(
        self,
        mock_launch: Mock,
        mock_prepare: Mock,
        mock_fetch: Mock,
        mock_database_class: Mock,
        mock_database_path: Mock,
        runner: CliRunner,
        sample_tdoc_metadata: TDocMetadata,
        tmp_path: Path,
    ) -> None:
        """Test open command with both flags."""
        # Setup mocks
        mock_db_instance = Mock()
        mock_database_class.return_value.__enter__.return_value = mock_db_instance
        mock_database_path.return_value = tmp_path / "test.db"
        mock_db_instance.get_tdoc.return_value = sample_tdoc_metadata
        mock_prepare.return_value = tmp_path / "S4-260001.zip"

        # Execute
        result = runner.invoke(app, ["open", "S4-260001", "--full-metadata", "--use-whatthespec"])

        # Verify
        assert result.exit_code == 0
        mock_fetch.assert_called_once()
        args, kwargs = mock_fetch.call_args
        assert kwargs["full_metadata"] is True
        assert kwargs["use_whatthespec"] is True

    @patch("tdoc_crawler.cli.app.database_path")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    @patch("tdoc_crawler.fetching.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.app.checkout_tdoc")
    def test_checkout_with_full_metadata_flag(
        self,
        mock_checkout: Mock,
        mock_fetch: Mock,
        mock_database_class: Mock,
        mock_database_path: Mock,
        runner: CliRunner,
        sample_tdoc_metadata: TDocMetadata,
        tmp_path: Path,
    ) -> None:
        """Test checkout command with --full-metadata flag."""
        # Setup mocks
        mock_db_instance = Mock()
        mock_database_class.return_value.__enter__.return_value = mock_db_instance
        mock_database_path.return_value = tmp_path / "test.db"
        mock_db_instance.get_tdoc.return_value = sample_tdoc_metadata

        # Execute
        result = runner.invoke(app, ["checkout", "S4-260001", "--full-metadata"])

        # Verify
        assert result.exit_code == 0
        mock_fetch.assert_called_once()
        args, kwargs = mock_fetch.call_args
        assert kwargs["full_metadata"] is True

    @patch("tdoc_crawler.cli.app.database_path")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    @patch("tdoc_crawler.fetching.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.app.checkout_tdoc")
    def test_checkout_with_whatthespec_flag(
        self,
        mock_checkout: Mock,
        mock_fetch: Mock,
        mock_database_class: Mock,
        mock_database_path: Mock,
        runner: CliRunner,
        sample_tdoc_metadata: TDocMetadata,
        tmp_path: Path,
    ) -> None:
        """Test checkout command with --use-whatthespec flag."""
        # Setup mocks
        mock_db_instance = Mock()
        mock_database_class.return_value.__enter__.return_value = mock_db_instance
        mock_database_path.return_value = tmp_path / "test.db"
        mock_db_instance.get_tdoc.return_value = sample_tdoc_metadata

        # Execute
        result = runner.invoke(app, ["checkout", "S4-260001", "--use-whatthespec"])

        # Verify
        assert result.exit_code == 0
        mock_fetch.assert_called_once()
        args, kwargs = mock_fetch.call_args
        assert kwargs["use_whatthespec"] is True

    @patch("tdoc_crawler.cli.app.database_path")
    @patch("tdoc_crawler.cli.app.TDocDatabase")
    @patch("tdoc_crawler.fetching.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.app.prepare_tdoc_file")
    @patch("tdoc_crawler.cli.app.launch_file")
    def test_default_behavior_unchanged(
        self,
        mock_launch: Mock,
        mock_prepare: Mock,
        mock_fetch: Mock,
        mock_database_class: Mock,
        mock_database_path: Mock,
        runner: CliRunner,
        sample_tdoc_metadata: TDocMetadata,
        tmp_path: Path,
    ) -> None:
        """Test that default behavior (no flags) still works as expected."""
        # Setup mocks
        mock_db_instance = Mock()
        mock_database_class.return_value.__enter__.return_value = mock_db_instance
        mock_database_path.return_value = tmp_path / "test.db"
        mock_db_instance.get_tdoc.return_value = sample_tdoc_metadata
        mock_prepare.return_value = tmp_path / "S4-260001.zip"

        # Execute
        result = runner.invoke(app, ["open", "S4-260001"])

        # Verify
        assert result.exit_code == 0
        mock_fetch.assert_called_once()
        args, kwargs = mock_fetch.call_args
        assert kwargs["full_metadata"] is False
        assert kwargs["use_whatthespec"] is False
