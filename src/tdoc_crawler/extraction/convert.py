"""TDoc to Markdown conversion operations.

This module provides TDoc-specific conversion functionality using OpenDataLoader.
No wrapper layers - direct use of OpenDataLoader output files.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TypedDict

import opendataloader_pdf

from tdoc_crawler.database.meetings import get_meeting_short_name
from tdoc_crawler.extraction.fetch_tdoc import fetch_tdoc_files
from tdoc_crawler.extraction.metrics import MetricType, get_metrics_tracker, timed_operation
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.workspaces import ConversionError
from tdoc_crawler.tdocs.models import TDocMetadata
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec
from tdoc_crawler.utils.normalization import normalize_tdoc_id

logger = get_logger(__name__)


@dataclass
class OpendataloaderConfig:
    """Configuration for OpenDataLoader PDF conversion.

    Fields map 1:1 to opendataloader_pdf.convert() parameters.
    """

    image_format: str = "png"
    hybrid: str = "off"
    table_method: str | None = None
    use_struct_tree: bool = False
    reading_order: str | None = None
    pages: str | None = None
    include_header_footer: bool = False
    detect_strikethrough: bool = False
    keep_line_breaks: bool = False
    sanitize: bool = False
    content_safety_off: str | list[str] | None = None
    replace_invalid_chars: str | None = None
    image_output: str | None = None
    image_dir: str | None = None
    hybrid_mode: str | None = None
    hybrid_url: str | None = None
    hybrid_timeout: str | None = None
    hybrid_fallback: bool = False
    text_page_separator: str | None = None
    html_page_separator: str | None = None
    markdown_page_separator: str | None = None
    password: str | None = None

    def to_convert_kwargs(self) -> dict[str, str | bool | list[str]]:
        """Build kwargs dict for opendataloader_pdf.convert().

        Only non-None fields are included.
        """
        return {k: v for k, v in asdict(self).items() if v is not None}


class ExtractedTable(TypedDict):
    element_id: str
    page_number: int | None
    row_count: int
    column_count: int
    cells: list[list[str]]
    cell_metadata: list[dict[str, Any]]
    markdown: str
    caption: str | None
    source_anchor_id: str


class ExtractedFigure(TypedDict):
    element_id: str
    page_number: int | None
    image_path: str | None
    image_format: str | None
    caption: str | None
    description: str | None
    source_anchor_id: str
    is_partial: bool
    partial_reason_codes: list[str]
    metadata: dict[str, Any]


class ExtractedEquation(TypedDict):
    element_id: str
    page_number: int | None
    equation_number: str | None
    latex: str
    raw_text: str | None
    source_anchor_id: str
    normalized_text: str | None
    equation_type: str
    display_mode: str


class ExtractionResult(TypedDict):
    content: str
    tables: list[ExtractedTable]
    figures: list[ExtractedFigure]
    equations: list[ExtractedEquation]


def _format_tdoc_metadata(metadata: TDocMetadata) -> str:
    """Format TDoc metadata as markdown header.

    Args:
        metadata: TDoc metadata to format.

    Returns:
        Markdown formatted string with TDoc metadata.
    """
    lines: list[str] = []

    lines.append(f"# {metadata.title}\n")
    lines.append(f"**TDoc ID:** {metadata.document_id}\n")

    meeting_name = get_meeting_short_name(metadata.meeting_id)
    if meeting_name:
        lines.append(f"**Meeting:** {meeting_name}\n")
    else:
        lines.append(f"**Meeting ID:** {metadata.meeting_id}\n")

    if metadata.source:
        lines.append(f"**Source:** {metadata.source}\n")

    if metadata.contact:
        lines.append(f"**Contact:** {metadata.contact}\n")

    lines.append(f"**Type:** {metadata.tdoc_type}\n")
    lines.append(f"**For:** {metadata.for_purpose}\n")

    if metadata.agenda_item_text:
        lines.append(f"**Agenda Item:** {metadata.agenda_item_text}\n")

    if metadata.status:
        lines.append(f"**Status:** {metadata.status}\n")

    if metadata.url:
        lines.append(f"\n**URL:** {metadata.url}\n")

    return "".join(lines)


def convert_tdoc_metadata(
    document_id: str,
    output_file: Path | None = None,
) -> str:
    """Convert a TDoc's metadata to markdown format.

    Args:
        document_id: Document identifier (e.g., "S4-260001").
        output_file: Optional file to write markdown to.

    Returns:
        Markdown formatted string or output file path.

    Raises:
        ValueError: If TDoc cannot be found via WhatTheSpec.
    """
    normalized_id = normalize_tdoc_id(document_id)
    metadata = resolve_via_whatthespec(normalized_id)

    if metadata is None:
        msg = f"TDoc {normalized_id} not found via WhatTheSpec"
        raise ValueError(msg)

    markdown_content = _format_tdoc_metadata(metadata)

    if output_file is not None:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(markdown_content, encoding="utf-8")
        logger.info("Wrote metadata markdown to %s", output_file)
        return str(output_file)

    return markdown_content


def _parse_opendataloader_elements(json_file: Path) -> list[dict[str, Any]]:
    """Parse OpenDataLoader JSON output into element list."""
    try:
        data = json.loads(json_file.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception as e:
        logger.warning("Failed to parse OpenDataLoader JSON: %s", e)
    return []


def _extract_tables_from_opendataloader_json(json_file: Path) -> list[dict[str, Any]]:
    """Extract table elements from OpenDataLoader JSON output."""
    return [
        {
            "element_id": f"table_{i}",
            "page_number": el.get("page number"),
            "row_count": 0,
            "column_count": 0,
            "cells": [],
            "cell_metadata": [],
            "markdown": el.get("content", ""),
            "caption": None,
            "source_anchor_id": f"table-{i}",
        }
        for i, el in enumerate(_parse_opendataloader_elements(json_file), start=1)
        if el.get("type") == "table"
    ]


def _extract_figures_from_opendataloader_json(json_file: Path) -> list[dict[str, Any]]:
    """Extract figure elements from OpenDataLoader JSON output."""
    return [
        {
            "element_id": f"figure_{i}",
            "page_number": el.get("page number"),
            "image_path": None,
            "image_format": None,
            "caption": None,
            "description": None,
            "source_anchor_id": f"figure-{i}",
            "is_partial": False,
            "partial_reason_codes": [],
            "metadata": {},
        }
        for i, el in enumerate(_parse_opendataloader_elements(json_file), start=1)
        if el.get("type") in ("image", "figure")
    ]


def _extract_formulas_from_opendataloader_json(json_file: Path) -> list[dict[str, Any]]:
    """Extract formula elements from OpenDataLoader JSON output."""
    return [
        {
            "element_id": f"formula_{i}",
            "page_number": el.get("page number"),
            "equation_number": None,
            "latex": el.get("content", ""),
            "raw_text": None,
            "source_anchor_id": f"formula-{i}",
            "normalized_text": None,
            "equation_type": "latex",
            "display_mode": "display",
        }
        for i, el in enumerate(_parse_opendataloader_elements(json_file), start=1)
        if el.get("type") == "formula"
    ]


def _ensure_converted(
    document_id: str,
    force: bool = False,
    config: OpendataloaderConfig | None = None,
) -> tuple[str, Path, str]:
    """Fetch TDoc and ensure markdown conversion exists.

    Handles file fetching, cache checking, and OpenDataLoader conversion.
    Writes only raw content to cache (no metadata) for consistency across callers.

    Args:
        document_id: TDoc identifier (e.g., "S4-260001")
        force: Force reconversion even if cached
        config: Optional OpenDataLoader configuration

    Returns:
        Tuple of (raw_markdown, json_path, normalized_id).
        json_path may not exist on disk — caller must check.

    Raises:
        ConversionError: If no document files found or conversion fails.
    """
    normalized_id = normalize_tdoc_id(document_id)

    tdoc_files = fetch_tdoc_files(normalized_id, force_download=force)
    primary = tdoc_files.primary_path
    if primary is None:
        raise ConversionError(f"No document files found for {normalized_id}")

    ai_dir = _get_ai_directory(primary)
    md_file = ai_dir / f"{primary.stem}.md"
    json_file = ai_dir / f"{primary.stem}.json"

    if md_file.exists() and not force:
        markdown_content = md_file.read_text(encoding="utf-8")
    else:
        markdown_content, _ = _run_opendataloader(primary, ai_dir, config=config)
        md_file.write_text(markdown_content, encoding="utf-8")

    return markdown_content, json_file, normalized_id


def _prepend_metadata_header(content: str, document_id: str) -> str:
    """Resolve TDoc metadata and prepend as markdown header."""
    metadata = resolve_via_whatthespec(document_id)
    if metadata:
        header = _format_tdoc_metadata(metadata)
        return header + "\n\n---\n\n" + content
    return content


def convert_document_to_markdown(
    document_id: str,
    output_file: Path | None = None,
    force: bool = False,
    config: OpendataloaderConfig | None = None,
) -> str:
    """Convert TDoc to markdown.

    Args:
        document_id: TDoc identifier (e.g., "S4-260001")
        output_file: Optional file to write markdown to
        force: Force reconversion even if cached
        config: Optional OpenDataLoader configuration

    Returns:
        Markdown content string

    Raises:
        ConversionError: If no document files found or conversion fails
    """
    with timed_operation(get_metrics_tracker(), normalize_tdoc_id(document_id), MetricType.CONVERSION):
        markdown_content, _, normalized_id = _ensure_converted(document_id, force, config=config)
        markdown_content = _prepend_metadata_header(markdown_content, normalized_id)

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(markdown_content, encoding="utf-8")
        return str(output_file)

    return markdown_content


def extract_document_structured_from_tdoc(
    document_id: str,
    force: bool = False,
    config: OpendataloaderConfig | None = None,
) -> ExtractionResult:
    """Extract TDoc content and artifacts.

    Args:
        document_id: TDoc identifier (e.g., "S4-260001")
        force: Force reconversion
        config: Optional OpenDataLoader configuration

    Returns:
        ExtractionResult dict with 'content' (markdown) and optional 'tables', 'figures', 'equations'
    """
    with timed_operation(get_metrics_tracker(), normalize_tdoc_id(document_id), MetricType.CONVERSION):
        markdown_content, json_file, normalized_id = _ensure_converted(document_id, force, config=config)

        tables: list[dict[str, Any]] = []
        figures: list[dict[str, Any]] = []
        equations: list[dict[str, Any]] = []

        if json_file.exists():
            tables = _extract_tables_from_opendataloader_json(json_file)
            figures = _extract_figures_from_opendataloader_json(json_file)
            equations = _extract_formulas_from_opendataloader_json(json_file)

        markdown_content = _prepend_metadata_header(markdown_content, normalized_id)

        result: ExtractionResult = {"content": markdown_content}  # type: ignore[typeddict-item]
        if tables:
            result["tables"] = tables
        if figures:
            result["figures"] = figures
        if equations:
            result["equations"] = equations

        return result


def _get_ai_directory(source_file: Path) -> Path:
    """Get the .ai directory adjacent to the source file."""
    return source_file.parent / ".ai"


def _run_opendataloader(
    input_file: Path,
    output_dir: Path,
    *,
    config: OpendataloaderConfig | None = None,
) -> tuple[str, Path]:
    """Run OpenDataLoader conversion on a single file.

    Args:
        input_file: Path to the PDF file.
        output_dir: Directory for output files.
        config: Optional OpenDataLoader configuration.

    Returns:
        Tuple of (markdown_content, json_file).

    Raises:
        ConversionError: If conversion fails.
    """
    config = config or OpendataloaderConfig()
    formats = "markdown,json,markdown-with-images"

    try:
        opendataloader_pdf.convert(
            input_path=[str(input_file)],
            output_dir=str(output_dir),
            format=formats,
            quiet=True,
            **config.to_convert_kwargs(),
        )
    except Exception as e:
        msg = f"OpenDataLoader conversion failed for {input_file.name}: {e}"
        logger.error(msg)
        raise ConversionError(msg) from e

    stem = input_file.stem
    md_file = output_dir / f"{stem}.md"
    json_file = output_dir / f"{stem}.json"

    markdown_content = md_file.read_text(encoding="utf-8")

    return markdown_content, json_file


# Public alias for convert operation.
convert_tdoc_to_markdown = convert_document_to_markdown


__all__ = [
    "ExtractedEquation",
    "ExtractedFigure",
    "ExtractedTable",
    "ExtractionResult",
    "OpendataloaderConfig",
    "convert_document_to_markdown",
    "convert_tdoc_metadata",
    "convert_tdoc_to_markdown",
    "extract_document_structured_from_tdoc",
]
