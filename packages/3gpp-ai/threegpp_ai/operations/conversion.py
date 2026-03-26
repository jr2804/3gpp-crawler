"""Generic document to PDF conversion operations.

This module provides generic PDF conversion functionality for Office documents,
supporting both local LibreOffice conversion and remote API fallback.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import requests
from convert_lo import LibreOfficeFormat
from convert_lo.converter import Converter
from tdoc_crawler.logging import get_logger

from threegpp_ai.models import ConversionError

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


def is_office_format(file_path: Path) -> bool:
    """Check if a file is an Office document that needs PDF conversion.

    Args:
        file_path: Path to the file to check.

    Returns:
        True if the file is an Office document format.
    """
    return file_path.suffix.lower() in OFFICE_FORMATS


def get_cached_pdf_path(file_path: Path) -> Path | None:
    """Get the path to a cached PDF conversion if it exists.

    The cached PDF is stored in a `.ai` subdirectory next to the original file.

    Args:
        file_path: Path to the original Office document.

    Returns:
        Path to cached PDF if it exists, None otherwise.
    """
    ai_dir = file_path.parent / ".ai"
    cached_pdf = ai_dir / f"{file_path.stem}.pdf"
    return cached_pdf if cached_pdf.exists() else None


def convert_to_pdf(
    file_path: Path,
    output_dir: Path | None = None,
    *,
    force: bool = False,
    config: ConverterConfig | None = None,
) -> Path:
    """Convert an Office document to PDF.

    This is the main entry point for PDF conversion. It handles:
    - Checking for cached conversions
    - Selecting the appropriate backend (LibreOffice or remote)
    - Fallback from local to remote on failure (when using AUTO backend)

    Args:
        file_path: Path to the Office document (DOCX, DOC, PPT, etc.)
        output_dir: Optional output directory for the PDF. If None, uses
            the `.ai` subdirectory next to the source file.
        force: If True, re-convert even if a cached PDF exists.
        config: Optional converter configuration. If None, uses defaults
            from environment variables.

    Returns:
        Path to the converted PDF file.

    Raises:
        ConversionError: If conversion fails with all available backends.
        FileNotFoundError: If the input file does not exist.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    if not is_office_format(file_path):
        raise ConversionError(f"Unsupported file format: {file_path.suffix}")

    config = config or ConverterConfig.from_env()
    output_dir = output_dir or file_path.parent / ".ai"
    output_path = output_dir / f"{file_path.stem}.pdf"

    # Check for cached conversion
    if not force and output_path.exists():
        logger.debug("Using cached PDF: %s", output_path)
        return output_path

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Select backend and convert
    if config.backend == ConverterBackend.REMOTE:
        return convert_via_remote(file_path, output_dir, config)

    if config.backend == ConverterBackend.LIBREOFFICE:
        return convert_via_libreoffice(file_path, output_dir)

    # AUTO: Try LibreOffice first, fallback to remote
    try:
        return convert_via_libreoffice(file_path, output_dir)
    except Exception as e:
        logger.warning("LibreOffice conversion failed for %s: %s", file_path.name, e)
        logger.info("Falling back to remote converter for %s", file_path.name)
        return convert_via_remote(file_path, output_dir, config)


def convert_via_libreoffice(
    file_path: Path,
    output_dir: Path,
) -> Path:
    """Convert an Office document to PDF using local LibreOffice.

    Uses the convert-lo package which wraps LibreOffice in headless mode.
    Requires LibreOffice to be installed and available on the system PATH.

    Args:
        file_path: Path to the Office document.
        output_dir: Output directory for the PDF.

    Returns:
        Path to the converted PDF file.

    Raises:
        ConversionError: If LibreOffice conversion fails.
    """
    output_path = output_dir / f"{file_path.stem}.pdf"

    try:
        converter = Converter()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = converter.convert(file_path, LibreOfficeFormat.PDF, Path(tmpdir))

            if result is None or result.output_path is None:
                raise ConversionError(f"LibreOffice returned empty result for {file_path.name}")

            # Copy the converted PDF to the output directory
            output_path.write_bytes(result.output_path.read_bytes())

        logger.info("Converted %s to PDF via LibreOffice: %s", file_path.name, output_path)
        return output_path

    except ConversionError:
        raise
    except Exception as e:
        msg = f"LibreOffice conversion failed for {file_path.name}: {e}"
        logger.error(msg)
        raise ConversionError(msg) from e


def convert_via_remote(
    file_path: Path,
    output_dir: Path,
    config: ConverterConfig | None = None,
) -> Path:
    """Convert an Office document to PDF via remote API.

    Uses a remote conversion service (e.g., pdf-convert.3gpp.org) as a fallback
    when local LibreOffice is not available or fails.

    Args:
        file_path: Path to the Office document.
        output_dir: Output directory for the PDF.
        config: Optional converter configuration with API credentials.
            If None, reads from environment variables.

    Returns:
        Path to the converted PDF file.

    Raises:
        ConversionError: If remote conversion fails.
    """
    config = config or ConverterConfig.from_env()
    output_path = output_dir / f"{file_path.stem}.pdf"

    # Prepare API request
    api_key = config.api_key or os.getenv("PDF_REMOTE_API_KEY")
    api_base = config.api_base or os.getenv("PDF_REMOTE_API_BASE", "https://pdf-convert.3gpp.org")

    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    url = f"{api_base.rstrip('/')}/convert"
    logger.debug("Converting %s via remote API: %s", file_path.name, url)

    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        with file_path.open("rb") as source_handle:
            files = {"file": (file_path.name, source_handle, "application/octet-stream")}
            with requests.post(url, files=files, headers=headers, stream=True, timeout=120) as response:
                response.raise_for_status()

                # Stream response to output file
                with output_path.open("wb") as output_handle:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            output_handle.write(chunk)

        logger.info("Converted %s to PDF via remote API: %s", file_path.name, output_path)
        return output_path

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        msg = f"Remote conversion failed for {file_path.name}: HTTP {status}"
        logger.error(msg)
        raise ConversionError(msg) from e
    except requests.exceptions.RequestException as e:
        msg = f"Remote conversion failed for {file_path.name}: {e}"
        logger.error(msg)
        raise ConversionError(msg) from e
    except OSError as e:
        msg = f"Remote conversion failed for {file_path.name}: {e}"
        logger.error(msg)
        raise ConversionError(msg) from e


__all__ = [
    "OFFICE_FORMATS",
    "ConversionError",
    "ConverterBackend",
    "ConverterConfig",
    "convert_to_pdf",
    "convert_via_libreoffice",
    "convert_via_remote",
    "get_cached_pdf_path",
    "is_office_format",
]
