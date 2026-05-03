"""Hybrid server lifecycle management for OpenDataLoader extraction.

Manages the opendataloader-pdf-hybrid server process: start, health check, stop.
Provides auto-start capability for conversion pipelines that require hybrid mode.
"""

from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO

import niquests

from tdoc_crawler.config import resolve_cache_manager

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5002
DEFAULT_URL = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"
_HEALTH_CHECK_TIMEOUT = 15.0
_CONNECT_TIMEOUT = 10.0
_STARTUP_MAX_WAIT = 600  # seconds — docling model loading can take several minutes
_LOGS_DIR_NAME = "logs"
_SERVER_LOG_FILENAME = "hybrid-server.log"


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

    Starts the server as a subprocess, checks its health, and stops it.
    """

    def __init__(self, config: HybridServerConfig | None = None) -> None:
        self.config = config or HybridServerConfig()
        self._process: subprocess.Popen[bytes] | None = None
        self._log_file_handle: IO[bytes] | None = None

    @property
    def url(self) -> str:
        return f"http://{self.config.host}:{self.config.port}"

    @property
    def is_running(self) -> bool:
        """Check if the server subprocess is still alive."""
        if self._process is None:
            return False
        return self._process.poll() is None

    @property
    def log_file(self) -> Path:
        """Path to the hybrid server log file."""
        cache = resolve_cache_manager()
        logs_dir = cache.root / _LOGS_DIR_NAME
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir / _SERVER_LOG_FILENAME

    def check_health(self) -> HybridServerStatus:
        """Check if the hybrid server is reachable via HTTP health endpoint."""
        if self._process is not None and self._process.poll() is not None:
            return HybridServerStatus(
                running=False,
                url=self.url,
                pid=self._process.pid,
                error="Process exited unexpectedly",
            )

        try:
            response = niquests.get(
                f"{self.url}/health",
                timeout=(_CONNECT_TIMEOUT, _HEALTH_CHECK_TIMEOUT),
            )
            if response.status_code == 200:
                return HybridServerStatus(
                    running=True,
                    url=self.url,
                    pid=self._process.pid if self._process else None,
                )
            return HybridServerStatus(
                running=False,
                url=self.url,
                error=f"Health check returned {response.status_code}",
            )
        except niquests.ConnectionError:
            return HybridServerStatus(
                running=False,
                url=self.url,
                error="Connection refused - server not running",
            )
        except niquests.Timeout:
            return HybridServerStatus(
                running=False,
                url=self.url,
                error="Connection timeout",
            )
        except Exception as e:
            return HybridServerStatus(running=False, url=self.url, error=str(e))

    def start(
        self,
        *,
        wait: bool = True,
        progress_callback: Callable[[str], None] | None = None,
    ) -> HybridServerStatus:
        """Start the hybrid server as a subprocess.

        Args:
            wait: If True, wait for server to become healthy before returning.
            progress_callback: Optional callback to report startup progress.

        Returns:
            HybridServerStatus indicating success or failure.
        """
        # Already running?
        health = self.check_health()
        if health.running:
            return health

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
            log_path = self.log_file
            self._log_file_handle = log_path.open("ab")
            self._process = subprocess.Popen(  # noqa: S603 — binary name is hardcoded, not user input
                cmd,
                stdout=self._log_file_handle,
                stderr=subprocess.STDOUT,
            )
            logger.info("Started opendataloader-pdf-hybrid (pid=%s) at %s — logs: %s", self._process.pid, self.url, log_path)
        except FileNotFoundError:
            return HybridServerStatus(
                running=False,
                url=self.url,
                error="opendataloader-pdf-hybrid not found in PATH",
            )
        except OSError as e:
            return HybridServerStatus(running=False, url=self.url, error=str(e))

        if not wait:
            return self.check_health()

        return self._wait_for_healthy(progress_callback)

    def stop(self) -> HybridServerStatus:
        """Stop the running hybrid server."""
        if self._process is None:
            return HybridServerStatus(running=False, url=self.url, error="No process to stop")

        pid = self._process.pid
        try:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
            logger.info("Stopped opendataloader-pdf-hybrid (pid=%s)", pid)
        except Exception as e:
            logger.warning("Error stopping hybrid server: %s", e)
        finally:
            if self._log_file_handle is not None:
                self._log_file_handle.close()
                self._log_file_handle = None

        status = HybridServerStatus(running=False, url=self.url, pid=pid)
        self._process = None
        return status

    def _wait_for_healthy(
        self,
        progress_callback: Callable[[str], None] | None = None,
    ) -> HybridServerStatus:
        """Poll health endpoint until server is ready or timeout."""
        deadline = time.monotonic() + _STARTUP_MAX_WAIT
        start = time.monotonic()
        poll_interval = 1.0

        while time.monotonic() < deadline:
            status = self.check_health()
            if status.running:
                return status

            if self._process is not None and self._process.poll() is not None:
                # Process crashed during startup
                output = self._capture_output()
                detail = f" | Output: {output[:500]}" if output else ""
                return HybridServerStatus(
                    running=False,
                    url=self.url,
                    pid=self._process.pid,
                    error=f"Process exited during startup{detail}",
                )

            if progress_callback:
                elapsed = time.monotonic() - start
                remaining = deadline - time.monotonic()
                progress_callback(f"Waiting for hybrid server at {self.url}... ({elapsed:.0f}s elapsed, {remaining:.0f}s remaining)")

            time.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.5, 5.0)

        return HybridServerStatus(
            running=False,
            url=self.url,
            pid=self._process.pid if self._process else None,
            error=f"Server did not become healthy within {_STARTUP_MAX_WAIT}s",
        )

    def _capture_output(self) -> str:
        """Read recent output from the server log file."""
        if self._log_file_handle is None:
            return ""
        try:
            log_path = self.log_file
            text = log_path.read_text(encoding="utf-8", errors="replace")
            return text[-2000:] if len(text) > 2000 else text
        except OSError:
            return ""


class _GlobalManager:
    """Mutable container for the global HybridServerManager singleton."""

    instance: HybridServerManager | None = None


def get_manager() -> HybridServerManager:
    """Get the global hybrid server manager instance."""
    if _GlobalManager.instance is None:
        _GlobalManager.instance = HybridServerManager()
    return _GlobalManager.instance


def ensure_hybrid_server(
    config: HybridServerConfig | None = None,
    *,
    auto_start: bool = True,
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[HybridServerManager, HybridServerStatus]:
    """Ensure the hybrid server is running, starting it if necessary.

    Args:
        config: Optional server configuration.
        auto_start: If True, start the server if not already running.
        progress_callback: Optional callback for startup progress messages.

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
