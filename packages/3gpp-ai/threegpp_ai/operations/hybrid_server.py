"""Hybrid server lifecycle management for OpenDataLoader extraction.

This module provides:
- HybridServerManager: Start/stop/check status of the opendataloader-pdf-hybrid server
- Auto-start capability when extraction with hybrid mode is needed
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass

import httpx

HTTPCX_TIMEOUT = httpx.Timeout(15.0, connect=10.0)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5002
DEFAULT_URL = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"


@dataclass
class HybridServerConfig:
    """Configuration for the hybrid server."""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    device: str = "auto"
    log_level: str = "info"


@dataclass
class HybridServerStatus:
    """Status of the hybrid server."""

    running: bool
    url: str
    pid: int | None = None
    error: str | None = None


class HybridServerManager:
    """Manages the opendataloader-pdf-hybrid server lifecycle.

    Can start the server as a subprocess, check its health, and stop it.
    """

    def __init__(self, config: HybridServerConfig | None = None, time_out: httpx.Timeout = HTTPCX_TIMEOUT) -> None:
        self.config = config or HybridServerConfig()
        self._process: subprocess.Popen[bytes] | None = None
        self._time_out: httpx.Timeout = time_out

    @property
    def url(self) -> str:
        return f"http://{self.config.host}:{self.config.port}"

    @property
    def is_running(self) -> bool:
        """Check if the server process is alive."""
        if self._process is None:
            return False
        return self._process.poll() is None

    def check_health(self) -> HybridServerStatus:
        """Check if the server is reachable via HTTP."""
        if self._process is not None and self._process.poll() is not None:
            return HybridServerStatus(
                running=False,
                url=self.url,
                pid=self._process.pid,
                error="Process exited unexpectedly",
            )

        try:
            response = httpx.get(f"{self.url}/health", timeout=self._time_out)
            if response.status_code == 200:
                return HybridServerStatus(running=True, url=self.url, pid=self._process.pid if self._process else None)
            return HybridServerStatus(running=False, url=self.url, error=f"Health check returned {response.status_code}")
        except httpx.ConnectError:
            return HybridServerStatus(running=False, url=self.url, error="Connection refused - server not running")
        except httpx.TimeoutException:
            return HybridServerStatus(running=False, url=self.url, error="Connection timeout")
        except Exception as e:
            return HybridServerStatus(running=False, url=self.url, error=str(e))

    def start(self, *, wait: bool = True, progress_callback: Callable[[str], None] | None = None) -> HybridServerStatus:
        """Start the hybrid server as a subprocess.

        Args:
            wait: If True, wait for server to become healthy before returning.
            progress_callback: Optional callback to report startup progress.

        Returns:
            HybridServerStatus indicating success or failure.
        """
        if self.is_running or self.check_health().running:
            return HybridServerStatus(running=True, url=self.url, pid=self._process.pid if self._process else None)

        cmd = [
            "opendataloader-pdf-hybrid",
            "--host",
            self.config.host,
            "--port",
            str(self.config.port),
            "--device",
            self.config.device,
            "--log-level",
            self.config.log_level,
            "--force-ocr",
            "--enrich-formula",
            "--enrich-picture-description",
        ]

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=False,
            )

            if wait:
                status = self._wait_for_healthy(progress_callback)
                if not status.running:
                    # Capture any output from the process to help debug
                    output = self._capture_output()
                    if output:
                        status.error = f"{status.error} | Server output: {output[:500]}"
                return status
            else:
                return self.check_health()

        except FileNotFoundError:
            return HybridServerStatus(running=False, url=self.url, error="opendataloader-pdf-hybrid not found in PATH")
        except Exception as e:
            return HybridServerStatus(running=False, url=self.url, error=str(e))

    def stop(self) -> HybridServerStatus:
        """Stop the running server."""
        if self._process is None:
            return HybridServerStatus(running=False, url=self.url, error="No process to stop")

        try:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()

            status = HybridServerStatus(running=False, url=self.url, pid=self._process.pid)
            self._process = None
            return status
        except Exception as e:
            return HybridServerStatus(running=False, url=self.url, error=str(e))

    def _capture_output(self, *, timeout: float = 1.0) -> str:
        """Capture output from the process pipe if available.

        Note: This only captures output after the process has exited.
        For running processes, output may not be immediately available.
        """
        if self._process is None:
            return ""
        # Only capture if process has exited
        if self._process.poll() is None:
            return ""
        try:
            stdout, _ = self._process.communicate(timeout=timeout)
            return stdout.decode("utf-8", errors="replace") if stdout else ""
        except Exception:
            return ""

    def _wait_for_healthy(
        self,
        progress_callback: Callable[[str], None] | None = None,
    ) -> HybridServerStatus:
        """Wait for the server to become healthy."""
        # check_health() starts server if not running, also with timeout/wait handling - no need to wait here and then check again
        status = self.check_health()
        if status.running:
            return status

        if progress_callback:
            progress_callback(f"Waiting for server at {self.url}...")

        return HybridServerStatus(running=False, url=self.url, error="Server did not become healthy")


# Global manager instance for auto-start
_manager: HybridServerManager | None = None


def get_manager() -> HybridServerManager:
    """Get the global hybrid server manager instance."""
    global _manager
    if _manager is None:
        _manager = HybridServerManager()
    return _manager


def ensure_hybrid_server(
    config: HybridServerConfig | None = None,
    *,
    auto_start: bool = True,
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[HybridServerManager, HybridServerStatus]:
    """Ensure hybrid server is running.

    Args:
        config: Optional server configuration.
        auto_start: If True, start the server if not running.
        progress_callback: Optional callback for startup progress.

    Returns:
        Tuple of (manager, status).
    """
    manager = get_manager()
    if config is not None:
        manager.config = config

    status = manager.check_health()
    if not status.running and auto_start:
        status = manager.start(wait=True, progress_callback=progress_callback)

    return manager, status


__all__ = [
    "DEFAULT_URL",
    "HybridServerConfig",
    "HybridServerManager",
    "HybridServerStatus",
    "ensure_hybrid_server",
    "get_manager",
]
