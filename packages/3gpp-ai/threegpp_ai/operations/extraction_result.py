"""Shared structured extraction payload utilities.

This module defines a thin constructor around the canonical extraction models
so process/convert/summarize can share one contract.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
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


def _build_artifact_filename(doc_stem: str, artifact_type: str, page: int | None, index: int) -> str:
    """Build artifact filename with page number for traceability.

    Pattern: {doc_stem}_{type}_{page}_{index}.json
    """
    page_str = str(page) if page is not None else "unknown"
    return f"{doc_stem}_{artifact_type}_{page_str}_{index}.json"


def _persist_single_artifact(
    artifact: ExtractedTableElement | ExtractedFigureElement | ExtractedEquationElement,
    ai_dir: Path,
    doc_stem: str,
    artifact_type: str,
    page: int | None,
    index: int,
) -> Path:
    """Persist a single artifact to a temp file then move to final location."""
    folder = ai_dir / artifact_type
    folder.mkdir(parents=True, exist_ok=True)

    # Folder name is plural (tables/, figures/, equations/) but filename uses singular type
    singular_type = artifact_type.rstrip("s")
    filename = _build_artifact_filename(doc_stem, singular_type, page, index)
    artifact_path = folder / filename

    # Write to temp file first, then move
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(artifact.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
        temp_path = Path(f.name)

    shutil.move(str(temp_path), str(artifact_path))
    return artifact_path


def persist_tables_from_extraction(
    tables: list[ExtractedTableElement],
    ai_dir: Path,
    doc_stem: str,
) -> list[Path]:
    """Persist extracted tables to individual JSON files.

    Uses temp-then-commit pattern: writes to temp file, then moves to final location.

    Args:
        tables: List of extracted table elements.
        ai_dir: The .ai directory for the document.
        doc_stem: Document stem (e.g., "S4-250638").

    Returns:
        List of paths to persisted table artifacts.
    """
    if not tables:
        return []

    persisted: list[Path] = []
    for index, table in enumerate(tables, start=1):
        path = _persist_single_artifact(table, ai_dir, doc_stem, "tables", table.page_number, index)
        persisted.append(path)

    return persisted


def persist_equations_from_extraction(
    equations: list[ExtractedEquationElement],
    ai_dir: Path,
    doc_stem: str,
) -> list[Path]:
    """Persist extracted equations to individual JSON files.

    Uses temp-then-commit pattern: writes to temp file, then moves to final location.

    Args:
        equations: List of extracted equation elements.
        ai_dir: The .ai directory for the document.
        doc_stem: Document stem (e.g., "S4-250638").

    Returns:
        List of paths to persisted equation artifacts.
    """
    if not equations:
        return []

    persisted: list[Path] = []
    for index, equation in enumerate(equations, start=1):
        path = _persist_single_artifact(equation, ai_dir, doc_stem, "equations", equation.page_number, index)
        persisted.append(path)

    return persisted


def persist_figures_from_extraction(
    figures: list[ExtractedFigureElement],
    figures_dir: Path,
    doc_stem: str,
) -> dict[str, Path]:
    """Persist extracted figure bytes and metadata to disk.

    Uses temp-then-commit pattern for metadata files.

    Args:
        figures: List of extracted figure elements. Image bytes may be in metadata
            or already saved to disk (image_path set).
        figures_dir: Target directory for figure artifacts.
        doc_stem: Document stem (e.g., "S4-250638").

    Returns:
        Mapping from figure element_id to resolved file path.
    """
    if not figures:
        return {}

    figures_dir.mkdir(parents=True, exist_ok=True)
    path_map: dict[str, Path] = {}

    for index, figure in enumerate(figures, start=1):
        image_path: Path | None = None

        # Case 1: Image already saved to disk (image_path is set)
        if figure.image_path:
            image_path = Path(figure.image_path)
        else:
            # Case 2: Image bytes in metadata (legacy path)
            image_bytes = figure.metadata.get("image_bytes") if figure.metadata else None
            if not isinstance(image_bytes, bytes):
                continue

            image_format = figure.image_format or "png"
            extension = "jpg" if image_format == "jpeg" else image_format

            # Build filename with page number
            filename = f"{doc_stem}_figure_{figure.page_number or 'unknown'}_{index}.{extension}"
            image_path = figures_dir / filename
            image_path.write_bytes(image_bytes)

        # Persist figure metadata JSON — strip image_bytes (already written as binary file)
        metadata_without_bytes = {k: v for k, v in figure.metadata.items() if k != "image_bytes"} if figure.metadata else {}
        figure_for_json = figure.model_copy(update={"metadata": metadata_without_bytes, "image_path": str(image_path)})
        _persist_single_artifact(figure_for_json, figures_dir.parent, doc_stem, "figures", figure.page_number, index)

        path_map[figure.element_id] = image_path

    return path_map


def persist_figures_from_kreuzberg_result(
    result: Any,
    figures_dir: Path,
    doc_stem: str | None = None,
) -> dict[str, Path]:
    """Persist extracted figure bytes to disk and return resolved paths.

    Args:
        result: Object returned by kreuzberg extract APIs.
        figures_dir: Target directory for figure artifacts.
        doc_stem: Document stem for naming (e.g., "S4-250638"). If None, uses legacy naming.

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

        if doc_stem:
            # New naming: {doc_stem}_figure_{page}_{index}.{ext}
            page = getattr(image, "page_number", None)
            filename = f"{doc_stem}_figure_{page or 'unknown'}_{index}.{extension}"
        else:
            # Legacy naming for backward compatibility
            filename = f"figure_{index}.{extension}"

        image_path = figures_dir / filename
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
        figure_paths: Optional mapping from figure id to resolved file path.
        figure_descriptions: Optional mapping from figure id to generated description.

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


def _load_json_artifact(path: Path) -> dict[str, Any]:
    """Load a single JSON artifact file."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_cached_artifacts(
    ai_dir: Path,
    doc_stem: str,
) -> StructuredExtractionResult | None:
    """Read cached artifacts from .ai folder structure.

    Looks for:
    - .ai/tables/{doc_stem}_table_{page}_{index}.json
    - .ai/figures/{doc_stem}_figure_{page}_{index}.json
    - .ai/equations/{doc_stem}_equation_{page}_{index}.json

    Args:
        ai_dir: The .ai directory for the document.
        doc_stem: Document stem (e.g., "S4-250638").

    Returns:
        StructuredExtractionResult if any artifacts found, None otherwise.
    """
    tables_dir = ai_dir / "tables"
    figures_dir = ai_dir / "figures"
    equations_dir = ai_dir / "equations"

    tables: list[ExtractedTableElement] = []
    figures: list[ExtractedFigureElement] = []
    equations: list[ExtractedEquationElement] = []

    # Load tables
    if tables_dir.exists():
        for table_file in sorted(tables_dir.glob(f"{doc_stem}_table_*.json")):
            data = _load_json_artifact(table_file)
            if data:
                tables.append(ExtractedTableElement.model_validate(data))

    # Load figures (metadata only - image bytes handled separately)
    if figures_dir.exists():
        for figure_file in sorted(figures_dir.glob(f"{doc_stem}_figure_*.json")):
            data = _load_json_artifact(figure_file)
            if data:
                figures.append(ExtractedFigureElement.model_validate(data))

    # Load equations
    if equations_dir.exists():
        for eq_file in sorted(equations_dir.glob(f"{doc_stem}_equation_*.json")):
            data = _load_json_artifact(eq_file)
            if data:
                equations.append(ExtractedEquationElement.model_validate(data))

    if not tables and not figures and not equations:
        return None

    return build_structured_extraction_result(
        content="",
        tables=tables,
        figures=figures,
        equations=equations,
    )


def has_cached_artifacts(
    ai_dir: Path,
    doc_stem: str,
    artifact_types: set[str],
) -> bool:
    """Check if cached artifacts exist for specified types.

    Args:
        ai_dir: The .ai directory for the document.
        doc_stem: Document stem (e.g., "S4-250638").
        artifact_types: Set of types to check: {"tables", "figures", "equations"}.

    Returns:
        True if all specified artifact types have at least one cached file.
    """
    for artifact_type in artifact_types:
        folder = ai_dir / artifact_type
        if not folder.exists():
            return False
        pattern = f"{doc_stem}_{artifact_type[:-1]}_*.json"
        if not any(folder.glob(pattern)):
            return False
    return True


__all__ = [
    "ExtractedEquationElement",
    "ExtractedFigureElement",
    "ExtractedTableElement",
    "StructuredExtractionResult",
    "build_structured_extraction_result",
    "from_kreuzberg_result",
    "has_cached_artifacts",
    "persist_equations_from_extraction",
    "persist_figures_from_extraction",
    "persist_figures_from_kreuzberg_result",
    "persist_tables_from_extraction",
    "read_cached_artifacts",
]
