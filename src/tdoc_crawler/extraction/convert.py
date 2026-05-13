"""Document conversion orchestrator — PDF generation + structured extraction.

After checkout/fetch, all source types (TDocs, Specs, Other) are treated as
generic documents.  Four extraction profiles are supported:

- **pdf-only**:  Convert to PDF only (via LibreOffice).  No structured extraction.
- **markdown-only**:  Fast markitdown extraction (.md only, no ML).
- **default**:   PDF → Docling structured output (Markdown + JSON).
- **advanced**:  Same as default + picture descriptions, code/formula enrichment.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import niquests as requests
from convert_lo import LibreOfficeFormat
from convert_lo.converter import Converter

from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.extraction.docling import (
    DoclingConfig,
    _run_docling,
)
from tdoc_crawler.extraction.errors import ConversionError
from tdoc_crawler.extraction.fetch_tdoc import fetch_spec_files as fetch_spec_files_from_tdoc
from tdoc_crawler.extraction.fetch_tdoc import fetch_tdoc_files
from tdoc_crawler.extraction.markitdown import _run_markitdown
from tdoc_crawler.extraction.metrics import MetricType, get_metrics_tracker, timed_operation
from tdoc_crawler.extraction.profiles import DEFAULT_EXTRACTION_PROFILE, ExtractionProfile
from tdoc_crawler.models.workspaces import SourceKind
from tdoc_crawler.utils.async_helpers import run_async
from tdoc_crawler.utils.normalization import normalize_tdoc_id
from tdoc_crawler.utils.security import validate_api_url
from tdoc_crawler.workspaces import checkout_spec_to_workspace

logger = logging.getLogger(__name__)

# File suffixes that can be fed directly to backends (no LibreOffice PDF step).
_DOCX_SUFFIXES: frozenset[str] = frozenset({".docx"})


# ---------------------------------------------------------------------------
# PDF conversion (LibreOffice / remote API)
# ---------------------------------------------------------------------------

# File formats that need PDF conversion.
OFFICE_FORMATS: frozenset[str] = frozenset(
    {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".rtf", ".odt", ".odp", ".ods"},
)


class ConverterBackend(Enum):
    """PDF conversion backends."""

    LIBREOFFICE = "libreoffice"
    REMOTE = "remote"
    AUTO = "auto"


@dataclass
class ConverterConfig:
    """PDF converter configuration."""

    backend: ConverterBackend = ConverterBackend.AUTO
    api_key: str | None = None
    api_base: str = "https://pdf-convert.3gpp.org"

    @classmethod
    def from_env(cls) -> ConverterConfig:
        """Build converter config from environment variables.

        Supported variables:
        - ``PDF_REMOTE_API_KEY``: API key for remote converter
        - ``PDF_REMOTE_API_BASE``: Base URL for remote converter API
        """
        return cls(
            api_key=os.getenv("PDF_REMOTE_API_KEY"),
            api_base=os.getenv("PDF_REMOTE_API_BASE", "https://pdf-convert.3gpp.org"),
        )


def is_office_format(source_file: Path) -> bool:
    """Check if a file is an Office document that needs PDF conversion."""
    return source_file.suffix.lower() in OFFICE_FORMATS


def ensure_pdf(
    source_file: Path,
    output_dir: Path,
    *,
    force: bool = False,
    config: ConverterConfig | None = None,
) -> Path:
    """Ensure a PDF version of *source_file* exists in *output_dir*.

    For office documents, converts via LibreOffice (or remote fallback).
    For native PDFs, copies.  Uses cached conversion when available.
    """
    pdf_path = output_dir / f"{source_file.stem}.pdf"

    if pdf_path.exists() and not force:
        return pdf_path

    if is_office_format(source_file):
        return convert_to_pdf(source_file, output_dir, force=force, config=config)

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
) -> Path:
    """Convert an Office document to PDF.

    Selects the appropriate backend and falls back from local to remote
    when using ``AUTO``.

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

    if not force and output_file.exists():
        logger.debug("Using cached PDF: %s", output_file)
        return output_file

    output_dir.mkdir(parents=True, exist_ok=True)

    if config.backend == ConverterBackend.REMOTE:
        return _convert_via_remote(source_file, output_dir, config)
    if config.backend == ConverterBackend.LIBREOFFICE:
        return _convert_via_libreoffice(source_file, output_dir)

    # AUTO: try local, fall back to remote.
    try:
        return _convert_via_libreoffice(source_file, output_dir)
    except ConversionError as e:
        logger.warning("LibreOffice conversion failed for %s: %s", source_file.name, e)
        logger.info("Falling back to remote converter for %s", source_file.name)
        return _convert_via_remote(source_file, output_dir, config)


def _convert_via_libreoffice(source_file: Path, output_dir: Path) -> Path:
    """Convert Office document to PDF via local LibreOffice (headless mode)."""
    output_file = output_dir / f"{source_file.stem}.pdf"

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
        logger.exception(msg)
        raise ConversionError(msg) from e


def _convert_via_remote(
    source_file: Path,
    output_dir: Path,
    config: ConverterConfig | None = None,
) -> Path:
    """Convert Office document to PDF via remote API (fallback)."""
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


# ---------------------------------------------------------------------------
# Source file resolution (source-kind-specific, before generic conversion)
# ---------------------------------------------------------------------------


def _resolve_source_files(
    document_id: str,
    *,
    source_kind: SourceKind = SourceKind.TDOC,
    source_path: str | Path | None = None,
    force: bool = False,
) -> Path:
    """Resolve source document files and return the primary path.

    Raises:
        ConversionError: If no document files can be found.
    """
    if source_kind == SourceKind.SPEC:
        spec_rel_match = re.match(r"^(\d+(?:\.\d+)?)(?:-REL(.+))?$", document_id)
        spec_number = spec_rel_match.group(1) if spec_rel_match else document_id
        spec_release = spec_rel_match.group(2) if spec_rel_match and spec_rel_match.group(2) else "latest"

        actual_path: Path | None = None
        if source_path and Path(str(source_path)).exists():
            actual_path = Path(str(source_path))
        else:
            checkout_base = PathConfig().checkout_dir
            actual_path = run_async(
                checkout_spec_to_workspace(spec_number, checkout_base, release=spec_release),
            )

        if actual_path is None:
            msg = f"Spec {document_id} could not be checked out or found on disk"
            raise ConversionError(msg)

        doc_files = fetch_spec_files_from_tdoc(actual_path)
    else:
        normalized_id = normalize_tdoc_id(document_id)
        doc_files = fetch_tdoc_files(normalized_id, force_download=force)

    primary = doc_files.primary_path
    if primary is None:
        msg = f"No document files found for {document_id}"
        raise ConversionError(msg)

    return primary


# ---------------------------------------------------------------------------
# Public conversion entry point
# ---------------------------------------------------------------------------


def convert_for_wiki(
    document_id: str,
    wiki_source_dir: Path,
    *,
    source_kind: SourceKind = SourceKind.TDOC,
    source_path: str | Path | None = None,
    profile: ExtractionProfile | None = None,
    force: bool = False,
    docling_config: DoclingConfig | None = None,
    docx_direct: bool = False,
    extract_media: bool = False,
) -> Path | None:
    """Convert a document for wiki ingestion using the specified profile.

    For **markdown-only** the pipeline is:
    1. Convert legacy ``.doc`` files to PDF (via LibreOffice) — they are binary
       format and cannot be processed directly by markitdown.
    2. Feed ``.docx`` or PDF to markitdown — no ML, no JSON.
    3. Write ``.md`` to *wiki_source_dir*.

    For **default** and **advanced** profiles the pipeline is:
    1. Convert to PDF (via LibreOffice) if not already PDF, unless docx_direct.
    2. Feed to Docling for structured extraction.
    3. Write Markdown + JSON to *wiki_source_dir*.

    Args:
        document_id: Document identifier (TDoc ID, spec number, etc.).
        wiki_source_dir: Target directory under ``wiki/<workspace>/sources/<doc-id>/``.
        source_kind: Kind of source (TDOC, SPEC, OTHER).
        source_path: Optional explicit path to the source document/directory.
        profile: Extraction profile. Defaults to ``DEFAULT_EXTRACTION_PROFILE``.
        force: Force reconversion.
        docling_config: Optional Docling-specific configuration (figure/table modes).
        docx_direct: Feed .docx directly to backend, skip LibreOffice PDF step.
        extract_media: Extract embedded images to ``./media/`` next to the
            markdown (markdown-only profile, .docx only).

    Returns:
        Path to the primary output file (PDF for pdf-only, MD for others),
        or ``None`` if conversion fails.
    """
    if profile is None:
        profile = DEFAULT_EXTRACTION_PROFILE

    wiki_source_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Resolve source files (source-kind-specific)
    primary = _resolve_source_files(
        document_id,
        source_kind=source_kind,
        source_path=source_path,
        force=force,
    )

    # Step 2a: pdf-only → just ensure PDF
    if profile == ExtractionProfile.PDF_ONLY:
        return ensure_pdf(primary, wiki_source_dir, force=force)

    # Step 2b: markdown-only → fast markitdown, .md only
    if profile == ExtractionProfile.MARKDOWN_ONLY:
        md_file = wiki_source_dir / f"{primary.stem}.md"
        if not force and md_file.exists():
            logger.debug("Skipping %s — markdown already exists", document_id)
            return md_file
        # Legacy .doc files (binary format) cannot be processed directly;
        # convert to PDF first, then run markitdown on the PDF.
        input_for_markitdown = primary
        if primary.suffix.lower() == ".doc":
            input_for_markitdown = ensure_pdf(primary, wiki_source_dir, force=force)
        with timed_operation(get_metrics_tracker(), document_id, MetricType.CONVERSION):
            return _run_markitdown(input_for_markitdown, wiki_source_dir, extract_media=extract_media)

    # Step 2c: default/advanced → check existing output before running Docling
    md_file = wiki_source_dir / f"{primary.stem}.md"
    json_file = wiki_source_dir / f"{primary.stem}.json"
    if not force and md_file.exists() and json_file.exists():
        logger.debug("Skipping %s — output already exists", document_id)
        return md_file

    # Step 2d: ensure PDF first (unless docx-direct), then Docling
    is_docx_direct = docx_direct and primary.suffix.lower() in _DOCX_SUFFIXES
    input_for_docling = primary if is_docx_direct else ensure_pdf(primary, wiki_source_dir, force=force)

    with timed_operation(get_metrics_tracker(), document_id, MetricType.CONVERSION):
        _, _, _ = _run_docling(
            input_for_docling,
            wiki_source_dir,
            profile=profile,
            config=docling_config,
            docx_direct=is_docx_direct,
        )

    return md_file


__all__ = [
    "OFFICE_FORMATS",
    "ConversionError",
    "ConverterBackend",
    "ConverterConfig",
    "DoclingConfig",
    "convert_for_wiki",
    "convert_to_pdf",
    "ensure_pdf",
    "is_office_format",
]
