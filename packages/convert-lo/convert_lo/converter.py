"""LibreOffice conversion helpers."""

from __future__ import annotations

import logging
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from convert_lo.exceptions import ConversionError, UnsupportedConversionError
from convert_lo.formats import UNSUPPORTED_CONVERSIONS, LibreOfficeFormat
from convert_lo.locator import find_soffice

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ConversionResult:
    """Result of a LibreOffice conversion."""

    input_path: Path
    output_path: Path
    output_format: LibreOfficeFormat


class Converter:
    """Convert documents using LibreOffice CLI.

    Uses headless LibreOffice CLI for reliable, cross-platform conversion.
    This is the most straightforward and reliable method.

    Example:
        ```python
        converter = Converter()
        result = converter.convert(input_file, "pdf", output_dir)
        ```
    """

    def __init__(
        self,
        soffice_path: Path | None = None,
        timeout: int = 300,
    ) -> None:
        """Initialize the converter.

        Args:
            soffice_path: Path to soffice executable. If None, auto-detects.
            timeout: Timeout in seconds per file conversion (default: 300).
        """
        self._soffice_path = soffice_path or find_soffice()
        self._timeout = timeout

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
            self._run_conversion(input_file, output_format.value, output_dir)
        except subprocess.CalledProcessError as exc:
            msg = f"LibreOffice conversion failed for {input_file}: {exc.stderr or exc}"
            raise ConversionError(msg) from exc
        except Exception as exc:
            msg = f"LibreOffice conversion failed for {input_file}: {exc}"
            raise ConversionError(msg) from exc

        output_path = output_dir / f"{input_file.stem}.{output_format.value}"
        return ConversionResult(
            input_path=input_file,
            output_path=output_path,
            output_format=output_format,
        )

    def _run_conversion(self, input_file: Path, output_format: str, output_dir: Path) -> None:
        """Execute the LibreOffice conversion command.

        Args:
            input_file: Path to input file (must exist and be absolute).
            output_format: Target format (e.g., 'pdf', 'docx').
            output_dir: Output directory (must exist and be absolute).
        """
        # Ensure absolute paths for security - validate before passing to subprocess
        input_file = input_file.resolve()
        output_dir = output_dir.resolve()

        if not input_file.is_file():
            msg = f"Input file is not a valid file: {input_file}"
            raise ConversionError(msg)
        if not output_dir.is_dir():
            msg = f"Output directory is not valid: {output_dir}"
            raise ConversionError(msg)

        cmd: list[str] = [
            str(self._soffice_path),
            "--headless",
            "--invisible",
            "--nologo",
            "--nodefault",
            "--norestore",
            "--nofirststartwizard",
            "--convert-to",
            output_format,
            "--outdir",
            str(output_dir),
            str(input_file),
        ]

        startupinfo: subprocess.STARTUPINFO | None = None
        creationflags = 0
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        result = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=self._timeout,
            check=False,
            creationflags=creationflags,
            startupinfo=startupinfo,
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
