"""LibreOffice server management for unoserver."""

from __future__ import annotations

import logging
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from convert_lo.exceptions import ConversionError
from convert_lo.locator import find_soffice

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ServerStatus:
    """Status of a running unoserver instance."""

    is_running: bool
    host: str
    port: int
    pid: int | None = None


class ServerManager:
    """Manages unoserver lifecycle (start/stop/status).

    This class provides methods to start, stop, and check the status
    of a unoserver instance. It can manage the server as a context manager
    or as a long-running service.

    Example:
        ```python
        # As context manager (auto start/stop)
        with ServerManager() as manager:
            converter = Converter(use_server=True)
            converter.convert(input_file, "pdf", output_dir)

        # Manual lifecycle
        manager = ServerManager()
        manager.start()
        # ... do conversions ...
        manager.stop()
        ```
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 2003,
        uno_port: int = 2002,
        soffice_path: Path | None = None,
        timeout: int = 30,
    ) -> None:
        """Initialize the server manager.

        Args:
            host: Host interface for the server (default: 127.0.0.1).
            port: XML-RPC port for client connections (default: 2003).
            uno_port: UNO port for LibreOffice communication (default: 2002).
            soffice_path: Path to soffice executable. If None, auto-detects.
            timeout: Timeout in seconds for server startup.
        """
        self._host = host
        self._port = port
        self._uno_port = uno_port
        self._soffice_path = soffice_path or find_soffice()
        self._timeout = timeout
        self._process: subprocess.Popen[str] | None = None
        self._pid: int | None = None

    @property
    def host(self) -> str:
        """Return the server host."""
        return self._host

    @property
    def port(self) -> int:
        """Return the server port."""
        return self._port

    @property
    def is_running(self) -> bool:
        """Check if the server is currently running."""
        return self._check_connection()

    def start(self, daemon: bool = False) -> None:
        """Start the unoserver.

        Args:
            daemon: If True, run as daemon process (detached).

        Raises:
            ConversionError: If server fails to start within timeout.
        """
        if self.is_running:
            logger.info("Unoserver already running on %s:%d", self._host, self._port)
            return

        cmd = [
            "unoserver",
            "--interface",
            self._host,
            "--port",
            str(self._port),
            "--uno-port",
            str(self._uno_port),
            "--executable",
            str(self._soffice_path),
        ]

        if daemon:
            cmd.append("--daemon")

        logger.info("Starting unoserver on %s:%d", self._host, self._port)
        logger.debug("Command: %s", " ".join(cmd))

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self._pid = self._process.pid

            # Wait for server to be ready
            if not self._wait_for_startup():
                msg = f"Unoserver failed to start within {self._timeout}s"
                raise ConversionError(msg)

            logger.info("Unoserver started successfully (PID: %s)", self._pid)

        except FileNotFoundError as exc:
            msg = "unoserver command not found. Ensure unoserver is installed."
            raise ConversionError(msg) from exc
        except Exception as exc:
            msg = f"Failed to start unoserver: {exc}"
            raise ConversionError(msg) from exc

    def stop(self) -> None:
        """Stop the unoserver.

        Gracefully terminates the server process. If the server does not
        stop within the timeout, it is forcefully killed.
        """
        if self._process is None:
            logger.warning("Cannot stop: server was not started by this manager")
            return

        if self._process.poll() is None:
            logger.info("Stopping unoserver (PID: %s)", self._pid)
            self._process.terminate()

            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("Graceful shutdown failed, killing process")
                self._process.kill()
                self._process.wait()

        self._process = None
        self._pid = None
        logger.info("Unoserver stopped")

    def status(self) -> ServerStatus:
        """Get the current server status.

        Returns:
            ServerStatus with connection info and PID.
        """
        is_running = self._check_connection()
        return ServerStatus(
            is_running=is_running,
            host=self._host,
            port=self._port,
            pid=self._pid if is_running else None,
        )

    def _check_connection(self) -> bool:
        """Check if the server is accepting connections.

        Returns:
            True if server is reachable, False otherwise.
        """
        try:
            with socket.create_connection(
                (self._host, self._port),
                timeout=2,
            ):
                return True
        except socket.timeout, ConnectionRefusedError, OSError:
            return False

    def _wait_for_startup(self) -> bool:
        """Wait for server to become available.

        Returns:
            True if server started, False if timeout.
        """
        start_time = time.monotonic()
        while (time.monotonic() - start_time) < self._timeout:
            if self._process is not None and self._process.poll() is not None:
                # Process exited prematurely
                stderr = self._process.stderr.read() if self._process.stderr else ""
                logger.error("Unoserver exited prematurely: %s", stderr)
                return False

            if self._check_connection():
                return True

            time.sleep(0.5)

        return False

    def __enter__(self) -> ServerManager:
        """Start server on context entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop server on context exit."""
        self.stop()


def is_server_running(host: str = "127.0.0.1", port: int = 2003) -> bool:
    """Check if a unoserver is running at the specified address.

    Args:
        host: Server host to check.
        port: Server port to check.

    Returns:
        True if server is running, False otherwise.
    """
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except socket.timeout, ConnectionRefusedError, OSError:
        return False


def get_server_mode(
    host: str = "127.0.0.1",
    port: int = 2003,
    auto_start: bool = False,
) -> Literal["server", "cli", "started"]:
    """Determine the conversion mode to use.

    Args:
        host: Server host to check.
        port: Server port to check.
        auto_start: If True, start server if not running.

    Returns:
        "server" if server is running,
        "started" if server was started,
        "cli" if falling back to CLI mode.
    """
    if is_server_running(host, port):
        return "server"

    if auto_start:
        try:
            manager = ServerManager(host=host, port=port)
            manager.start()
            return "started"
        except ConversionError:
            logger.warning("Failed to auto-start server, using CLI mode")
            return "cli"

    return "cli"
