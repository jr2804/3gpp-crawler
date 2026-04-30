"""Generic document to PDF conversion operations.

This module provides generic PDF conversion functionality for Office documents,
supporting both local LibreOffice conversion and remote API fallback.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import niquests as requests
from convert_lo import LibreOfficeFormat
from convert_lo.converter import Converter

from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.workspaces import ConversionError
from tdoc_crawler.utils.security import validate_api_url

logger = get_logger(__name__)

# File formats that need PDF conversion
OFFICE_FORMATS: frozenset[str] = frozenset({".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".rtf", ".odt", ".odp", ".ods"})


class ConverterBackend(Enum):
    """PDF conversion backends."""

    LIBREOFFICE = "libreoffice"  # Local LibreOffice (default)
    REMOTE = "remote"  # pdf-remote-converter API
    AUTO = "auto"  # Try local, fallback to remote


@dataclass
class ConverterConfig:
    """PDF converter configuration."""

    backend: ConverterBackend = ConverterBackend.AUTO
    api_key: str | None = None  # For remote backend
    api_base: str = "https://pdf-convert.3gpp.org"  # Default API endpoint

    @classmethod
    def from_env(cls) -> ConverterConfig:
        """Build converter config from environment variables.

        Supported variables:
        - PDF_REMOTE_API_KEY: API key for remote converter
        - PDF_REMOTE_API_BASE: Base URL for remote converter API
        """
        return cls(
            api_key=os.getenv("PDF_REMOTE_API_KEY"),
            api_base=os.getenv("PDF_REMOTE_API_BASE", "https://pdf-convert.3gpp.org"),
        )


def is_office_format(source_file: Path) -> bool:
    """Check if a file is an Office document that needs PDF conversion.

    Args:
        source_file: Path to the file to check.

    Returns:
        True if the file is an Office document format.
    """
    return source_file.suffix.lower() in OFFICE_FORMATS


def convert_to_pdf(
    source_file: Path,
    output_dir: Path,
    *,
    force: bool = False,
    config: ConverterConfig | None = None,
) -> Path:
    """Convert an Office document to PDF.

    This is the main entry point for PDF conversion. It handles:
    - Selecting the appropriate backend (LibreOffice or remote)
    - Fallback from local to remote on failure (when using AUTO backend)

    Args:
        source_file: Path to the Office document (DOCX, DOC, PPT, etc.)
        output_dir: Output directory for the PDF.
        force: If True, re-convert even if a cached PDF exists.
        config: Optional converter configuration. If None, uses defaults
            from environment variables.

    Returns:
        Path to the converted PDF file.

    Raises:
        ConversionError: If conversion fails with all available backends.
        FileNotFoundError: If the input file does not exist.
    """
    if not source_file.exists():
        msg = f"Input file not found: {source_file}"
        raise FileNotFoundError(msg)

    if not is_office_format(source_file):
        msg = f"Unsupported file format: {source_file.suffix}"
        raise ConversionError(msg)

    config = config or ConverterConfig.from_env()
    output_file = output_dir / f"{source_file.stem}.pdf"

    # Check for cached conversion
    if not force and output_file.exists():
        logger.debug("Using cached PDF: %s", output_file)
        return output_file

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Select backend and convert
    if config.backend == ConverterBackend.REMOTE:
        return convert_via_remote(source_file, output_dir, config)

    if config.backend == ConverterBackend.LIBREOFFICE:
        return convert_via_libreoffice(source_file, output_dir)

    # AUTO: Try LibreOffice first, fallback to remote
    try:
        return convert_via_libreoffice(source_file, output_dir)
    except ConversionError as e:
        logger.warning("LibreOffice conversion failed for %s: %s", source_file.name, e)
        logger.info("Falling back to remote converter for %s", source_file.name)
        return convert_via_remote(source_file, output_dir, config)


def ensure_pdf(
    source_file: Path,
    output_dir: Path,
    *,
    force: bool = False,
    config: ConverterConfig | None = None,
) -> Path:
    """Ensure a PDF version of the source file exists in output_dir.

    For office documents, converts via LibreOffice. For native PDFs, copies.
    Uses cached conversion when available.

    Args:
        source_file: Path to source document.
        output_dir: Directory to place the PDF.
        force: Force reconversion.
        config: Optional converter configuration.

    Returns:
        Path to the PDF file.
    """
    pdf_path = output_dir / f"{source_file.stem}.pdf"

    if pdf_path.exists() and not force:
        return pdf_path

    if is_office_format(source_file):
        return convert_to_pdf(source_file, output_dir, force=force, config=config)

    # Native PDF - copy to output
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_file, pdf_path)
    return pdf_path


def convert_via_libreoffice(
    source_file: Path,
    output_dir: Path,
) -> Path:
    """Convert an Office document to PDF using local LibreOffice.

    Uses the convert-lo package which wraps LibreOffice in headless mode.
    Requires LibreOffice to be installed and available on the system PATH.

    Args:
        source_file: Path to the Office document.
        output_dir: Output directory for the PDF.

    Returns:
        Path to the converted PDF file.

    Raises:
        ConversionError: If LibreOffice conversion fails.
    """
    output_file = output_dir / f"{source_file.stem}.pdf"

    try:
        converter = Converter()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = converter.convert(source_file, LibreOfficeFormat.PDF, Path(tmpdir))

            if result is None or result.output_file is None:
                msg = f"LibreOffice returned empty result for {source_file.name}"
                raise ConversionError(msg)

            # Copy the converted PDF to the output directory
            output_file.write_bytes(result.output_file.read_bytes())

        logger.info("Converted %s to PDF via LibreOffice: %s", source_file.name, output_file)
        return output_file

    except ConversionError:
        raise
    except Exception as e:
        msg = f"LibreOffice conversion failed for {source_file.name}: {e}"
        logger.exception(msg)
        raise ConversionError(msg) from e


def convert_via_remote(
    source_file: Path,
    output_dir: Path,
    config: ConverterConfig | None = None,
) -> Path:
    """Convert an Office document to PDF via remote API.

    Uses a remote conversion service (e.g., pdf-convert.3gpp.org) as a fallback
    when local LibreOffice is not available or fails.
    """
    config = config or ConverterConfig.from_env()
    validate_api_url(config.api_base)
    output_file = output_dir / f"{source_file.stem}.pdf"

    try:
        with source_file.open("rb") as f:
            files = {"file": (source_file.name, f, "application/octet-stream")}
            headers: dict[str, str] = {}
            if config.api_key:
                headers["X-API-Key"] = config.api_key

            response = requests.post(
                f"{config.api_base}/convert",
                files=files,
                headers=headers,
                timeout=300,
            )
            response.raise_for_status()

            output_file.write_bytes(response.content)

        logger.info("Converted %s to PDF via remote API: %s", source_file.name, output_file)
        return output_file

    except requests.RequestException as e:
        msg = f"Remote conversion failed for {source_file.name}: {e}"
        logger.exception(msg)
        raise ConversionError(msg) from e


__all__ = [
    "OFFICE_FORMATS",
    "ConverterBackend",
    "ConverterConfig",
    "convert_to_pdf",
    "convert_via_libreoffice",
    "convert_via_remote",
    "is_office_format",
]
