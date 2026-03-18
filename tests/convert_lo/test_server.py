"""Tests for unoserver management."""

from __future__ import annotations

import socket
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from convert_lo.exceptions import ConversionError
from convert_lo.server import ServerManager, ServerStatus, get_server_mode, is_server_running


class TestServerStatus:
    """Tests for ServerStatus dataclass."""

    def test_server_status_running(self) -> None:
        """Create status for running server."""
        status = ServerStatus(
            is_running=True,
            host="127.0.0.1",
            port=2003,
            pid=12345,
        )

        assert status.is_running is True
        assert status.host == "127.0.0.1"
        assert status.port == 2003
        assert status.pid == 12345

    def test_server_status_stopped(self) -> None:
        """Create status for stopped server."""
        status = ServerStatus(
            is_running=False,
            host="127.0.0.1",
            port=2003,
            pid=None,
        )

        assert status.is_running is False
        assert status.pid is None


class TestIsServerRunning:
    """Tests for is_server_running function."""

    def test_server_running_success(self) -> None:
        """Return True when server accepts connection."""
        with patch("convert_lo.server.socket.create_connection") as mock_connect:
            mock_connect.return_value.__enter__ = MagicMock()
            mock_connect.return_value.__exit__ = MagicMock()

            result = is_server_running("127.0.0.1", 2003)

            assert result is True
            mock_connect.assert_called_once_with(("127.0.0.1", 2003), timeout=2)

    def test_server_running_timeout(self) -> None:
        """Return False on connection timeout."""
        with patch("convert_lo.server.socket.create_connection") as mock_connect:
            mock_connect.side_effect = socket.timeout

            result = is_server_running("127.0.0.1", 2003)

            assert result is False

    def test_server_running_refused(self) -> None:
        """Return False on connection refused."""
        with patch("convert_lo.server.socket.create_connection") as mock_connect:
            mock_connect.side_effect = ConnectionRefusedError

            result = is_server_running("127.0.0.1", 2003)

            assert result is False

    def test_server_running_os_error(self) -> None:
        """Return False on OSError."""
        with patch("convert_lo.server.socket.create_connection") as mock_connect:
            mock_connect.side_effect = OSError

            result = is_server_running("127.0.0.1", 2003)

            assert result is False


class TestGetServerMode:
    """Tests for get_server_mode function."""

    def test_get_server_mode_server_running(self) -> None:
        """Return 'server' when server is running."""
        with patch("convert_lo.server.is_server_running", return_value=True):
            result = get_server_mode("127.0.0.1", 2003, auto_start=False)
            assert result == "server"

    def test_get_server_mode_cli_fallback(self) -> None:
        """Return 'cli' when server not running and auto_start=False."""
        with patch("convert_lo.server.is_server_running", return_value=False):
            result = get_server_mode("127.0.0.1", 2003, auto_start=False)
            assert result == "cli"

    def test_get_server_mode_auto_start_success(self) -> None:
        """Return 'started' when auto_start succeeds."""
        with (
            patch("convert_lo.server.is_server_running", return_value=False),
            patch("convert_lo.server.ServerManager") as mock_manager_class,
        ):
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            result = get_server_mode("127.0.0.1", 2003, auto_start=True)

            assert result == "started"
            mock_manager.start.assert_called_once()

    def test_get_server_mode_auto_start_failure(self) -> None:
        """Return 'cli' when auto_start fails."""
        with (
            patch("convert_lo.server.is_server_running", return_value=False),
            patch("convert_lo.server.ServerManager") as mock_manager_class,
        ):
            mock_manager = MagicMock()
            mock_manager.start.side_effect = ConversionError("Failed")
            mock_manager_class.return_value = mock_manager

            result = get_server_mode("127.0.0.1", 2003, auto_start=True)

            assert result == "cli"


class TestServerManager:
    """Tests for ServerManager class."""

    def test_server_manager_init_default(self) -> None:
        """Initialize with default parameters."""
        manager = ServerManager()

        assert manager.host == "127.0.0.1"
        assert manager.port == 2003
        assert manager._uno_port == 2002
        assert manager._timeout == 30

    def test_server_manager_init_custom(self) -> None:
        """Initialize with custom parameters."""
        manager = ServerManager(
            host="0.0.0.0",
            port=3003,
            uno_port=3002,
            timeout=60,
        )

        assert manager.host == "0.0.0.0"
        assert manager.port == 3003
        assert manager._uno_port == 3002
        assert manager._timeout == 60

    def test_server_manager_init_with_soffice_path(self) -> None:
        """Initialize with custom soffice path."""
        soffice_path = Path("C:/custom/soffice.exe")
        manager = ServerManager(soffice_path=soffice_path)

        assert manager._soffice_path == soffice_path

    def test_server_manager_status_not_running(self) -> None:
        """Get status when server is not running."""
        with patch("convert_lo.server.ServerManager._check_connection", return_value=False):
            manager = ServerManager()
            status = manager.status()

            assert status.is_running is False
            assert status.pid is None

    def test_server_manager_status_running(self) -> None:
        """Get status when server is running."""
        with patch("convert_lo.server.ServerManager._check_connection", return_value=True):
            manager = ServerManager()
            manager._pid = 12345
            status = manager.status()

            assert status.is_running is True
            assert status.pid == 12345

    def test_server_manager_is_running_property(self) -> None:
        """Check is_running property delegates to _check_connection."""
        with patch("convert_lo.server.ServerManager._check_connection", return_value=True):
            manager = ServerManager()
            assert manager.is_running is True

    def test_server_manager_start_already_running(self) -> None:
        """Skip start if server already running."""
        with patch("convert_lo.server.ServerManager._check_connection", return_value=True):
            manager = ServerManager()
            manager.start()

            # Should not attempt to start new process
            assert manager._process is None

    def test_server_manager_start_success(self) -> None:
        """Start server successfully."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Process still running

        with (
            patch("convert_lo.server.ServerManager._check_connection", side_effect=[False, True]),
            patch("convert_lo.server.subprocess.Popen", return_value=mock_process),
            patch("convert_lo.server.time.monotonic", side_effect=[0, 1, 2]),
        ):
            manager = ServerManager()
            manager.start()

            assert manager._process is not None
            assert manager._pid == 12345

    def test_server_manager_start_timeout(self) -> None:
        """Raise ConversionError on startup timeout."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None

        with (
            patch("convert_lo.server.ServerManager._check_connection", return_value=False),
            patch("convert_lo.server.subprocess.Popen", return_value=mock_process),
            patch("convert_lo.server.time.monotonic", side_effect=[0, 35]),  # Timeout
        ):
            manager = ServerManager(timeout=30)

            with pytest.raises(ConversionError, match="failed to start within"):
                manager.start()

    def test_server_manager_stop_not_started(self) -> None:
        """Stop when server was not started."""
        manager = ServerManager()
        manager.stop()

        # Should not raise, just log warning
        assert manager._process is None

    def test_server_manager_stop_success(self) -> None:
        """Stop server gracefully."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Running
        mock_process.wait.return_value = 0

        manager = ServerManager()
        manager._process = mock_process

        manager.stop()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()
        assert manager._process is None

    def test_server_manager_stop_force_kill(self) -> None:
        """Force kill on graceful shutdown timeout."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        # First wait() times out, second wait() (after kill) succeeds
        mock_process.wait.side_effect = [subprocess.TimeoutExpired(cmd="unoserver", timeout=10), None]

        manager = ServerManager()
        manager._process = mock_process

        manager.stop()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        assert manager._process is None

    def test_server_manager_context_manager(self) -> None:
        """Use as context manager."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_process.wait.return_value = 0

        with (
            patch("convert_lo.server.ServerManager._check_connection", side_effect=[False, True, True]),
            patch("convert_lo.server.subprocess.Popen", return_value=mock_process),
            patch("convert_lo.server.time.monotonic", side_effect=[0, 1, 2]),
        ):
            with ServerManager() as manager:
                assert manager._process is not None

            # Server should be stopped after context exit
            mock_process.terminate.assert_called_once()

    def test_server_manager_check_connection_success(self) -> None:
        """Check connection returns True when server accepts."""
        with patch("convert_lo.server.socket.create_connection") as mock_connect:
            mock_connect.return_value.__enter__ = MagicMock()
            mock_connect.return_value.__exit__ = MagicMock()

            manager = ServerManager()
            result = manager._check_connection()

            assert result is True

    def test_server_manager_check_connection_failure(self) -> None:
        """Check connection returns False when server unavailable."""
        with patch("convert_lo.server.socket.create_connection") as mock_connect:
            mock_connect.side_effect = ConnectionRefusedError

            manager = ServerManager()
            result = manager._check_connection()

            assert result is False

    def test_server_manager_wait_for_startup_success(self) -> None:
        """Wait for startup returns True when server becomes available."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None

        with (
            patch("convert_lo.server.ServerManager._check_connection", side_effect=[False, False, True]),
            patch("convert_lo.server.time.monotonic", side_effect=[0, 0.5, 1.0, 1.5]),
            patch("convert_lo.server.time.sleep"),
        ):
            manager = ServerManager()
            manager._process = mock_process

            result = manager._wait_for_startup()

            assert result is True

    def test_server_manager_wait_for_startup_process_exits(self) -> None:
        """Wait for startup returns False if process exits prematurely."""
        mock_process = MagicMock()
        mock_process.poll.return_value = 1  # Exited with error
        mock_process.stderr.read.return_value = "Error message"

        with patch("convert_lo.server.time.monotonic", return_value=0):
            manager = ServerManager()
            manager._process = mock_process

            result = manager._wait_for_startup()

            assert result is False


# Import subprocess for the test
import subprocess
