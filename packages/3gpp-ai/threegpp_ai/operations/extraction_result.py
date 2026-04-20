"""Shared structured extraction payload utilities.

This module defines a thin constructor around the canonical extraction models
so process/convert/summarize can share one contract.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from tdoc_crawler.logging import get_logger

from threegpp_ai.models import (
    DocumentMetadataContract,
    ExtractedEquationElement,
    ExtractedFigureElement,
    ExtractedTableElement,
    ExtractionQualityReasonCode,
    ExtractionQualityReport,
    ExtractionQualityStatus,
    PageMetadataContract,
    QualityGateCheckResult,
    StructuredExtractionResult,
)

logger = get_logger(__name__)

_EQUATION_PATTERNS = [
    re.compile(r"\$\$(.*?)\$\$", re.DOTALL),
    re.compile(r"\\\[(.*?)\\\]", re.DOTALL),
    re.compile(r"\\begin\{equation\}(.*?)\\end\{equation\}", re.DOTALL),
]


def _normalize_source_anchor_id(value: Any, fallback: str) -> str:
    """Return a stable, machine-readable source anchor identifier."""
    candidate = str(value).strip().lower() if value is not None else ""
    if not candidate:
        candidate = fallback
    normalized = re.sub(r"\s+", "-", candidate)
    normalized = re.sub(r"[^a-z0-9._-]", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized or fallback


def _normalize_equation_text(value: str) -> str:
    """Normalize equation text to a deterministic single-space form."""
    return re.sub(r"\s+", " ", value).strip()


def _coerce_cell_metadata(cell: Any) -> dict[str, Any] | None:
    """Extract optional cell metadata without requiring geometry contracts."""
    metadata: dict[str, Any] = {}
    if isinstance(cell, dict):
        for key in ("row_span", "col_span", "is_header", "confidence", "row", "column"):
            if key in cell:
                metadata[key] = cell[key]
        return metadata or None

    for key in ("row_span", "col_span", "is_header", "confidence", "row", "column"):
        if hasattr(cell, key):
            value = getattr(cell, key)
            if value is not None:
                metadata[key] = value
    return metadata or None


def _resolve_source_anchor(element: Any, fallback: str) -> str:
    """Resolve source anchor from common provider fields with deterministic fallback."""
    for attr in ("source_anchor_id", "source_anchor", "anchor_id", "self_ref"):
        if hasattr(element, attr):
            raw = getattr(element, attr)
            if raw:
                return _normalize_source_anchor_id(raw, fallback)
    return _normalize_source_anchor_id(None, fallback)


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
            inner_text = match.group(1).strip() if match.lastindex else ""
            equations.append(
                ExtractedEquationElement(
                    element_id=f"equation_{index}",
                    latex=latex,
                    raw_text=inner_text or None,
                    source_anchor_id=_normalize_source_anchor_id(None, f"equation-{index}"),
                    normalized_text=_normalize_equation_text(inner_text or latex),
                    equation_type="latex",
                    display_mode="display",
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


def build_structured_extraction_result(
    content: str,
    *,
    tables: list[ExtractedTableElement] | None = None,
    figures: list[ExtractedFigureElement] | None = None,
    equations: list[ExtractedEquationElement] | None = None,
    document_metadata: DocumentMetadataContract | None = None,
    pages: list[PageMetadataContract] | None = None,
    metadata: dict[str, Any] | None = None,
) -> StructuredExtractionResult:
    """Build a normalized structured extraction payload.

    Args:
        content: Primary extracted markdown/text content.
        tables: Optional extracted table elements.
        figures: Optional extracted figure elements.
        equations: Optional extracted equation elements.
        document_metadata: Optional canonical document metadata contract.
        pages: Optional canonical page metadata contracts.
        metadata: Optional document-level extraction metadata.

    Returns:
        Canonical structured extraction result shared across AI flows.
    """
    table_elements = tables or []
    figure_elements = figures or []
    equation_elements = equations or []

    page_numbers = {
        *(table.page_number for table in table_elements if table.page_number is not None),
        *(figure.page_number for figure in figure_elements if figure.page_number is not None),
        *(equation.page_number for equation in equation_elements if equation.page_number is not None),
    }

    resolved_pages = pages or [
        PageMetadataContract(
            page_number=page_number,
            table_count=sum(1 for table in table_elements if table.page_number == page_number),
            figure_count=sum(1 for figure in figure_elements if figure.page_number == page_number),
            equation_count=sum(1 for equation in equation_elements if equation.page_number == page_number),
        )
        for page_number in sorted(page_numbers)
    ]

    metadata_dict = metadata or {}
    resolved_document_metadata = document_metadata or DocumentMetadataContract(
        document_id=metadata_dict.get("document_id"),
        title=metadata_dict.get("title"),
        source_path=metadata_dict.get("source_path"),
        file_extension=metadata_dict.get("file_extension"),
        total_pages=max(page_numbers) if page_numbers else None,
        extraction_profile=metadata_dict.get("extraction_profile"),
        extraction_status=metadata_dict.get("extraction_status", "ok"),
        config_hash=metadata_dict.get("config_hash"),
    )

    return StructuredExtractionResult(
        content=content,
        tables=table_elements,
        figures=figure_elements,
        equations=equation_elements,
        document_metadata=resolved_document_metadata,
        pages=resolved_pages,
        metadata=metadata_dict,
    )


def _stable_config_hash(metadata: dict[str, Any]) -> str:
    """Create deterministic config fingerprint from extraction-relevant metadata."""
    source = {
        "extraction_profile": metadata.get("extraction_profile"),
        "effective_extraction_settings": metadata.get("effective_extraction_settings"),
        "extraction_status": metadata.get("extraction_status", "ok"),
    }
    encoded = json.dumps(source, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def build_canonical_output(extraction: StructuredExtractionResult) -> dict[str, Any]:
    """Build deterministic canonical JSON payload for persisted contracts."""

    def _json_fallback(value: Any) -> Any:
        if isinstance(value, (bytes, bytearray)):
            return f"<binary:{len(value)}>"
        return str(value)

    def _sanitize_for_json(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): _sanitize_for_json(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_sanitize_for_json(item) for item in value]
        if isinstance(value, tuple):
            return [_sanitize_for_json(item) for item in value]
        if isinstance(value, (bytes, bytearray)):
            return _json_fallback(value)
        return value

    sorted_tables = sorted(
        extraction.tables,
        key=lambda table: (table.page_number if table.page_number is not None else 10**9, table.element_id),
    )
    sorted_figures = sorted(
        extraction.figures,
        key=lambda figure: (figure.page_number if figure.page_number is not None else 10**9, figure.element_id),
    )
    sorted_equations = sorted(
        extraction.equations,
        key=lambda equation: (equation.page_number if equation.page_number is not None else 10**9, equation.element_id),
    )
    sorted_pages = sorted(extraction.pages, key=lambda page: page.page_number)

    return {
        "content": extraction.content,
        "document": extraction.document_metadata.model_dump(mode="json") if extraction.document_metadata else {},
        "pages": [page.model_dump(mode="json") for page in sorted_pages],
        "elements": {
            "tables": [_sanitize_for_json(table.model_dump(mode="python")) for table in sorted_tables],
            "figures": [_sanitize_for_json(figure.model_dump(mode="python")) for figure in sorted_figures],
            "equations": [_sanitize_for_json(equation.model_dump(mode="python")) for equation in sorted_equations],
        },
        "metadata": json.loads(json.dumps(extraction.metadata, default=_json_fallback)),
    }


def persist_canonical_output(
    ai_dir: Path,
    doc_stem: str,
    extraction: StructuredExtractionResult,
) -> Path:
    """Persist canonical extraction payload as first-class JSON artifact."""
    ai_dir.mkdir(parents=True, exist_ok=True)
    output_path = ai_dir / f"{doc_stem}.canonical.json"
    payload = build_canonical_output(extraction)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return output_path


def _collect_artifact_inventory(ai_dir: Path, doc_stem: str, canonical_path: Path, manifest_path: Path) -> list[dict[str, str]]:
    """Collect deterministic artifact inventory for manifest generation."""
    inventory: list[dict[str, str]] = []

    markdown_path = ai_dir / f"{doc_stem}.md"
    if markdown_path.exists():
        inventory.append({"type": "markdown", "path": str(markdown_path)})

    if canonical_path.exists():
        inventory.append({"type": "canonical_json", "path": str(canonical_path)})

    for artifact_type, pattern in (
        ("table", f"{doc_stem}_table_*.json"),
        ("figure", f"{doc_stem}_figure_*.json"),
        ("equation", f"{doc_stem}_equation_*.json"),
    ):
        folder = ai_dir / f"{artifact_type}s"
        if not folder.exists():
            continue
        for path in sorted(folder.glob(pattern)):
            inventory.append({"type": artifact_type, "path": str(path)})

    inventory.append({"type": "manifest", "path": str(manifest_path)})
    return inventory


def persist_output_manifest(
    ai_dir: Path,
    doc_stem: str,
    extraction: StructuredExtractionResult,
    canonical_path: Path,
) -> Path:
    """Persist deterministic output manifest containing status and inventory contracts."""
    manifest_path = ai_dir / f"{doc_stem}_manifest.json"
    config_hash = extraction.metadata.get("config_hash") or _stable_config_hash(extraction.metadata)
    status = extraction.metadata.get("extraction_status", "ok")

    inventory = _collect_artifact_inventory(ai_dir, doc_stem, canonical_path, manifest_path)
    payload = {
        "document_id": extraction.metadata.get("document_id"),
        "doc_stem": doc_stem,
        "extraction_status": status,
        "config_hash": config_hash,
        "artifact_counts": {
            "tables": extraction.table_count,
            "figures": extraction.figure_count,
            "equations": extraction.equation_count,
        },
        "artifacts": inventory,
    }
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return manifest_path


def evaluate_quality_gates(extraction: StructuredExtractionResult) -> ExtractionQualityReport:
    """Evaluate deterministic quality gates for extraction output."""
    checks: list[QualityGateCheckResult] = []

    has_content = bool(extraction.content.strip())
    checks.append(
        QualityGateCheckResult(
            gate="artifact_presence",
            passed=has_content,
            reason_code=None if has_content else ExtractionQualityReasonCode.MISSING_ARTIFACT,
            message=None if has_content else "Primary extracted content is empty.",
        )
    )

    metadata = extraction.metadata or {}
    has_any_metadata = bool(metadata.get("document_id") or metadata.get("source_path") or metadata.get("file_extension"))
    checks.append(
        QualityGateCheckResult(
            gate="metadata_completeness",
            passed=has_any_metadata,
            reason_code=None if has_any_metadata else ExtractionQualityReasonCode.MISSING_METADATA,
            message=None if has_any_metadata else "Required metadata fields are missing.",
        )
    )

    has_invalid_provenance = any(
        element.page_number is None or not element.element_id.strip() for element in [*extraction.tables, *extraction.figures, *extraction.equations]
    )
    checks.append(
        QualityGateCheckResult(
            gate="provenance_integrity",
            passed=not has_invalid_provenance,
            reason_code=None if not has_invalid_provenance else ExtractionQualityReasonCode.INVALID_PROVENANCE,
            message=None if not has_invalid_provenance else "At least one element has missing page or invalid ID.",
        )
    )

    expected_page_counts = {page.page_number: (page.table_count, page.figure_count, page.equation_count) for page in extraction.pages}
    observed_page_numbers = {
        *(table.page_number for table in extraction.tables if table.page_number is not None),
        *(figure.page_number for figure in extraction.figures if figure.page_number is not None),
        *(equation.page_number for equation in extraction.equations if equation.page_number is not None),
    }

    coverage_mismatch = False
    if extraction.pages and observed_page_numbers and set(expected_page_counts) != observed_page_numbers:
        coverage_mismatch = True
    else:
        for page_number, (expected_tables, expected_figures, expected_equations) in expected_page_counts.items():
            observed_tables = sum(1 for table in extraction.tables if table.page_number == page_number)
            observed_figures = sum(1 for figure in extraction.figures if figure.page_number == page_number)
            observed_equations = sum(1 for equation in extraction.equations if equation.page_number == page_number)
            if (expected_tables, expected_figures, expected_equations) != (
                observed_tables,
                observed_figures,
                observed_equations,
            ):
                coverage_mismatch = True
                break

    checks.append(
        QualityGateCheckResult(
            gate="page_coverage_consistency",
            passed=not coverage_mismatch,
            reason_code=None if not coverage_mismatch else ExtractionQualityReasonCode.COVERAGE_MISMATCH,
            message=None if not coverage_mismatch else "Page-level contract counts differ from element provenance.",
        )
    )

    failed_checks = [check for check in checks if not check.passed]
    reason_codes: list[ExtractionQualityReasonCode] = []
    for check in failed_checks:
        if check.reason_code is not None and check.reason_code not in reason_codes:
            reason_codes.append(check.reason_code)

    if any(code in reason_codes for code in (ExtractionQualityReasonCode.MISSING_ARTIFACT, ExtractionQualityReasonCode.INVALID_PROVENANCE)):
        status = ExtractionQualityStatus.FAILED
    elif reason_codes:
        status = ExtractionQualityStatus.PARTIAL
    else:
        status = ExtractionQualityStatus.OK

    metrics = {
        "checks_total": len(checks),
        "checks_failed": len(failed_checks),
        "table_count": extraction.table_count,
        "figure_count": extraction.figure_count,
        "equation_count": extraction.equation_count,
        "page_count": len(extraction.pages),
    }

    return ExtractionQualityReport(
        status=status,
        reason_codes=reason_codes,
        checks=checks,
        gate_metrics_summary=metrics,
    )


def persist_quality_report(
    ai_dir: Path,
    doc_stem: str,
    report: ExtractionQualityReport,
) -> Path:
    """Persist deterministic extraction quality report."""
    ai_dir.mkdir(parents=True, exist_ok=True)
    report_path = ai_dir / f"{doc_stem}_quality.json"
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return report_path


def persist_output_contracts(
    ai_dir: Path,
    doc_stem: str,
    extraction: StructuredExtractionResult,
) -> StructuredExtractionResult:
    """Persist canonical JSON + manifest and annotate extraction metadata with paths."""
    ai_dir.mkdir(parents=True, exist_ok=True)

    base_metadata = dict(extraction.metadata)
    config_hash = base_metadata.get("config_hash") or _stable_config_hash(base_metadata)
    enriched_metadata = base_metadata | {"config_hash": config_hash}
    enriched = extraction.model_copy(update={"metadata": enriched_metadata})

    quality_report = evaluate_quality_gates(enriched)
    extraction_status = quality_report.status.value
    reason_codes = [code.value for code in quality_report.reason_codes]

    enriched_metadata = enriched.metadata | {
        "extraction_status": extraction_status,
        "quality_reason_codes": reason_codes,
        "quality_gate_metrics": quality_report.gate_metrics_summary,
    }
    enriched = enriched.model_copy(update={"metadata": enriched_metadata})

    canonical_path = persist_canonical_output(ai_dir, doc_stem, enriched)
    manifest_path = persist_output_manifest(ai_dir, doc_stem, enriched, canonical_path)
    quality_report_path = persist_quality_report(ai_dir, doc_stem, quality_report)

    document_metadata = enriched.document_metadata or DocumentMetadataContract(extraction_status=extraction_status)
    document_metadata = document_metadata.model_copy(
        update={
            "extraction_status": extraction_status,
            "config_hash": config_hash,
        }
    )

    return enriched.model_copy(
        update={
            "document_metadata": document_metadata,
            "metadata": enriched_metadata
            | {
                "canonical_json_path": str(canonical_path),
                "manifest_path": str(manifest_path),
                "quality_report_path": str(quality_report_path),
            },
        }
    )





def from_opendataloader_result(
    markdown_content: str,
    *,
    tables: list[dict[str, Any]] | None = None,
    figures: list[dict[str, Any]] | None = None,
    formulas: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> StructuredExtractionResult:
    """Convert OpenDataLoader extraction output into the canonical payload.

    OpenDataLoader outputs Markdown + JSON with bounding boxes. This function
    parses those outputs and converts them into the canonical structured format.

    Args:
        markdown_content: Extracted markdown text from OpenDataLoader.
        tables: List of table element dictionaries from OpenDataLoader JSON.
        figures: List of figure element dictionaries from OpenDataLoader JSON.
        formulas: List of formula element dictionaries from OpenDataLoader JSON.
        metadata: Optional additional metadata.

    Returns:
        Canonical structured extraction result.
    """
    # Convert table dicts to ExtractedTableElement
    table_elements: list[ExtractedTableElement] = []
    for index, table_dict in enumerate(tables or [], start=1):
        try:
            table_elements.append(
                ExtractedTableElement(
                    element_id=table_dict.get("element_id", f"table_{index}"),
                    page_number=table_dict.get("page_number"),
                    row_count=table_dict.get("row_count", 0),
                    column_count=table_dict.get("column_count", 0),
                    cells=table_dict.get("cells", []),
                    cell_metadata=table_dict.get("cell_metadata", []),
                    markdown=table_dict.get("markdown"),
                    caption=table_dict.get("caption"),
                    source_anchor_id=table_dict.get("source_anchor_id", f"table-{index}"),
                )
            )
        except Exception as e:
            logger.warning("Failed to parse table element %d: %s", index, e)

    # Convert figure dicts to ExtractedFigureElement
    figure_elements: list[ExtractedFigureElement] = []
    for index, figure_dict in enumerate(figures or [], start=1):
        try:
            figure_elements.append(
                ExtractedFigureElement(
                    element_id=figure_dict.get("element_id", f"figure_{index}"),
                    page_number=figure_dict.get("page_number"),
                    image_path=figure_dict.get("image_path"),
                    image_format=figure_dict.get("image_format", "png"),
                    caption=figure_dict.get("caption"),
                    description=figure_dict.get("description"),
                    source_anchor_id=figure_dict.get("source_anchor_id", f"figure-{index}"),
                    is_partial=figure_dict.get("is_partial", False),
                    partial_reason_codes=figure_dict.get("partial_reason_codes", []),
                    metadata=figure_dict.get("metadata", {}),
                )
            )
        except Exception as e:
            logger.warning("Failed to parse figure element %d: %s", index, e)

    # Convert formula dicts to ExtractedEquationElement
    equation_elements: list[ExtractedEquationElement] = []
    for index, formula_dict in enumerate(formulas or [], start=1):
        try:
            equation_elements.append(
                ExtractedEquationElement(
                    element_id=formula_dict.get("element_id", f"equation_{index}"),
                    latex=formula_dict.get("latex", ""),
                    raw_text=formula_dict.get("raw_text"),
                    source_anchor_id=formula_dict.get("source_anchor_id", f"equation-{index}"),
                    normalized_text=formula_dict.get("normalized_text", formula_dict.get("latex", "")),
                    equation_type=formula_dict.get("equation_type", "latex"),
                    display_mode=formula_dict.get("display_mode", "display"),
                    page_number=formula_dict.get("page_number"),
                )
            )
        except Exception as e:
            logger.warning("Failed to parse formula element %d: %s", index, e)

    # Build marker lines for tables and figures (equations already in markdown if LaTeX)
    marker_lines: list[str] = []
    marker_lines.extend(_build_table_marker(table) for table in table_elements)
    marker_lines.extend(_build_figure_marker(figure) for figure in figure_elements)
    # Only add equation markers if not already embedded in markdown as LaTeX
    for equation in equation_elements:
        if equation.latex and not (equation.latex.startswith("$$") or equation.latex.startswith("\\[")):
            marker_lines.append(_build_equation_marker(equation))

    content = markdown_content
    if marker_lines:
        content = f"{content.rstrip()}\n\n" + "\n".join(marker_lines) + "\n"

    result_metadata = metadata or {}

    return build_structured_extraction_result(
        content=content,
        tables=table_elements,
        figures=figure_elements,
        equations=equation_elements,
        metadata=result_metadata,
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


__all__ = [
    "DocumentMetadataContract",
    "ExtractedEquationElement",
    "ExtractedFigureElement",
    "ExtractedTableElement",
    "ExtractionQualityReport",
    "PageMetadataContract",
    "StructuredExtractionResult",
    "build_canonical_output",
    "build_structured_extraction_result",
    "evaluate_quality_gates",
    "from_opendataloader_result",
    "persist_canonical_output",
    "persist_equations_from_extraction",
    "persist_figures_from_extraction",
    "persist_output_contracts",
    "persist_output_manifest",
    "persist_quality_report",
    "persist_tables_from_extraction",
    "read_cached_artifacts",
]
