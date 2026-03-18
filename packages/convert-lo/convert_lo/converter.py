"""LibreOffice conversion helpers."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from convert_lo.exceptions import ConversionError, UnsupportedConversionError
from convert_lo.formats import UNSUPPORTED_CONVERSIONS, LibreOfficeFormat
from convert_lo.locator import find_soffice
from convert_lo.server import ServerManager, is_server_running

try:
    from unoserver.client import UnoClient

    HAS_UNOSERVER = True
except ImportError:
    UnoClient = None  # type: ignore[assignment, misc]
    HAS_UNOSERVER = False

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ConversionResult:
    """Result of a LibreOffice conversion."""

    input_path: Path
    output_path: Path
    output_format: LibreOfficeFormat


class Converter:
    """Convert documents using LibreOffice.

    Supports two conversion modes:
    - **CLI mode**: Uses headless LibreOffice CLI (default, always available)
    - **Server mode**: Uses unoserver for faster batch conversions (requires running server)

    The converter automatically detects and uses a running unoserver when available,
    falling back to CLI mode otherwise.

    Example:
        ```python
        # Auto-detect server, fallback to CLI
        converter = Converter()
        result = converter.convert(input_file, "pdf", output_dir)

        # Force server mode (raises error if server unavailable)
        converter = Converter(server_mode="server")
        result = converter.convert(input_file, "pdf", output_dir)

        # Force CLI mode
        converter = Converter(server_mode="cli")
        result = converter.convert(input_file, "pdf", output_dir)
        ```
    """

    def __init__(
        self,
        soffice_path: Path | None = None,
        server_host: str = "127.0.0.1",
        server_port: int = 2003,
        server_mode: Literal["auto", "server", "cli"] = "auto",
        auto_start_server: bool = True,
    ) -> None:
        """Initialize the converter.

        Args:
            soffice_path: Path to soffice executable. If None, auto-detects.
            server_host: Host for unoserver connection (default: 127.0.0.1).
            server_port: Port for unoserver connection (default: 2003).
            server_mode: Conversion mode:
                - "auto": Use server if running, else CLI (default)
                - "server": Require server (raises error if unavailable)
                - "cli": Always use CLI mode
            auto_start_server: If True and server_mode is "auto" or "server",
                attempt to start unoserver if not running.

        Raises:
            ConversionError: If server mode is required but server unavailable.
        """
        self._soffice_path = soffice_path or find_soffice()
        self._server_host = server_host
        self._server_port = server_port
        self._server_mode = server_mode
        self._auto_start_server = auto_start_server
        self._server_manager: ServerManager | None = None
        self._client: object | None = None

        # Initialize client if server is available
        self._init_server_client()

    def _init_server_client(self) -> None:
        """Initialize unoserver client if server is available."""
        if not HAS_UNOSERVER:
            logger.debug("unoserver not installed, using CLI mode")
            return

        if self._server_mode == "cli":
            logger.debug("CLI mode forced, skipping server initialization")
            return

        # Check if server is running
        server_available = is_server_running(self._server_host, self._server_port)

        if not server_available and self._auto_start_server:
            try:
                self._server_manager = ServerManager(
                    host=self._server_host,
                    port=self._server_port,
                    soffice_path=self._soffice_path,
                )
                self._server_manager.start()
                server_available = True
                logger.info("Auto-started unoserver on %s:%d", self._server_host, self._server_port)
            except ConversionError as exc:
                logger.warning("Failed to auto-start server: %s", exc)
                if self._server_mode == "server":
                    raise

        if server_available:
            self._client = UnoClient(
                server=self._server_host,
                port=str(self._server_port),
                host_location="local",
            )
            logger.info("Using unoserver on %s:%d", self._server_host, self._server_port)
        elif self._server_mode == "server":
            msg = f"Unoserver required but not available at {self._server_host}:{self._server_port}"
            raise ConversionError(msg)
        else:
            logger.info("No server available, using CLI mode")

    @property
    def is_using_server(self) -> bool:
        """Check if converter is currently using unoserver."""
        return self._client is not None

    @property
    def server_mode(self) -> Literal["auto", "server", "cli"]:
        """Return the configured server mode."""
        return self._server_mode

    def convert(
        self,
        input_file: Path,
        output_format: LibreOfficeFormat | str,
        output_dir: Path,
    ) -> ConversionResult:
        """Convert a single document to the requested format.

        Args:
            input_file: Path to the input document.
            output_format: Desired output format.
            output_dir: Directory for converted file.

        Returns:
            ConversionResult with input/output paths.

        Raises:
            UnsupportedConversionError: When format validation fails.
            ConversionError: When the conversion command fails.
        """
        if not isinstance(output_format, (str, LibreOfficeFormat)):
            msg = f"Unsupported format: {output_format}"
            raise UnsupportedConversionError(msg)

        try:
            output_format = LibreOfficeFormat(output_format) if isinstance(output_format, str) else output_format
        except ValueError as exc:
            msg = f"Unsupported format: {output_format}"
            raise UnsupportedConversionError(msg) from exc

        if not input_file.exists():
            msg = f"Input file does not exist: {input_file}"
            raise ConversionError(msg)

        output_dir.mkdir(parents=True, exist_ok=True)

        input_suffix = input_file.suffix.lower().lstrip(".")
        if (input_suffix, output_format.value) in UNSUPPORTED_CONVERSIONS:
            msg = f"Unsupported conversion from {input_suffix} to {output_format.value}"
            raise UnsupportedConversionError(msg)

        try:
            logger.info("Converting %s to %s", input_file, output_format.value)
            if self._client is not None:
                self._convert_via_server(input_file, output_format.value, output_dir)
            else:
                self._run_conversion(input_file, output_format.value, output_dir)
        except subprocess.CalledProcessError as exc:
            msg = f"LibreOffice conversion failed for {input_file}: {exc.stderr or exc}"
            raise ConversionError(msg) from exc
        except Exception as exc:
            msg = f"LibreOffice conversion failed for {input_file}: {exc}"
            raise ConversionError(msg) from exc

        output_path = output_dir / f"{input_file.stem}.{output_format.value}"
        return ConversionResult(input_path=input_file, output_path=output_path, output_format=output_format)

    def _convert_via_server(self, input_file: Path, output_format: str, output_dir: Path) -> None:
        """Convert using unoserver.

        Args:
            input_file: Path to input file.
            output_format: Target format (e.g., 'pdf', 'docx').
            output_dir: Output directory.
        """
        if self._client is None:
            msg = "unoserver client not initialized"
            raise ConversionError(msg)

        output_path = output_dir / f"{input_file.stem}.{output_format}"

        try:
            self._client.convert(
                inpath=str(input_file),
                outpath=str(output_path),
                convert_to=output_format,
            )
        except Exception as exc:
            logger.warning("Server conversion failed, falling back to CLI: %s", exc)
            self._run_conversion(input_file, output_format, output_dir)

    def _run_conversion(self, input_file: Path, output_format: str, output_dir: Path) -> None:
        """Execute the LibreOffice conversion command.

        Args:
            input_file: Path to input file.
            output_format: Target format (e.g., 'pdf', 'docx').
            output_dir: Output directory.
        """
        cmd = [
            str(self._soffice_path),
            "--headless",
            "--convert-to",
            output_format,
            "--outdir",
            str(output_dir),
            str(input_file),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout per file
        )

        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)

    def convert_batch(
        self,
        input_files: Iterable[Path],
        output_format: LibreOfficeFormat,
        output_dir: Path,
    ) -> list[ConversionResult]:
        """Convert multiple documents sequentially.

        When using unoserver, this is significantly faster than CLI mode
        as LibreOffice stays loaded between conversions.

        Args:
            input_files: Iterable of input file paths.
            output_format: Desired output format.
            output_dir: Directory for converted files.

        Returns:
            List of ConversionResult items.
        """
        results: list[ConversionResult] = []
        for input_file in input_files:
            result = self.convert(input_file, output_format, output_dir)
            results.append(result)
        return results

    def __enter__(self) -> Converter:
        """Start server on context entry if auto_start_server is True."""
        if self._auto_start_server and self._server_manager is not None:
            self._server_manager.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop server on context exit if auto_start_server is True."""
        if self._auto_start_server and self._server_manager is not None:
            self._server_manager.stop()
