"""Tests for CLI dependency injection integration (cli/di.py and --di-mode flag)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from tdoc_crawler.cli import app
from tdoc_crawler.cli import di as cli_di
from tdoc_crawler.di.container import ServiceContainer

runner = CliRunner()


@pytest.fixture(autouse=True)
def reset_container() -> None:
    """Reset the module-level container state between tests."""
    cli_di.set_container(None)
    yield
    cli_di.set_container(None)


class TestCliDiModule:
    """Tests for the cli.di module state management helpers."""

    def test_initial_state_is_none(self) -> None:
        """Container is None before any set_container call."""
        assert cli_di.get_container() is None

    def test_is_di_mode_false_initially(self) -> None:
        """is_di_mode returns False when no container is set."""
        assert cli_di.is_di_mode() is False

    def test_set_container_activates_di_mode(self, tmp_path: Path) -> None:
        """Setting a container activates DI mode."""
        container = ServiceContainer(cache_dir=tmp_path)
        cli_di.set_container(container)

        assert cli_di.get_container() is container
        assert cli_di.is_di_mode() is True

    def test_set_container_none_deactivates_di_mode(self, tmp_path: Path) -> None:
        """Setting container to None deactivates DI mode."""
        container = ServiceContainer(cache_dir=tmp_path)
        cli_di.set_container(container)
        cli_di.set_container(None)

        assert cli_di.get_container() is None
        assert cli_di.is_di_mode() is False

    def test_get_container_returns_same_instance(self, tmp_path: Path) -> None:
        """get_container returns the exact instance that was set."""
        container = ServiceContainer(cache_dir=tmp_path)
        cli_di.set_container(container)

        assert cli_di.get_container() is container

    def test_resolve_cache_dir_no_container_returns_arg(self, tmp_path: Path) -> None:
        """resolve_cache_dir returns the passed path when no container is active."""
        result = cli_di.resolve_cache_dir(tmp_path)
        assert result == tmp_path

    def test_resolve_cache_dir_no_container_returns_none(self) -> None:
        """resolve_cache_dir returns None when no container and no arg."""
        result = cli_di.resolve_cache_dir(None)
        assert result is None

    def test_resolve_cache_dir_container_without_cache_manager_returns_arg(
        self, tmp_path: Path
    ) -> None:
        """resolve_cache_dir falls back to arg when container has no initialized cache manager."""
        container = ServiceContainer(cache_dir=tmp_path)
        cli_di.set_container(container)
        # _cache_manager is None because cache_manager property has not been accessed
        assert container._cache_manager is None

        fallback = tmp_path / "fallback"
        result = cli_di.resolve_cache_dir(fallback)
        assert result == fallback

    def test_resolve_cache_dir_container_with_cache_manager_returns_root(
        self, tmp_path: Path
    ) -> None:
        """resolve_cache_dir returns container's cache root when cache manager is initialized."""
        container = ServiceContainer(cache_dir=tmp_path, name="test-di")
        _ = container.cache_manager  # trigger lazy initialization
        cli_di.set_container(container)

        result = cli_di.resolve_cache_dir(Path("/some/other/path"))
        assert result == container._cache_manager.root


class TestDiModeFlag:
    """Tests for the --di-mode / --no-di-mode global CLI flag."""

    def test_help_shows_di_mode_option(self) -> None:
        """--di-mode appears in --help output."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--di-mode" in result.stdout
        assert "--no-di-mode" in result.stdout

    def test_no_di_mode_by_default(self, tmp_path: Path) -> None:
        """Container is not activated when --di-mode is not passed."""
        with (
            patch("tdoc_crawler.cli.app.ServiceContainer") as mock_container_class,
            patch("tdoc_crawler.cli.app.CacheManager") as mock_cm_class,
            patch("tdoc_crawler.cli.app.MeetingDatabase") as mock_db_class,
        ):
            db_file = tmp_path / "tdoc_crawler.db"
            db_file.touch()
            mock_cm = MagicMock()
            mock_cm.db_file = db_file
            mock_cm_class.return_value.register.return_value = mock_cm
            db_mock = MagicMock()
            db_mock.__enter__ = MagicMock(return_value=db_mock)
            db_mock.__exit__ = MagicMock(return_value=False)
            db_mock.get_statistics.return_value = {}
            mock_db_class.return_value = db_mock

            runner.invoke(app, ["--cache-dir", str(tmp_path), "stats"])

        mock_container_class.assert_not_called()

    @patch("tdoc_crawler.cli.app.ServiceContainer")
    def test_di_mode_flag_creates_container(
        self, mock_container_class: MagicMock, tmp_path: Path
    ) -> None:
        """--di-mode creates a ServiceContainer and registers it."""
        mock_container = MagicMock(spec=ServiceContainer)
        mock_container_class.return_value = mock_container

        with (
            patch("tdoc_crawler.cli.app.CacheManager") as mock_cm_class,
            patch("tdoc_crawler.cli.app.MeetingDatabase") as mock_db_class,
        ):
            db_file = tmp_path / "tdoc_crawler.db"
            db_file.touch()
            mock_cm = MagicMock()
            mock_cm.db_file = db_file
            mock_cm_class.return_value.register.return_value = mock_cm
            db_mock = MagicMock()
            db_mock.__enter__ = MagicMock(return_value=db_mock)
            db_mock.__exit__ = MagicMock(return_value=False)
            db_mock.get_statistics.return_value = {}
            mock_db_class.return_value = db_mock

            result = runner.invoke(
                app,
                ["--di-mode", "--cache-dir", str(tmp_path), "stats"],
            )

        assert result.exit_code == 0
        mock_container_class.assert_called_once_with(cache_dir=tmp_path)

    @patch("tdoc_crawler.cli.app.ServiceContainer")
    def test_di_mode_flag_close_called_on_exit(
        self, mock_container_class: MagicMock, tmp_path: Path
    ) -> None:
        """Container.close() is called after the command completes."""
        mock_container = MagicMock(spec=ServiceContainer)
        mock_container_class.return_value = mock_container

        with (
            patch("tdoc_crawler.cli.app.CacheManager") as mock_cm_class,
            patch("tdoc_crawler.cli.app.MeetingDatabase") as mock_db_class,
        ):
            db_file = tmp_path / "tdoc_crawler.db"
            db_file.touch()
            mock_cm = MagicMock()
            mock_cm.db_file = db_file
            mock_cm_class.return_value.register.return_value = mock_cm
            db_mock = MagicMock()
            db_mock.__enter__ = MagicMock(return_value=db_mock)
            db_mock.__exit__ = MagicMock(return_value=False)
            db_mock.get_statistics.return_value = {}
            mock_db_class.return_value = db_mock

            runner.invoke(
                app,
                ["--di-mode", "--cache-dir", str(tmp_path), "stats"],
            )

        mock_container.close.assert_called_once()

    @patch("tdoc_crawler.cli.app.ServiceContainer")
    def test_no_di_mode_flag_no_container_created(
        self, mock_container_class: MagicMock, tmp_path: Path
    ) -> None:
        """--no-di-mode does not create a ServiceContainer."""
        with (
            patch("tdoc_crawler.cli.app.CacheManager") as mock_cm_class,
            patch("tdoc_crawler.cli.app.MeetingDatabase") as mock_db_class,
        ):
            db_file = tmp_path / "tdoc_crawler.db"
            db_file.touch()
            mock_cm = MagicMock()
            mock_cm.db_file = db_file
            mock_cm_class.return_value.register.return_value = mock_cm
            db_mock = MagicMock()
            db_mock.__enter__ = MagicMock(return_value=db_mock)
            db_mock.__exit__ = MagicMock(return_value=False)
            db_mock.get_statistics.return_value = {}
            mock_db_class.return_value = db_mock

            runner.invoke(
                app,
                ["--no-di-mode", "--cache-dir", str(tmp_path), "stats"],
            )

        mock_container_class.assert_not_called()

    def test_di_mode_env_var(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """TDC_DI_MODE env var activates DI mode."""
        monkeypatch.setenv("TDC_DI_MODE", "true")

        with (
            patch("tdoc_crawler.cli.app.ServiceContainer") as mock_container_class,
            patch("tdoc_crawler.cli.app.CacheManager") as mock_cm_class,
            patch("tdoc_crawler.cli.app.MeetingDatabase") as mock_db_class,
        ):
            db_file = tmp_path / "tdoc_crawler.db"
            db_file.touch()
            mock_cm = MagicMock()
            mock_cm.db_file = db_file
            mock_cm_class.return_value.register.return_value = mock_cm
            db_mock = MagicMock()
            db_mock.__enter__ = MagicMock(return_value=db_mock)
            db_mock.__exit__ = MagicMock(return_value=False)
            db_mock.get_statistics.return_value = {}
            mock_db_class.return_value = db_mock
            mock_container = MagicMock(spec=ServiceContainer)
            mock_container_class.return_value = mock_container

            runner.invoke(app, ["--cache-dir", str(tmp_path), "stats"])

        mock_container_class.assert_called_once()
