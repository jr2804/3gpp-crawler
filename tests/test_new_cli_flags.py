"""Tests for the new CLI flags --full-metadata and --use-whatthespec."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from typer.testing import CliRunner

from tdoc_crawler.cli import tdoc_app
from tdoc_crawler.config import DEFAULT_HTTP_CACHE_FILENAME, CheckoutConfig
from tdoc_crawler.database.oxyde_models import TDocMetadata
from tdoc_crawler.models.main_files import MainFileSelection, MainFileSelector, MainFileSource
from tdoc_crawler.tdocs.operations.fetch import FetchMissingResult
from tdoc_crawler.tdocs.operations.open import TDocOpenResult


class TestNewCLIFlags:
    """Test suite for new CLI flags in open and checkout commands."""

    @patch("tdoc_crawler.cli.tdoc_app.create_cached_session")
    @patch("tdoc_crawler.cli.tdoc_app.resolve_tdoc_main_file")
    @patch("tdoc_crawler.cli.tdoc_app.launch_file")
    @patch("tdoc_crawler.cli.tdoc_app.set_credentials")
    @patch("tdoc_crawler.cli.tdoc_app.load_cli_config")
    def test_open_with_full_metadata_flag(
        self,
        mock_load_config: Mock,
        mock_set_creds: Mock,
        mock_launch: Mock,
        mock_resolve: Mock,
        mock_session: Mock,
        runner: CliRunner,
        sample_tdoc_metadata: TDocMetadata,
        tmp_path: Path,
    ) -> None:
        """Test open command with --full-metadata flag."""
        mock_config = _make_mock_config(tmp_path)
        mock_load_config.side_effect = _make_load_cli_config_side_effect(mock_config)

        mock_resolve.return_value = TDocOpenResult(
            metadata=sample_tdoc_metadata,
            selection=MainFileSelection(path=tmp_path / "S4-260001.zip", relative_path="S4-260001.zip", source=MainFileSource.HEURISTIC),
        )
        mock_set_creds.return_value = None
        mock_session.return_value.__enter__.return_value = Mock()

        result = runner.invoke(tdoc_app, ["open", "S4-260001", "--full-metadata"])

        assert result.exit_code == 0, result.output
        _, kwargs = mock_resolve.call_args
        assert kwargs["full_metadata"] is True
        assert kwargs["use_whatthespec"] is False

    @patch("tdoc_crawler.cli.tdoc_app.create_cached_session")
    @patch("tdoc_crawler.cli.tdoc_app.resolve_tdoc_main_file")
    @patch("tdoc_crawler.cli.tdoc_app.launch_file")
    @patch("tdoc_crawler.cli.tdoc_app.set_credentials")
    @patch("tdoc_crawler.cli.tdoc_app.load_cli_config")
    def test_open_selector_flag_overrides_config(
        self,
        mock_load_config: Mock,
        mock_set_creds: Mock,
        mock_launch: Mock,
        mock_resolve: Mock,
        mock_session: Mock,
        runner: CliRunner,
        sample_tdoc_metadata: TDocMetadata,
        tmp_path: Path,
    ) -> None:
        """--selector overrides the configured main-file strategy for one run."""
        mock_config = _make_mock_config(tmp_path)
        mock_load_config.side_effect = _make_load_cli_config_side_effect(mock_config)

        mock_resolve.return_value = TDocOpenResult(
            metadata=sample_tdoc_metadata,
            selection=MainFileSelection(path=tmp_path / "S4-260001.zip", relative_path="S4-260001.zip", source=MainFileSource.HEURISTIC),
        )
        mock_set_creds.return_value = None
        mock_session.return_value.__enter__.return_value = Mock()

        result = runner.invoke(tdoc_app, ["open", "S4-260001", "--selector", "decision_model"])

        assert result.exit_code == 0, result.output
        _, kwargs = mock_resolve.call_args
        assert kwargs["checkout_config"].selector is MainFileSelector.DECISION_MODEL
        # The shared config object must not be mutated by the one-off override.
        assert mock_config.checkout.selector is MainFileSelector.HEURISTIC

    @patch("tdoc_crawler.cli.tdoc_app.create_cached_session")
    @patch("tdoc_crawler.cli.tdoc_app.resolve_tdoc_main_file")
    @patch("tdoc_crawler.cli.tdoc_app.launch_file")
    @patch("tdoc_crawler.cli.tdoc_app.set_credentials")
    @patch("tdoc_crawler.cli.tdoc_app.load_cli_config")
    def test_open_with_whatthespec_flag(
        self,
        mock_load_config: Mock,
        mock_set_creds: Mock,
        mock_launch: Mock,
        mock_resolve: Mock,
        mock_session: Mock,
        runner: CliRunner,
        sample_tdoc_metadata: TDocMetadata,
        tmp_path: Path,
    ) -> None:
        """Test open command with --use-whatthespec flag."""
        mock_config = _make_mock_config(tmp_path)
        mock_load_config.side_effect = _make_load_cli_config_side_effect(mock_config)

        mock_resolve.return_value = TDocOpenResult(
            metadata=sample_tdoc_metadata,
            selection=MainFileSelection(path=tmp_path / "S4-260001.zip", relative_path="S4-260001.zip", source=MainFileSource.HEURISTIC),
        )
        mock_set_creds.return_value = None
        mock_session.return_value.__enter__.return_value = Mock()

        result = runner.invoke(tdoc_app, ["open", "S4-260001", "--use-whatthespec"])

        assert result.exit_code == 0, result.output
        _, kwargs = mock_resolve.call_args
        assert kwargs["use_whatthespec"] is True

    @patch("tdoc_crawler.cli.tdoc_app.create_cached_session")
    @patch("tdoc_crawler.cli.tdoc_app.resolve_tdoc_main_file")
    @patch("tdoc_crawler.cli.tdoc_app.launch_file")
    @patch("tdoc_crawler.cli.tdoc_app.set_credentials")
    @patch("tdoc_crawler.cli.tdoc_app.load_cli_config")
    def test_open_with_both_flags(
        self,
        mock_load_config: Mock,
        mock_set_creds: Mock,
        mock_launch: Mock,
        mock_resolve: Mock,
        mock_session: Mock,
        runner: CliRunner,
        sample_tdoc_metadata: TDocMetadata,
        tmp_path: Path,
    ) -> None:
        """Test open command with both flags."""
        mock_config = _make_mock_config(tmp_path)
        mock_load_config.side_effect = _make_load_cli_config_side_effect(mock_config)

        mock_resolve.return_value = TDocOpenResult(
            metadata=sample_tdoc_metadata,
            selection=MainFileSelection(path=tmp_path / "S4-260001.zip", relative_path="S4-260001.zip", source=MainFileSource.HEURISTIC),
        )
        mock_set_creds.return_value = None
        mock_session.return_value.__enter__.return_value = Mock()

        result = runner.invoke(tdoc_app, ["open", "S4-260001", "--full-metadata", "--use-whatthespec"])

        assert result.exit_code == 0, result.output
        _, kwargs = mock_resolve.call_args
        assert kwargs["full_metadata"] is True
        assert kwargs["use_whatthespec"] is True

    @patch("tdoc_crawler.cli.checkout.TDocDatabase")
    @patch("tdoc_crawler.cli.checkout.create_cached_session")
    @patch("tdoc_crawler.cli.checkout.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.checkout.checkout_tdoc")
    @patch("tdoc_crawler.cli.checkout.set_credentials")
    @patch("tdoc_crawler.cli.tdoc_app.load_cli_config")
    def test_checkout_with_full_metadata_flag(
        self,
        mock_load_config: Mock,
        mock_set_creds: Mock,
        mock_checkout: Mock,
        mock_fetch: Mock,
        mock_session: Mock,
        mock_database_class: Mock,
        runner: CliRunner,
        sample_tdoc_metadata: TDocMetadata,
        tmp_path: Path,
    ) -> None:
        """Test checkout command with --full-metadata flag."""
        mock_config = _make_mock_config(tmp_path)
        mock_load_config.side_effect = _make_load_cli_config_side_effect(mock_config)

        # Setup database mock
        mock_db_instance = MagicMock()
        mock_database_class.return_value.__aenter__.return_value = mock_db_instance
        mock_db_instance.query_tdocs = AsyncMock(return_value=[])
        mock_db_instance.get_main_file_override = AsyncMock(return_value=None)

        # Setup other mocks
        mock_fetch.return_value = FetchMissingResult(refreshed=[sample_tdoc_metadata], fetch_result=None)
        mock_set_creds.return_value = None
        mock_session.return_value.__enter__.return_value = Mock()
        mock_checkout.return_value = tmp_path / "S4-260001.zip"

        # Execute
        result = runner.invoke(tdoc_app, ["checkout", "S4-260001", "--full-metadata"])

        # Verify
        assert result.exit_code == 0, result.output
        mock_fetch.assert_called_once()
        args, kwargs = mock_fetch.call_args
        assert kwargs["full_metadata"] is True

    @patch("tdoc_crawler.cli.checkout.TDocDatabase")
    @patch("tdoc_crawler.cli.checkout.create_cached_session")
    @patch("tdoc_crawler.cli.checkout.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.checkout.checkout_tdoc")
    @patch("tdoc_crawler.cli.checkout.set_credentials")
    @patch("tdoc_crawler.cli.tdoc_app.load_cli_config")
    def test_checkout_with_whatthespec_flag(
        self,
        mock_load_config: Mock,
        mock_set_creds: Mock,
        mock_checkout: Mock,
        mock_fetch: Mock,
        mock_session: Mock,
        mock_database_class: Mock,
        runner: CliRunner,
        sample_tdoc_metadata: TDocMetadata,
        tmp_path: Path,
    ) -> None:
        """Test checkout command with --use-whatthespec flag."""
        mock_config = _make_mock_config(tmp_path)
        mock_load_config.side_effect = _make_load_cli_config_side_effect(mock_config)

        # Setup database mock
        mock_db_instance = MagicMock()
        mock_database_class.return_value.__aenter__.return_value = mock_db_instance
        mock_db_instance.query_tdocs = AsyncMock(return_value=[])
        mock_db_instance.get_main_file_override = AsyncMock(return_value=None)

        # Setup other mocks
        mock_fetch.return_value = FetchMissingResult(refreshed=[sample_tdoc_metadata], fetch_result=None)
        mock_set_creds.return_value = None
        mock_session.return_value.__enter__.return_value = Mock()
        mock_checkout.return_value = tmp_path / "S4-260001.zip"

        # Execute
        result = runner.invoke(tdoc_app, ["checkout", "S4-260001", "--use-whatthespec"])

        # Verify
        assert result.exit_code == 0, result.output
        mock_fetch.assert_called_once()
        args, kwargs = mock_fetch.call_args
        assert kwargs["use_whatthespec"] is True

    @patch("tdoc_crawler.cli.tdoc_app.create_cached_session")
    @patch("tdoc_crawler.cli.tdoc_app.resolve_tdoc_main_file")
    @patch("tdoc_crawler.cli.tdoc_app.launch_file")
    @patch("tdoc_crawler.cli.tdoc_app.set_credentials")
    @patch("tdoc_crawler.cli.tdoc_app.load_cli_config")
    def test_default_behavior_unchanged(
        self,
        mock_load_config: Mock,
        mock_set_creds: Mock,
        mock_launch: Mock,
        mock_resolve: Mock,
        mock_session: Mock,
        runner: CliRunner,
        sample_tdoc_metadata: TDocMetadata,
        tmp_path: Path,
    ) -> None:
        """Test open command without flags uses default behavior."""
        mock_config = _make_mock_config(tmp_path)
        mock_load_config.side_effect = _make_load_cli_config_side_effect(mock_config)

        mock_resolve.return_value = TDocOpenResult(
            metadata=sample_tdoc_metadata,
            selection=MainFileSelection(path=tmp_path / "S4-260001.zip", relative_path="S4-260001.zip", source=MainFileSource.HEURISTIC),
        )
        mock_set_creds.return_value = None
        mock_session.return_value.__enter__.return_value = Mock()

        result = runner.invoke(tdoc_app, ["open", "S4-260001"])

        assert result.exit_code == 0, result.output
        _, kwargs = mock_resolve.call_args
        assert kwargs["full_metadata"] is False
        assert kwargs["use_whatthespec"] is False


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
        agenda_item_nbr="1.1",
        url="https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_123/Docs/S4-260001.zip",
        tdoc_type="unknown",
        for_purpose="unknown",
        agenda_item_text="Unknown",
        status=None,
        is_revision_of=None,
        file_size=None,
        date_created=None,
        validated=False,
        validation_failed=False,
    )


def _make_mock_config(tmp_path: Path) -> MagicMock:
    """Create a mock ThreeGPPConfig whose path.* attributes point to tmp_path."""
    mock_config = MagicMock()
    mock_config.path.db_file = tmp_path / "test.db"
    mock_config.path.http_cache_file = tmp_path / DEFAULT_HTTP_CACHE_FILENAME
    mock_config.path.checkout_dir = tmp_path / "checkout"
    mock_config.path.cache_dir = tmp_path
    mock_config.checkout = CheckoutConfig()
    return mock_config


def _make_load_cli_config_side_effect(mock_config: MagicMock) -> object:
    """Return a side_effect function that sets ctx.obj and returns mock_config."""

    def side_effect(ctx: Any, config_file: Any = None) -> MagicMock:
        ctx.obj = mock_config
        return mock_config

    return side_effect
