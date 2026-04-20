"""Unified, document-agnostic extraction pipeline using OpenDataLoader.

This module provides a generic extraction interface that works with various document formats
(PDF, DOCX, DOC, etc.) without TDoc-specific metadata handling.

OpenDataLoader features:
- #1 in benchmarks (0.907 accuracy)
- Extracts Markdown, JSON (with bounding boxes), HTML
- OCR for scanned PDFs
- Table, formula, and chart extraction
- Hybrid AI mode for complex documents

The functions:
* extract_document_structured: Main unified extraction function
* extract_document_text: Plain text extraction
"""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from enum import StrEnum, auto
from pathlib import Path
from typing import Any

import opendataloader_pdf
from convert_lo import LibreOfficeFormat
from convert_lo.converter import Converter
from tdoc_crawler.logging import get_logger

from threegpp_ai.models import ConversionError, ExtractionError
from threegpp_ai.operations.conversion import OFFICE_FORMATS
from threegpp_ai.operations.extraction_result import (
    StructuredExtractionResult,
    build_structured_extraction_result,
    from_opendataloader_result,
    persist_equations_from_extraction,
    persist_figures_from_extraction,
    persist_output_contracts,
    persist_tables_from_extraction,
    read_cached_artifacts,
)

logger = get_logger(__name__)

# Default extraction settings - all extractors enabled
_DEFAULT_EXTRACTION_SETTINGS = {"ocr": True, "layout": True, "tables": True, "figures": True, "equations": True, "enrichment": False}


def resolve_extraction_policy(file_path: Path) -> tuple[str, dict[str, bool]]:
    """Resolve extraction policy.

    Returns the default profile with all extractors enabled (tables, figures, equations).
    VLM/hybrid mode is controlled separately via vlm_options parameter.
    """
    return "default", dict(_DEFAULT_EXTRACTION_SETTINGS)


class HybridMode(StrEnum):
    AUTO = auto()
    FULL = auto()


class HybridBackend(StrEnum):
    DOCLING_FAST = "docling-fast"
    OFF = "off"


class ImageOutput(StrEnum):
    EXTERNAL = auto()
    EMBEDDED = auto()
    OFF = auto()


@dataclass
class VlmOptions:
    """Optional VLM features for extraction via hybrid AI mode.

    When hybrid mode is enabled, OpenDataLoader routes complex pages to a local
    or remote LLM for better extraction quality. Requires a running hybrid server.

    Attributes:
        enable_hybrid: Enable hybrid AI mode for complex document pages.
        hybrid_url: URL of the hybrid server (default: http://localhost:5002).
        hybrid_mode: Hybrid mode level - "fast" or "full".
    """

    hybrid_url: str = "http://127.0.0.1:5002"
    hybrid_mode: HybridMode = HybridMode.FULL
    hybrid_backend: HybridBackend = HybridBackend.DOCLING_FAST
    hybrid_fallback: bool = True
    image_output: ImageOutput = ImageOutput.EXTERNAL


@dataclass
class AcceleratorConfig:
    """Accelerator configuration for OpenDataLoader document processing.

    OpenDataLoader is CPU-optimized and doesn't require GPU acceleration.
    This dataclass is kept for API compatibility with the previous docling-based pipeline.

    Attributes:
        device: Compute device (ignored, kept for compatibility).
        num_threads: Thread count for parallel processing.
        batch_size: Batch size for processing (ignored by OpenDataLoader).
    """

    device: str = "auto"
    num_threads: int = 4
    batch_size: int | None = None


# All supported formats (PDF + Office formats + text files)
SUPPORTED_FORMATS = {".pdf", ".txt", ".md"} | OFFICE_FORMATS


def _is_supported_format(file_path: Path) -> bool:
    """Check if a file format is supported for extraction."""
    return file_path.suffix.lower() in SUPPORTED_FORMATS


def _get_ai_directory(file_path: Path) -> Path:
    """Get the .ai directory for a file.

    Creates .ai folder next to the file if it doesn't exist.
    If the file is already inside a .ai directory (e.g., converted PDF),
    uses the parent directory instead to avoid nested .ai/.ai paths.

    Args:
        file_path: Path to source document.

    Returns:
        Path to .ai directory.
    """
    # If file is already inside a .ai folder, use the parent's parent
    # to avoid creating .ai/.ai nested structure
    if file_path.parent.name == ".ai":
        return file_path.parent.parent / ".ai"
    return file_path.parent / ".ai"


def _get_doc_stem(file_path: Path) -> str:
    """Get document stem for naming artifacts.

    Args:
        file_path: Path to source document.

    Returns:
        Document stem (filename without extension).
    """
    return file_path.stem


def _check_cached_extraction(
    ai_dir: Path,
    doc_stem: str,
    extract_types: set[str],
) -> tuple[bool, str | None, set[str]]:
    """Check if cached extraction exists (markdown + artifacts).

    Args:
        ai_dir: The .ai directory.
        doc_stem: Document stem.
        extract_types: Types to check: {"tables", "figures", "equations"}.

    Returns:
        Tuple of (has_valid_cache, cached_content, present_artifact_types).
        has_valid_cache: True if markdown exists and has artifacts.
        cached_content: Cached markdown content if available.
        present_artifact_types: Set of artifact types that already have files in .ai folder.
    """
    md_path = ai_dir / f"{doc_stem}.md"
    has_cached_md = md_path.exists()
    cached_content = None

    if has_cached_md:
        content = md_path.read_text(encoding="utf-8")
        if len(content) > 100:
            cached_content = content

    present_artifact_types: set[str] = set()
    if cached_content:
        # Check for cached artifacts using folder-based storage
        cached = read_cached_artifacts(ai_dir, doc_stem)
        if cached is not None:
            if cached.tables:
                present_artifact_types.add("tables")
            if cached.figures:
                present_artifact_types.add("figures")
            if cached.equations:
                present_artifact_types.add("equations")
            return True, cached_content, present_artifact_types

    return False, None, present_artifact_types


def _run_opendataloader(
    file_path: Path,
    output_dir: Path,
    *,
    extract_tables: bool = True,
    extract_figures: bool = True,
    vlm_options: VlmOptions | None = None,
) -> tuple[Path, Path]:
    """Run opendataloader_pdf conversion on a single file.

    Args:
        file_path: Path to the PDF file.
        output_dir: Directory for output files.
        extract_tables: Whether to extract tables.
        extract_figures: Whether to extract figures.
        vlm_options: Optional VLM/hybrid mode configuration.

    Returns:
        Tuple of (markdown_path, json_path) for the converted file.

    Raises:
        ExtractionError: If conversion fails.
    """
    formats = ["markdown", "json"]
    if extract_figures:
        formats.append("markdown-with-images")

    vlm_options = vlm_options or VlmOptions()

    try:
        opendataloader_pdf.convert(
            input_path=[str(file_path)],
            output_dir=str(output_dir),
            format=",".join(formats),
            image_output=vlm_options.image_output,
            hybrid=vlm_options.hybrid_backend,
            hybrid_mode=vlm_options.hybrid_mode,
            hybrid_url=vlm_options.hybrid_url,
        )
    except Exception as e:
        msg = f"OpenDataLoader conversion failed for {file_path.name}: {e}"
        logger.error(msg)
        raise ExtractionError(msg) from e

    # OpenDataLoader creates output files with the same stem as input
    stem = file_path.stem
    md_path = output_dir / f"{stem}.md"
    json_path = output_dir / f"{stem}.json"

    return md_path, json_path


def _extract_tables_from_opendataloader(json_path: Path) -> list[dict[str, Any]]:
    """Extract table elements from OpenDataLoader JSON output.

    Args:
        json_path: Path to the JSON output file.

    Returns:
        List of table element dictionaries.
    """
    tables: list[dict[str, Any]] = []
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return tables

        for index, element in enumerate(data, start=1):
            if element.get("type") == "table":
                table = {
                    "element_id": f"table_{index}",
                    "page_number": element.get("page number"),
                    "row_count": 0,
                    "column_count": 0,
                    "cells": [],
                    "cell_metadata": [],
                    "markdown": element.get("content", ""),
                    "caption": None,
                    "source_anchor_id": f"table-{index}",
                    "bounding_box": element.get("bounding box"),
                }

                # Try to extract table structure from content
                content = element.get("content", "")
                if content:
                    lines = content.split("\n")
                    table["row_count"] = len(lines)
                    for line in lines:
                        cells = line.split("|")
                        cells = [c.strip() for c in cells if c.strip() and c.strip() != "---"]
                        if cells:
                            table["column_count"] = max(table["column_count"], len(cells))
                            table["cells"].append(cells)

                tables.append(table)
    except Exception as e:
        logger.warning("Failed to parse tables from OpenDataLoader JSON: %s", e)

    return tables


def _extract_figures_from_opendataloader(json_path: Path) -> list[dict[str, Any]]:
    """Extract figure/image elements from OpenDataLoader JSON output.

    Args:
        json_path: Path to the JSON output file.

    Returns:
        List of figure element dictionaries.
    """
    figures: list[dict[str, Any]] = []
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return figures

        for index, element in enumerate(data, start=1):
            if element.get("type") == "picture":
                figure = {
                    "element_id": f"figure_{index}",
                    "page_number": element.get("page number"),
                    "image_path": None,
                    "image_format": "png",
                    "caption": element.get("caption"),
                    "description": element.get("description"),
                    "source_anchor_id": f"figure-{index}",
                    "is_partial": False,
                    "partial_reason_codes": [],
                    "metadata": {"bounding_box": element.get("bounding box")},
                }
                figures.append(figure)
    except Exception as e:
        logger.warning("Failed to parse figures from OpenDataLoader JSON: %s", e)

    return figures


def _extract_formulas_from_opendataloader(json_path: Path) -> list[dict[str, Any]]:
    """Extract formula elements from OpenDataLoader JSON output.

    Args:
        json_path: Path to the JSON output file.

    Returns:
        List of formula element dictionaries with LaTeX content.
    """
    formulas: list[dict[str, Any]] = []
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return formulas

        for index, element in enumerate(data, start=1):
            if element.get("type") == "formula":
                formula = {
                    "element_id": f"equation_{index}",
                    "latex": element.get("content", ""),
                    "raw_text": element.get("content"),
                    "source_anchor_id": f"equation-{index}",
                    "normalized_text": element.get("content", ""),
                    "equation_type": "latex",
                    "display_mode": "display",
                    "page_number": element.get("page number"),
                    "metadata": {"bounding_box": element.get("bounding box")},
                }
                formulas.append(formula)
    except Exception as e:
        logger.warning("Failed to parse formulas from OpenDataLoader JSON: %s", e)

    return formulas


def _convert_via_libreoffice(
    file_path: Path,
    ai_dir: Path | None = None,
    doc_stem: str | None = None,
    extract_types: set[str] | None = None,
    vlm_options: VlmOptions | None = None,
    effective_settings: dict[str, bool] | None = None,
) -> StructuredExtractionResult:
    """Convert non-PDF document to structured extraction via LibreOffice + OpenDataLoader.

    Args:
        file_path: Path to source document (DOCX, DOC, etc.).
        ai_dir: Optional .ai directory for artifact storage.
        doc_stem: Document stem for naming artifacts.
        extract_types: Optional set of artifact types to extract/persist.
        vlm_options: Optional VLM features for PDF extraction.
        effective_settings: Effective profile settings controlling extraction stages.

    Returns:
        Structured extraction payload.

    Raises:
        ConversionError: If LibreOffice conversion fails.
    """
    try:
        converter = Converter()
        with tempfile.TemporaryDirectory() as tmpdir:
            conversion_result = converter.convert(file_path, LibreOfficeFormat.PDF, Path(tmpdir))

            settings = effective_settings or _DEFAULT_EXTRACTION_SETTINGS

            with tempfile.TemporaryDirectory() as output_dir:
                md_path, json_path = _run_opendataloader(
                    conversion_result.output_path,
                    Path(output_dir),
                    extract_tables=settings["tables"],
                    extract_figures=settings["figures"],
                    vlm_options=vlm_options,
                )

                # Read markdown content
                markdown_content = ""
                if md_path.exists():
                    markdown_content = md_path.read_text(encoding="utf-8")

                # Parse JSON for structured data
                tables = _extract_tables_from_opendataloader(json_path) if settings["tables"] else []
                figures = _extract_figures_from_opendataloader(json_path) if settings["figures"] else []
                formulas = _extract_formulas_from_opendataloader(json_path) if settings["equations"] else []

                # Extract images if enabled
                image_dir = ai_dir / "figures" if ai_dir and settings["figures"] else None
                if image_dir and md_path.exists():
                    # Copy images from output directory
                    for ext in ("*.png", "*.jpg", "*.jpeg"):
                        for img_path in Path(output_dir).glob(ext):
                            shutil.copy(img_path, image_dir / img_path.name)

                return from_opendataloader_result(
                    markdown_content=markdown_content,
                    tables=tables,
                    figures=figures,
                    formulas=formulas,
                )

    except ExtractionError:
        raise
    except Exception as e:
        msg = f"LibreOffice conversion failed for {file_path.name}: {e}"
        logger.error(msg)
        raise ConversionError(msg) from e


def _persist_extraction_artifacts(
    ai_dir: Path,
    doc_stem: str,
    extraction: StructuredExtractionResult,
    extract_types: set[str],
) -> None:
    """Persist extracted artifacts to folder-based storage.

    Args:
        ai_dir: Destination `.ai` directory.
        doc_stem: Base filename stem.
        extraction: Structured extraction payload.
        extract_types: Types to persist: {"tables", "figures", "equations"}.
    """
    if extraction.table_count > 0 and "tables" in extract_types:
        persist_tables_from_extraction(extraction.tables, ai_dir, doc_stem)

    if extraction.figure_count > 0 and "figures" in extract_types:
        figures_dir = ai_dir / "figures"
        persist_figures_from_extraction(extraction.figures, figures_dir, doc_stem)
    if extraction.equation_count > 0 and "equations" in extract_types:
        persist_equations_from_extraction(extraction.equations, ai_dir, doc_stem)


def _extract_pdf_or_text(
    file_path: Path,
    output_dir: Path,
    effective_settings: dict[str, bool],
    effective_vlm: VlmOptions | None,
) -> StructuredExtractionResult:
    """Extract content from PDF or text files using OpenDataLoader.

    Args:
        file_path: Path to the PDF or text file.
        output_dir: Temporary directory for OpenDataLoader output.
        effective_settings: Effective extraction settings.
        effective_vlm: Effective VLM options (may be None).

    Returns:
        StructuredExtractionResult with extracted content and artifacts.
    """
    md_path, json_path = _run_opendataloader(
        file_path,
        Path(output_dir),
        extract_tables=effective_settings["tables"],
        extract_figures=effective_settings["figures"],
        vlm_options=effective_vlm,
    )

    markdown_content = ""
    if md_path.exists():
        markdown_content = md_path.read_text(encoding="utf-8")

    tables = _extract_tables_from_opendataloader(json_path) if effective_settings["tables"] else []
    figures = _extract_figures_from_opendataloader(json_path) if effective_settings["figures"] else []
    formulas = _extract_formulas_from_opendataloader(json_path) if effective_settings["equations"] else []

    return from_opendataloader_result(
        markdown_content=markdown_content,
        tables=tables,
        figures=figures,
        formulas=formulas,
    )


def _build_result_from_cache(
    ai_dir: Path,
    doc_stem: str,
    cached_content: str,
    cached: Any,
    extract_types: set[str],
    present_artifact_types: set[str],
    skip_existing: bool,
    merged_metadata: dict[str, Any],
) -> StructuredExtractionResult | None:
    """Build result from cached extraction if available.

    Returns None if no cache hit, otherwise returns the structured result.
    """
    active_extract_types = extract_types - present_artifact_types if skip_existing else extract_types

    tables = cached.tables if "tables" in active_extract_types else []
    figures = cached.figures if "figures" in active_extract_types else []
    equations = cached.equations if "equations" in active_extract_types else []
    result = build_structured_extraction_result(
        cached_content,
        tables=tables,
        figures=figures,
        equations=equations,
        metadata=merged_metadata | {"cache_hit": True},
    )
    return persist_output_contracts(ai_dir, doc_stem, result)


def _merge_with_cached_artifacts(
    extraction: StructuredExtractionResult,
    ai_dir: Path,
    doc_stem: str,
    extraction_skip_types: set[str],
) -> StructuredExtractionResult:
    """Merge fresh extraction with cached artifacts when skip_existing=True."""
    cached = read_cached_artifacts(ai_dir, doc_stem)
    if cached is None:
        return extraction

    tables = list(extraction.tables)
    figures = list(extraction.figures)
    equations = list(extraction.equations)

    if cached.tables and "tables" not in extraction_skip_types:
        tables = cached.tables + tables
    if cached.figures and "figures" not in extraction_skip_types:
        figures = cached.figures + figures
    if cached.equations and "equations" not in extraction_skip_types:
        equations = cached.equations + equations

    return build_structured_extraction_result(
        extraction.content,
        tables=tables,
        figures=figures,
        equations=equations,
        metadata=extraction.metadata,
    )


def _compute_extraction_skip_types(
    skip_existing: bool,
    present_artifact_types: set[str],
    extract_types: set[str],
    effective_settings: dict[str, bool],
) -> tuple[set[str], dict[str, bool]]:
    """Compute which artifact types to skip during extraction.

    Returns tuple of (skip_types, modified_settings) where modified_settings
    is a copy with disabled settings for skipped types.
    """
    if not skip_existing or not present_artifact_types:
        return set(), effective_settings

    skip_types = present_artifact_types & extract_types
    modified_settings = effective_settings.copy()
    for artifact_type in skip_types:
        modified_settings[artifact_type] = False
    return skip_types, modified_settings


def extract_document_structured(
    file_path: Path,
    metadata: dict[str, Any] | None = None,
    force: bool = False,
    skip_existing: bool = False,
    extract_types: set[str] | None = None,
    vlm_options: VlmOptions | None = None,
    accelerator_config: AcceleratorConfig | None = None,
) -> StructuredExtractionResult:
    """Extract a document into a canonical structured payload.

    This is the main unified extraction function that handles:
    - PDF files: Direct extraction via OpenDataLoader
    - Office files (DOCX, DOC, etc.): Convert to PDF, then extract via OpenDataLoader
    - Text files (TXT, MD): Direct extraction via OpenDataLoader

    Caching:
    - Checks for existing .md file in .ai subdirectory
    - Checks for folder-based artifacts (tables/, figures/, equations/)
    - Only re-extracts if force=True or cache miss

    Args:
        file_path: Path to the source document file.
        metadata: Optional document metadata passed through to the result
            envelope for downstream consumers.
        force: If True, re-extract even if cached artifacts exist.
        skip_existing: If True, skip extraction for artifact types that already
            exist in the .ai folder (allows resuming extraction for missing components
            without re-extracting everything).
        extract_types: Optional set of artifact types to extract/persist.
            If None, extracts all types. Supported types: "tables", "figures", "equations".
        vlm_options: Optional VLM features for extraction. Enables hybrid AI mode
            for complex PDF pages. If None, uses deterministic local extraction.
        accelerator_config: Optional accelerator settings (ignored, kept for compatibility).

    Returns:
        StructuredExtractionResult with content, tables, figures, and equations.

    Raises:
        ExtractionError: If the source file does not exist or extraction fails.
        ConversionError: If Office document conversion fails.
    """
    del accelerator_config  # OpenDataLoader is CPU-optimized, no GPU needed

    if not file_path.exists():
        raise ExtractionError(f"Source file does not exist: {file_path}")

    if not _is_supported_format(file_path):
        raise ExtractionError(f"Unsupported file format: {file_path.suffix}")

    selected_profile, effective_settings = resolve_extraction_policy(file_path)

    if extract_types is None:
        extract_types = {"tables", "figures", "equations"}

    merged_metadata: dict[str, Any] = {
        "extraction_profile": selected_profile,
        "effective_extraction_settings": effective_settings,
    }
    if metadata:
        merged_metadata.update(metadata)

    ai_dir = _get_ai_directory(file_path)
    doc_stem = _get_doc_stem(file_path)

    # Check for cached extraction
    has_cache, cached_content, present_artifact_types = _check_cached_extraction(ai_dir, doc_stem, extract_types)
    if has_cache and cached_content is not None and not force:
        cached = read_cached_artifacts(ai_dir, doc_stem)
        if cached is not None:
            result = _build_result_from_cache(
                ai_dir,
                doc_stem,
                cached_content,
                cached,
                extract_types,
                present_artifact_types,
                skip_existing,
                merged_metadata,
            )
            if result is not None:
                return result

    # Compute which artifact types to skip when skip_existing=True
    extraction_skip_types, eff_settings = _compute_extraction_skip_types(
        skip_existing,
        present_artifact_types,
        extract_types,
        effective_settings,
    )

    with tempfile.TemporaryDirectory() as output_dir:
        suffix = file_path.suffix.lower()
        if suffix == ".pdf" or suffix in {".txt", ".md"}:
            extraction = _extract_pdf_or_text(file_path, output_dir, eff_settings, vlm_options)
        else:
            # Office formats (DOCX, DOC, etc.) - convert to PDF first
            extraction = _convert_via_libreoffice(
                file_path,
                ai_dir=ai_dir,
                doc_stem=doc_stem,
                extract_types=extract_types - extraction_skip_types,
                vlm_options=vlm_options,
                effective_settings=eff_settings,
            )

    extraction = extraction.model_copy(update={"metadata": merged_metadata | dict(extraction.metadata)})

    # Ensure .ai directory exists
    ai_dir.mkdir(parents=True, exist_ok=True)

    # Save markdown (only if we don't have cached content)
    md_path = ai_dir / f"{doc_stem}.md"
    if not cached_content:
        md_path.write_text(extraction.content, encoding="utf-8")
        logger.info("Saved markdown: %s", md_path)

    # Merge with cached artifacts when skip_existing=True
    if skip_existing and present_artifact_types:
        extraction = _merge_with_cached_artifacts(extraction, ai_dir, doc_stem, extraction_skip_types)

    # Persist artifacts (skipping types that were already present when skip_existing=True)
    persist_types = extract_types - extraction_skip_types
    _persist_extraction_artifacts(ai_dir, doc_stem, extraction, extract_types=persist_types)
    return persist_output_contracts(ai_dir, doc_stem, extraction)


def extract_document_text(
    file_path: Path,
    force: bool = False,
    vlm_options: VlmOptions | None = None,
    accelerator_config: AcceleratorConfig | None = None,
) -> str:
    """Extract plain text content from a document using OpenDataLoader.

    For office documents, first converts to PDF using convert-lo.
    Returns just the text content without structured artifacts.

    Args:
        file_path: Path to the document file.
        force: If True, re-extract even if cached markdown exists.
        vlm_options: Optional VLM features for extraction.
        accelerator_config: Optional accelerator settings (ignored, kept for compatibility).

    Returns:
        Extracted text content as a string.

    Raises:
        ExtractionError: If the source file does not exist or extraction fails.
        ConversionError: If Office document conversion fails.
    """
    extraction = extract_document_structured(
        file_path=file_path,
        metadata=None,
        force=force,
        extract_types=set(),  # No artifacts needed for text-only extraction
        vlm_options=vlm_options,
        accelerator_config=accelerator_config,
    )
    return extraction.content


__all__ = [
    "AcceleratorConfig",
    "VlmOptions",
    "extract_document_structured",
    "extract_document_text",
    "resolve_extraction_policy",
]
