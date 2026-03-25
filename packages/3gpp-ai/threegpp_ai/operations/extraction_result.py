"""Shared structured extraction payload utilities.

This module defines a thin constructor around the canonical extraction models
so process/convert/summarize can share one contract.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from threegpp_ai.models import (
    ExtractedEquationElement,
    ExtractedFigureElement,
    ExtractedTableElement,
    StructuredExtractionResult,
)

_EQUATION_PATTERNS = [
    re.compile(r"\$\$(.*?)\$\$", re.DOTALL),
    re.compile(r"\\\[(.*?)\\\]", re.DOTALL),
    re.compile(r"\\begin\{equation\}(.*?)\\end\{equation\}", re.DOTALL),
]


def _build_table_marker(table: ExtractedTableElement) -> str:
    page = table.page_number if table.page_number is not None else "unknown"
    return f"<!-- table:id={table.element_id},page={page},rows={table.row_count},cols={table.column_count} -->"


def _build_figure_marker(figure: ExtractedFigureElement) -> str:
    page = figure.page_number if figure.page_number is not None else "unknown"
    return f"<!-- figure:id={figure.element_id},page={page},format={figure.image_format or 'unknown'} -->"


def _build_equation_marker(equation: ExtractedEquationElement) -> str:
    page = equation.page_number if equation.page_number is not None else "unknown"
    return f"<!-- equation:id={equation.element_id},page={page} -->"


def _detect_equations(content: str) -> list[ExtractedEquationElement]:
    equations: list[ExtractedEquationElement] = []
    index = 1

    for pattern in _EQUATION_PATTERNS:
        for match in pattern.finditer(content):
            latex = match.group(0).strip()
            if not latex:
                continue
            equations.append(
                ExtractedEquationElement(
                    element_id=f"equation_{index}",
                    latex=latex,
                    raw_text=match.group(1).strip() if match.lastindex else None,
                )
            )
            index += 1

    return equations


def persist_figures_from_kreuzberg_result(result: Any, figures_dir: Path) -> dict[str, Path]:
    """Persist extracted figure bytes to disk and return resolved paths.

    Args:
        result: Object returned by kreuzberg extract APIs.
        figures_dir: Target directory for figure artifacts.

    Returns:
        Mapping from generated figure id (figure_N) to file path.
    """
    image_items: Sequence[Any] = getattr(result, "images", []) or []
    if not image_items:
        return {}

    figures_dir.mkdir(parents=True, exist_ok=True)
    path_map: dict[str, Path] = {}
    for index, image in enumerate(image_items, start=1):
        image_bytes = getattr(image, "content", None)
        if not isinstance(image_bytes, bytes) or not image_bytes:
            continue

        image_format = str(getattr(image, "format", "png") or "png").lower()
        extension = "jpg" if image_format == "jpeg" else image_format
        image_path = figures_dir / f"figure_{index}.{extension}"
        image_path.write_bytes(image_bytes)
        path_map[f"figure_{index}"] = image_path

    return path_map


def build_structured_extraction_result(
    content: str,
    *,
    tables: list[ExtractedTableElement] | None = None,
    figures: list[ExtractedFigureElement] | None = None,
    equations: list[ExtractedEquationElement] | None = None,
    metadata: dict[str, Any] | None = None,
) -> StructuredExtractionResult:
    """Build a normalized structured extraction payload.

    Args:
        content: Primary extracted markdown/text content.
        tables: Optional extracted table elements.
        figures: Optional extracted figure elements.
        equations: Optional extracted equation elements.
        metadata: Optional document-level extraction metadata.

    Returns:
        Canonical structured extraction result shared across AI flows.
    """
    return StructuredExtractionResult(
        content=content,
        tables=tables or [],
        figures=figures or [],
        equations=equations or [],
        metadata=metadata or {},
    )


def from_kreuzberg_result(
    result: Any,
    *,
    figure_paths: dict[str, str] | None = None,
    figure_descriptions: dict[str, str] | None = None,
) -> StructuredExtractionResult:
    """Convert a kreuzberg extraction result into the canonical payload.

    The converter is tolerant to partial/missing fields so existing behavior
    remains stable while richer extraction support is rolled out.

    Args:
        result: Object returned by kreuzberg extract APIs.

    Returns:
        Canonical structured extraction result.
    """
    content = getattr(result, "content", "") or ""
    table_items: Sequence[Any] = getattr(result, "tables", []) or []
    image_items: Sequence[Any] = getattr(result, "images", []) or []

    tables: list[ExtractedTableElement] = []
    for index, table in enumerate(table_items, start=1):
        cells_raw = getattr(table, "cells", []) or []
        cells = [[str(cell) for cell in row] for row in cells_raw if isinstance(row, list)]
        row_count = len(cells)
        col_count = max((len(row) for row in cells), default=0)
        tables.append(
            ExtractedTableElement(
                element_id=f"table_{index}",
                page_number=getattr(table, "page_number", None),
                row_count=row_count,
                column_count=col_count,
                cells=cells,
                markdown=getattr(table, "markdown", None),
                caption=getattr(table, "caption", None),
            )
        )

    figures: list[ExtractedFigureElement] = []
    for index, image in enumerate(image_items, start=1):
        figure_id = f"figure_{index}"
        metadata = getattr(image, "metadata", None)
        figures.append(
            ExtractedFigureElement(
                element_id=figure_id,
                page_number=getattr(image, "page_number", None),
                image_path=(figure_paths or {}).get(figure_id),
                image_format=getattr(image, "format", None),
                caption=getattr(image, "caption", None),
                description=(figure_descriptions or {}).get(figure_id),
                metadata=metadata if isinstance(metadata, dict) else {},
            )
        )

    equations = _detect_equations(content)

    marker_lines: list[str] = []
    marker_lines.extend(_build_table_marker(table) for table in tables)
    marker_lines.extend(_build_figure_marker(figure) for figure in figures)
    marker_lines.extend(_build_equation_marker(equation) for equation in equations)
    if marker_lines:
        content = f"{content.rstrip()}\n\n" + "\n".join(marker_lines) + "\n"

    result_metadata = getattr(result, "metadata", None)
    normalized_metadata = result_metadata if isinstance(result_metadata, dict) else {}
    return build_structured_extraction_result(
        content=content,
        tables=tables,
        figures=figures,
        equations=equations,
        metadata=normalized_metadata,
    )


__all__ = [
    "ExtractedEquationElement",
    "ExtractedFigureElement",
    "ExtractedTableElement",
    "StructuredExtractionResult",
    "build_structured_extraction_result",
    "from_kreuzberg_result",
    "persist_figures_from_kreuzberg_result",
]
