"""LibreOffice conversion helpers."""

from __future__ import annotations

import logging
import subprocess
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
    """Convert documents using LibreOffice.

    Note: LibreOffice conversion is NOT thread-safe. All conversions
    are processed sequentially to avoid silent failures.
    """

    def __init__(self, soffice_path: Path | None = None, max_workers: int = 1) -> None:
        """Initialize the converter.

        Args:
            soffice_path: Path to soffice executable. If None, auto-detects.
            max_workers: Ignored (kept for API compatibility). Conversions are
                always sequential due to LibreOffice thread-safety limitations.
        """
        self._soffice_path = soffice_path or find_soffice()
        # max_workers is ignored - LibreOffice is not thread-safe

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
        return ConversionResult(input_path=input_file, output_path=output_path, output_format=output_format)

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

        Note: Conversions are processed sequentially because LibreOffice
        is not thread-safe and will silently fail with concurrent processes.

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
