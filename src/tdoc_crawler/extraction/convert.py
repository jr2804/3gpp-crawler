"""PDF conversion for 3GPP documents (LibreOffice with remote fallback).

Office documents (``.doc``, ``.docx``, ``.pptx``, …) are converted to PDF
via local LibreOffice; if that fails or is unavailable, an online provider
from ``pdf-remote-converter`` is used.  PDF is the preferred downstream
exchange format (e.g. for knowledge tooling) and rescues legacy ``.doc``
specifications.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pdf_remote_converter.converter
import pdf_remote_converter.router
from convert_lo import LibreOfficeFormat
from convert_lo.converter import Converter
from pdf_remote_converter.config import ProviderSettings

from tdoc_crawler.extraction.errors import ConversionError

# File formats that need PDF conversion.
OFFICE_FORMATS: frozenset[str] = frozenset(
    {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".rtf", ".odt", ".odp", ".ods"},
)

logger = logging.getLogger(__name__)


class ConverterBackend(Enum):
    """PDF conversion backends."""

    LIBREOFFICE = "libreoffice"
    AUTO = "auto"


@dataclass
class ConverterConfig:
    """PDF converter configuration."""

    backend: ConverterBackend = ConverterBackend.AUTO

    @classmethod
    def from_env(cls) -> ConverterConfig:
        """Build converter config from environment variables."""
        return cls()


def ensure_pdf(
    source_file: Path,
    output_dir: Path,
    *,
    force: bool = False,
    config: ConverterConfig | None = None,
    output_stem: str | None = None,
    remote_fallback: bool = True,
) -> Path:
    """Ensure a PDF version of *source_file* exists in *output_dir*.

    For office documents, converts via LibreOffice (or remote fallback).
    For native PDFs, copies.  Uses cached conversion when available.
    """
    stem = output_stem or source_file.stem
    pdf_path = output_dir / f"{stem}.pdf"

    if pdf_path.exists() and not force:
        return pdf_path

    if is_office_format(source_file):
        return convert_to_pdf(source_file, output_dir, force=force, config=config, output_stem=stem, remote_fallback=remote_fallback)

    # Native PDF — copy to output.
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_file, pdf_path)
    return pdf_path


def convert_to_pdf(
    source_file: Path,
    output_dir: Path,
    *,
    force: bool = False,
    config: ConverterConfig | None = None,
    output_stem: str | None = None,
    remote_fallback: bool = True,
) -> Path:
    """Convert an Office document to PDF.

    Selects the appropriate backend and falls back from local to remote
    when using ``AUTO`` and ``remote_fallback`` is enabled.

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
    stem = output_stem or source_file.stem
    output_file = output_dir / f"{stem}.pdf"

    if not force and output_file.exists():
        logger.debug("Using cached PDF: %s", output_file)
        return output_file

    output_dir.mkdir(parents=True, exist_ok=True)

    if config.backend == ConverterBackend.LIBREOFFICE:
        return _convert_via_libreoffice(source_file, output_dir, output_stem=stem)

    # AUTO: try LibreOffice, optionally fall back to remote converter.
    try:
        return _convert_via_libreoffice(source_file, output_dir, output_stem=stem)
    except ConversionError:
        if not remote_fallback or not _is_remote_converter_available():
            raise
        logger.warning(
            "LibreOffice conversion failed for %s, falling back to remote converter",
            source_file.name,
        )
        return _convert_via_remote(source_file, output_file)


def is_office_format(source_file: Path) -> bool:
    """Check if a file is an Office document that needs PDF conversion."""
    return source_file.suffix.lower() in OFFICE_FORMATS


def _is_remote_converter_available() -> bool:
    """Check if pdf-remote-converter has at least one provider configured."""
    return bool(pdf_remote_converter.router.get_configured_providers(ProviderSettings()))


def _convert_via_remote(source_file: Path, output_file: Path) -> Path:
    """Convert Office document to PDF via pdf-remote-converter (online fallback)."""
    converter = pdf_remote_converter.converter.Converter()
    result = converter.convert(source_file, output_file)
    logger.info(
        "Converted %s to PDF via %s (remote fallback)",
        source_file.name,
        result.provider,
    )
    return output_file


def _convert_via_libreoffice(source_file: Path, output_dir: Path, *, output_stem: str | None = None) -> Path:
    """Convert Office document to PDF via local LibreOffice (headless mode)."""
    stem = output_stem or source_file.stem
    output_file = output_dir / f"{stem}.pdf"

    try:
        converter = Converter()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = converter.convert(source_file, LibreOfficeFormat.PDF, Path(tmpdir))
            if result is None or result.output_file is None:
                msg = f"LibreOffice returned empty result for {source_file.name}"
                raise ConversionError(msg)
            output_file.write_bytes(result.output_file.read_bytes())

        logger.info("Converted %s to PDF via LibreOffice: %s", source_file.name, output_file)
        return output_file

    except ConversionError:
        raise
    except Exception as e:
        msg = f"LibreOffice conversion failed for {source_file.name}: {e}"
        logger.warning(msg)
        raise ConversionError(msg) from e
