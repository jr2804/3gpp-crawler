"""TDoc to Markdown conversion operations."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import requests
from convert_lo import LibreOfficeFormat
from convert_lo.converter import Converter
from kreuzberg import extract_file_sync

from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.database.meetings import MeetingDatabase
from tdoc_crawler.logging import get_logger
from tdoc_crawler.tdocs.models import TDocMetadata
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec
from threegpp_ai.models import (
    ConversionError,
    ExtractedEquationElement,
    ExtractedFigureElement,
    ExtractedTableElement,
    ExtractionError,
)
from threegpp_ai.operations.extraction_result import (
    StructuredExtractionResult,
    build_structured_extraction_result,
    from_kreuzberg_result,
    persist_equations_from_extraction,
    persist_figures_from_extraction,
    persist_figures_from_kreuzberg_result,
    persist_tables_from_extraction,
    read_cached_artifacts,
)
from threegpp_ai.operations.fetch_tdoc import fetch_tdoc_files
from threegpp_ai.operations.figure_descriptor import describe_figures
from threegpp_ai.operations.metrics import MetricType, get_metrics_tracker, timed_operation

logger = get_logger(__name__)


class ConverterBackend(Enum):
    """PDF conversion backends."""

    LIBREOFFICE = "libreoffice"  # Local LibreOffice (current)
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
        - PDF_REMOTE_API_KEY
        - PDF_REMOTE_API_BASE
        """
        return cls(
            api_key=os.getenv("PDF_REMOTE_API_KEY"),
            api_base=os.getenv("PDF_REMOTE_API_BASE", "https://pdf-convert.3gpp.org"),
        )


def _get_meeting_info(meeting_id: int) -> str | None:
    """Get meeting short name from database.

    Args:
        meeting_id: Meeting identifier.

    Returns:
        Meeting short name if found, None otherwise.
    """
    try:
        manager = resolve_cache_manager()
        with MeetingDatabase(manager.db_file) as db:
            meetings = db._table_rows("meetings")
            for meeting in meetings:
                if meeting.meeting_id == meeting_id:
                    return meeting.short_name
    except Exception as exc:
        logger.debug(f"Failed to get meeting info for {meeting_id}: {exc}")
    return None


def _format_markdown(metadata: TDocMetadata) -> str:
    """Format TDoc metadata as markdown.

    Args:
        metadata: TDoc metadata to format.

    Returns:
        Markdown formatted string.
    """
    lines: list[str] = []

    # Title
    lines.append(f"# {metadata.title}\n")

    # TDoc ID
    lines.append(f"**TDoc ID:** {metadata.document_id}\n")

    # Meeting info
    meeting_name = _get_meeting_info(metadata.meeting_id)
    if meeting_name:
        lines.append(f"**Meeting:** {meeting_name}\n")
    else:
        lines.append(f"**Meeting ID:** {metadata.meeting_id}\n")

    # Source
    if metadata.source:
        lines.append(f"**Source:** {metadata.source}\n")

    # Contact
    if metadata.contact:
        lines.append(f"**Contact:** {metadata.contact}\n")

    # Document type
    lines.append(f"**Type:** {metadata.tdoc_type}\n")

    # Purpose
    lines.append(f"**For:** {metadata.for_purpose}\n")

    # Agenda item
    if metadata.agenda_item_text:
        lines.append(f"**Agenda Item:** {metadata.agenda_item_text}\n")

    # Status
    if metadata.status:
        lines.append(f"**Status:** {metadata.status}\n")

    # URL
    if metadata.url:
        lines.append(f"\n**URL:** {metadata.url}\n")

    return "".join(lines)


def convert_tdoc(
    document_id: str,
    output_path: Path | None = None,
) -> str:
    """Convert a TDoc to markdown format.

    Fetches TDoc metadata from WhatTheSpec and converts it to a markdown
    representation containing title, meeting info, source, and description.

    Args:
        document_id: Document identifier (e.g., "S4-260001").
        output_path: Optional path to write markdown file. If None, returns
            the markdown string.

    Returns:
        Markdown formatted string if output_path is None, otherwise returns
        the output path.

    Raises:
        ValueError: If TDoc cannot be found via WhatTheSpec.
    """
    # Normalize TDoc ID
    normalized_id = document_id.strip().upper()

    # Fetch metadata from WhatTheSpec
    logger.info(f"Fetching TDoc metadata for {normalized_id} via WhatTheSpec")
    metadata = resolve_via_whatthespec(normalized_id)

    if metadata is None:
        msg = f"TDoc {normalized_id} not found via WhatTheSpec"
        raise ValueError(msg)

    # Convert to markdown
    markdown_content = _format_markdown(metadata)

    # Write to file or return string
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown_content, encoding="utf-8")
        logger.info(f"Wrote markdown to {output_path}")
        return str(output_path)

    return markdown_content


def _convert_via_remote(
    input_path: Path,
    output_dir: Path,
    config: ConverterConfig,
) -> Path:
    """Convert document to PDF via remote API.

    Args:
        input_path: Source document path (DOCX, DOC, etc.)
        output_dir: Output directory for PDF
        config: Converter configuration with api_base and optional api_key

    Returns:
        Path to converted PDF

    Raises:
        ConversionError: If remote conversion fails
    """
    output_path = output_dir / f"{input_path.stem}.pdf"

    # Prepare multipart form upload
    api_key = config.api_key or os.getenv("PDF_REMOTE_API_KEY")
    api_base = config.api_base or os.getenv("PDF_REMOTE_API_BASE", "https://pdf-convert.3gpp.org")
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    url = f"{api_base.rstrip('/')}/convert"
    logger.debug(f"Converting {input_path.name} via remote API: {url}")

    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        with input_path.open("rb") as source_handle:
            files = {"file": (input_path.name, source_handle, "application/octet-stream")}
            with requests.post(url, files=files, headers=headers, stream=True, timeout=120) as response:
                response.raise_for_status()

                # Stream response to output file
                with output_path.open("wb") as output_handle:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            output_handle.write(chunk)

        logger.info(f"Remote conversion complete: {output_path}")
        return output_path

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        msg = f"Remote conversion failed for {input_path.name}: HTTP {status}"
        logger.error(msg)
        raise ConversionError(msg) from e
    except requests.exceptions.RequestException as e:
        msg = f"Remote conversion failed for {input_path.name}: {e}"
        logger.error(msg)
        raise ConversionError(msg) from e
    except OSError as e:
        msg = f"Remote conversion failed for {input_path.name}: {e}"
        logger.error(msg)
        raise ConversionError(msg) from e


def convert_tdoc_to_markdown(
    document_id: str,
    output_path: Path | None = None,
    force: bool = False,
    converter_config: ConverterConfig | None = None,
) -> str:
    """Convert TDoc to markdown using full pipeline.

    Pipeline:
    1. Fetch TDoc files (DOCX, DOC, or PDF)
    2. Convert to PDF if needed (via convert-lo / LibreOffice or remote API)
    3. Extract text using kreuzberg
    4. Return markdown content

    Caching:
    - Checks for existing .md file in .ai subdirectory
    - Only re-converts if force=True or cache miss

    Args:
        document_id: TDoc identifier (e.g., "S4-260001")
        output_path: Optional path to write markdown file
        force: Force reconversion even if cached
        converter_config: Optional converter configuration for backend selection

    Returns:
        Markdown content string

    Raises:
        TDocNotFoundError: If TDoc cannot be found
        ExtractionError: If no document files found
        ConversionError: If conversion fails (both LibreOffice and remote)
    """
    extraction = extract_tdoc_structured(
        document_id=document_id,
        force=force,
        converter_config=converter_config,
    )
    markdown = extraction.content

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        return str(output_path)

    return markdown


def extract_tdoc_structured(
    document_id: str,
    force: bool = False,
    converter_config: ConverterConfig | None = None,
    extract_types: set[str] | None = None,
) -> StructuredExtractionResult:
    """Extract a TDoc into the canonical structured payload.

    Args:
        document_id: TDoc identifier (e.g., "S4-260001").
        force: Force reconversion even if cached markdown exists.
        converter_config: Optional converter backend configuration.
        extract_types: Optional set of artifact types to extract/persist.
            If None, extracts all types. Supported types: "tables", "figures", "equations".

    Returns:
        Structured extraction result.

    Raises:
        ExtractionError: If no source file is available for the TDoc.
        ConversionError: If conversion/extraction fails.
    """
    normalized_id = document_id.strip().upper()
    config = converter_config or ConverterConfig.from_env()
    # Default to all types if not specified
    if extract_types is None:
        extract_types = {"tables", "figures", "equations"}

    with timed_operation(get_metrics_tracker(), normalized_id, MetricType.CONVERSION):
        tdoc_files = fetch_tdoc_files(normalized_id, force_download=force)

        primary = tdoc_files.primary_path
        if primary is None:
            raise ExtractionError(f"No document files found for {normalized_id}")

        ai_dir = tdoc_files.checkout_dir / ".ai"
        md_path = ai_dir / f"{normalized_id}.md"

        # Check for cached extraction: markdown + folder-based artifacts
        if md_path.exists() and not force:
            cached_content = md_path.read_text(encoding="utf-8")
            if len(cached_content) > 100:
                # Try new folder-based artifacts first
                cached = read_cached_artifacts(ai_dir, normalized_id)
                if cached is not None:
                    # Filter artifacts based on extract_types
                    tables = cached.tables if "tables" in extract_types else []
                    figures = cached.figures if "figures" in extract_types else []
                    equations = cached.equations if "equations" in extract_types else []
                    return build_structured_extraction_result(
                        cached_content,
                        tables=tables,
                        figures=figures,
                        equations=equations,
                    )
                # Fallback: try old flat sidecar format
                if _has_flat_sidecars(ai_dir, normalized_id):
                    cached = _read_cached_structured(ai_dir, normalized_id, cached_content)
                    tables = cached.tables if "tables" in extract_types else []
                    figures = cached.figures if "figures" in extract_types else []
                    equations = cached.equations if "equations" in extract_types else []
                    return build_structured_extraction_result(
                        cached_content,
                        tables=tables,
                        figures=figures,
                        equations=equations,
                    )

        if primary.suffix.lower() == ".pdf":
            result = extract_file_sync(str(primary))
            extraction = _build_structured_from_result(
                result,
                ai_dir=ai_dir,
                doc_stem=normalized_id,
                extract_types=extract_types,
            )
        else:
            extraction = _convert_document_to_structured(
                primary,
                config,
                ai_dir=ai_dir,
                doc_stem=normalized_id,
                extract_types=extract_types,
            )

        markdown = extraction.content

        ai_dir.mkdir(parents=True, exist_ok=True)
        md_path.write_text(markdown, encoding="utf-8")
        _persist_extraction_artifacts(ai_dir, normalized_id, extraction, extract_types=extract_types)

        return extraction


def _convert_document_to_structured(
    primary: Path,
    config: ConverterConfig,
    *,
    ai_dir: Path | None = None,
    doc_stem: str | None = None,
    extract_types: set[str] | None = None,
) -> StructuredExtractionResult:
    """Convert non-PDF document to structured extraction via configured backend.

    Args:
        primary: Path to source document (DOCX, DOC, etc.)
        config: Converter configuration
        ai_dir: Optional .ai directory for artifact storage.
        doc_stem: Document stem for naming artifacts.
        extract_types: Optional set of artifact types to extract/persist.

    Returns:
        Structured extraction payload

    Raises:
        ConversionError: If all conversion attempts fail
    """
    if extract_types is None:
        extract_types = {"tables", "figures", "equations"}

    if config.backend == ConverterBackend.REMOTE:
        # Remote only - no fallback
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = _convert_via_remote(primary, Path(tmpdir), config)
            result = extract_file_sync(str(pdf_path))
            return _build_structured_from_result(result, ai_dir=ai_dir, doc_stem=doc_stem, extract_types=extract_types)

    if config.backend == ConverterBackend.LIBREOFFICE:
        # LibreOffice only - no fallback
        return _convert_via_libreoffice(primary, ai_dir=ai_dir, doc_stem=doc_stem, extract_types=extract_types)

    # AUTO: Try LibreOffice first, fallback to remote on failure
    try:
        return _convert_via_libreoffice(primary, ai_dir=ai_dir, doc_stem=doc_stem, extract_types=extract_types)
    except Exception as e:
        logger.warning(f"LibreOffice conversion failed for {primary.name}: {e}")
        logger.info(f"Falling back to remote converter for {primary.name}")
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = _convert_via_remote(primary, Path(tmpdir), config)
            result = extract_file_sync(str(pdf_path))
            return _build_structured_from_result(result, ai_dir=ai_dir, doc_stem=doc_stem, extract_types=extract_types)


def _convert_via_libreoffice(
    primary: Path,
    *,
    ai_dir: Path | None = None,
    doc_stem: str | None = None,
    extract_types: set[str] | None = None,
) -> StructuredExtractionResult:
    """Convert document to structured extraction via LibreOffice.

    Args:
        primary: Path to source document (DOCX, DOC, etc.)
        ai_dir: Optional .ai directory for artifact storage.
        doc_stem: Document stem for naming artifacts.
        extract_types: Optional set of artifact types to extract/persist.

    Returns:
        Structured extraction payload

    Raises:
        ConversionError: If LibreOffice conversion fails
    """
    try:
        converter = Converter()
        with tempfile.TemporaryDirectory() as tmpdir:
            conversion_result = converter.convert(primary, LibreOfficeFormat.PDF, Path(tmpdir))
            result = extract_file_sync(str(conversion_result.output_path))
            return _build_structured_from_result(result, ai_dir=ai_dir, doc_stem=doc_stem, extract_types=extract_types)
    except Exception as e:
        msg = f"LibreOffice conversion failed for {primary.name}: {e}"
        logger.error(msg)
        raise ConversionError(msg) from e


def _persist_extraction_artifacts(
    ai_dir: Path,
    doc_stem: str,
    extraction: StructuredExtractionResult,
    *,
    extract_types: set[str] | None = None,
) -> None:
    """Persist extracted artifacts to folder-based storage.

    Args:
        ai_dir: Destination `.ai` directory.
        doc_stem: Base filename stem (typically normalized document ID).
        extraction: Structured extraction payload.
        extract_types: Optional set of artifact types to persist.
    """
    if extract_types is None:
        extract_types = {"tables", "figures", "equations"}

    if extraction.table_count > 0 and "tables" in extract_types:
        persist_tables_from_extraction(extraction.tables, ai_dir, doc_stem)

    if extraction.figure_count > 0 and "figures" in extract_types:
        figures_dir = ai_dir / "figures"
        persist_figures_from_extraction(extraction.figures, figures_dir, doc_stem)

    if extraction.equation_count > 0 and "equations" in extract_types:
        persist_equations_from_extraction(extraction.equations, ai_dir, doc_stem)


def _has_flat_sidecars(ai_dir: Path, doc_stem: str) -> bool:
    """Check if old flat sidecar format exists for backward compatibility.

    Args:
        ai_dir: The `.ai` directory.
        doc_stem: Base filename stem.

    Returns:
        True if any flat sidecar file exists.
    """
    return any((ai_dir / f"{doc_stem}_{suffix}").exists() for suffix in ("_tables.json", "_figures.json", "_equations.json"))


def _read_cached_structured(ai_dir: Path, doc_stem: str, cached_content: str) -> StructuredExtractionResult:
    """Read cached markdown and optional sidecars into a structured payload."""

    def _load_list(path: Path) -> list[dict]:
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, list) else []
        except Exception as exc:
            logger.warning("Failed to parse sidecar %s: %s", path, exc)
            return []

    tables_raw = _load_list(ai_dir / f"{doc_stem}_tables.json")
    figures_raw = _load_list(ai_dir / f"{doc_stem}_figures.json")
    equations_raw = _load_list(ai_dir / f"{doc_stem}_equations.json")

    tables = [ExtractedTableElement.model_validate(item) for item in tables_raw]
    figures = [ExtractedFigureElement.model_validate(item) for item in figures_raw]
    equations = [ExtractedEquationElement.model_validate(item) for item in equations_raw]
    return build_structured_extraction_result(
        cached_content,
        tables=tables,
        figures=figures,
        equations=equations,
    )


def _build_structured_from_result(
    result: object,
    *,
    ai_dir: Path | None = None,
    doc_stem: str | None = None,
    extract_types: set[str] | None = None,
) -> StructuredExtractionResult:
    """Build structured extraction from kreuzberg result.

    Args:
        result: kreuzberg extraction result.
        ai_dir: Optional .ai directory for artifact storage.
        doc_stem: Document stem for naming artifacts.
        extract_types: Optional set of artifact types to extract/persist.

    Returns:
        Structured extraction payload.
    """
    figure_paths: dict[str, str] | None = None
    figure_descriptions: dict[str, str] | None = None
    if ai_dir is not None and extract_types is not None and "figures" in extract_types:
        figures_dir = ai_dir / "figures"
        persisted = persist_figures_from_kreuzberg_result(result, figures_dir, doc_stem=doc_stem)
        figure_paths = {key: str(path) for key, path in persisted.items()}
        figure_descriptions = describe_figures(persisted, enabled=True)

    return from_kreuzberg_result(
        result,
        figure_paths=figure_paths,
        figure_descriptions=figure_descriptions,
    )


__all__ = [
    "ConverterBackend",
    "ConverterConfig",
    "convert_tdoc",
    "convert_tdoc_to_markdown",
    "extract_tdoc_structured",
]
