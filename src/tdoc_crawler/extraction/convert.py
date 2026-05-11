"""Document to structured Markdown/JSON conversion using Docling.

After checkout/fetch, all source types (TDocs, Specs, Other) are treated as
generic documents.  Three extraction profiles are supported:

- **pdf-only**:  Convert to PDF only (via LibreOffice).  No structured extraction.
- **default**:   PDF → Docling structured output (Markdown + JSON).
- **advanced**:  Same as default + picture descriptions, code/formula enrichment.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from pathlib import Path
from typing import Any, Literal

from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc.base import ImageRefMode

from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.extraction.conversion import ensure_pdf
from tdoc_crawler.extraction.fetch_tdoc import fetch_spec_files as fetch_spec_files_from_tdoc
from tdoc_crawler.extraction.fetch_tdoc import fetch_tdoc_files
from tdoc_crawler.extraction.metrics import MetricType, get_metrics_tracker, timed_operation
from tdoc_crawler.extraction.profiles import DEFAULT_EXTRACTION_PROFILE, ExtractionProfile
from tdoc_crawler.models.workspaces import SourceKind
from tdoc_crawler.utils.async_helpers import run_async
from tdoc_crawler.utils.normalization import normalize_tdoc_id
from tdoc_crawler.workspaces import checkout_spec_to_workspace

logger = logging.getLogger(__name__)

__all__ = [
    "ConversionError",
    "DoclingConfig",
    "convert_for_wiki",
]


class ConversionError(Exception):
    """Raised when document conversion fails."""


class DoclingConfig:
    """Configuration for Docling conversion.

    Args:
        figures_mode: How to handle figures in output.
            - ``"embed"``: Placeholder in markdown, data in JSON (default).
            - ``"reference"``: Extract figure images, reference via URI in markdown.
        tables_mode: How to handle tables in output.
            - ``"embed"``: Tables embedded in markdown (default).
            - ``"csv"``: Tables exported as separate CSV files alongside the JSON.
        device: Accelerator device for Docling models.
            - ``"auto"``: Auto-detect (CUDA if available, else CPU).
            - ``"cpu"``: Force CPU-only (avoids CUDA warnings).
            - ``"cuda"``: Force NVIDIA CUDA GPU.
            - ``"mps"``: Force Apple Metal Performance Shaders.
    """

    def __init__(
        self,
        figures_mode: Literal["embed", "reference"] = "embed",
        tables_mode: Literal["embed", "csv"] = "embed",
        device: Literal["auto", "cpu", "cuda", "mps"] = "auto",
    ) -> None:
        self.figures_mode = figures_mode
        self.tables_mode = tables_mode
        self.device = device


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

    Handles the source-kind-specific checkout/fetch, then returns
    the primary document path for generic conversion.

    Args:
        document_id: Document identifier.
        source_kind: Type of source.
        source_path: Optional explicit path to source.
        force: Force re-download.

    Returns:
        Path to the primary source document.

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
                checkout_spec_to_workspace(
                    spec_number,
                    checkout_base,
                    release=spec_release,
                ),
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
# Docling pipeline configuration
# ---------------------------------------------------------------------------


def _build_pipeline_options(
    profile: ExtractionProfile,
    *,
    device: Literal["auto", "cpu", "cuda", "mps"] = "auto",
) -> PdfPipelineOptions:
    """Build Docling ``PdfPipelineOptions`` for the given extraction profile.

    Args:
        profile: Extraction profile level.
        device: Accelerator device (auto, cpu, cuda, mps).

    Returns:
        Configured ``PdfPipelineOptions``.
    """
    pipeline_opts = PdfPipelineOptions(
        accelerator_options=AcceleratorOptions(device=device),
    )

    if profile == ExtractionProfile.ADVANCED:
        pipeline_opts.do_picture_description = True
        pipeline_opts.do_code_enrichment = True
        pipeline_opts.do_formula_enrichment = True

    return pipeline_opts


# ---------------------------------------------------------------------------
# Core Docling conversion
# ---------------------------------------------------------------------------


def _run_docling(
    input_file: Path,
    output_dir: Path,
    *,
    profile: ExtractionProfile,
    config: DoclingConfig | None = None,
) -> tuple[str, Path, int]:
    """Run Docling conversion on a document file.

    Args:
        input_file: Path to the input document (typically PDF).
        output_dir: Directory for output files (``.md``, ``.json``).
        profile: Extraction profile to use.
        config: Optional Docling configuration.

    Returns:
        Tuple of ``(markdown_content, json_path, page_count)``.

    Raises:
        ConversionError: If conversion fails.
    """
    config = config or DoclingConfig()
    pipeline_opts = _build_pipeline_options(profile, device=config.device)

    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts),
        },
    )

    try:
        result = converter.convert(input_file)
    except Exception as e:
        msg = f"Docling conversion failed for {input_file.name}: {e}"
        logger.exception(msg)
        raise ConversionError(msg) from e

    stem = input_file.stem
    md_path = output_dir / f"{stem}.md"
    json_path = output_dir / f"{stem}.json"

    # --- Export markdown ---
    if config.figures_mode == "reference":
        result.document.save_as_markdown(
            md_path,
            image_mode=ImageRefMode.REFERENCED,
        )
        markdown_content = md_path.read_text(encoding="utf-8")
    else:
        markdown_content = result.document.export_to_markdown(
            image_mode=ImageRefMode.PLACEHOLDER,
        )
        md_path.write_text(markdown_content, encoding="utf-8")

    # --- Export JSON (DoclingDocument schema) ---
    result.document.save_as_json(json_path)

    # Enrich JSON with extraction metadata
    _enrich_json_metadata(json_path, profile, input_file)

    # --- Export tables as CSV if requested ---
    if config.tables_mode == "csv":
        _export_tables_as_csv(result, output_dir, stem)

    page_count = getattr(result.input, "page_count", 0) or 0

    return markdown_content, json_path, page_count


def _enrich_json_metadata(json_path: Path, profile: ExtractionProfile, source_file: Path) -> None:
    """Add extraction metadata to the DoclingDocument JSON output."""
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data["extraction_profile"] = profile.value
            data["source_file"] = str(source_file)
        json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to enrich JSON metadata: %s", e)


def _export_tables_as_csv(result: Any, output_dir: Path, stem: str) -> None:
    """Export tables from DoclingDocument as CSV files.

    Each table is written to ``{stem}_table_{index}.csv`` in the output directory.
    """
    doc = result.document
    tables = doc.tables if doc else []

    for i, table_item in enumerate(tables):
        try:
            tbl_data = table_item.data
            if tbl_data is None or not hasattr(tbl_data, "grid"):
                continue

            csv_path = output_dir / f"{stem}_table_{i}.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                for row in tbl_data.grid:
                    cells = [cell.text if hasattr(cell, "text") else str(cell) for cell in (row.cells if hasattr(row, "cells") else [])]
                    writer.writerow(cells)

        except Exception as e:
            logger.warning("Failed to export table %d as CSV: %s", i, e)


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
) -> Path | None:
    """Convert a document for wiki ingestion using the specified profile.

    For **default** and **advanced** profiles the pipeline is:
    1. Convert to PDF (via LibreOffice) if not already PDF.
    2. Feed the PDF to Docling for structured extraction.
    3. Write Markdown + JSON to *wiki_source_dir*.

    Args:
        document_id: Document identifier (TDoc ID, spec number, etc.).
        wiki_source_dir: Target directory under ``wiki/<workspace>/sources/<doc-id>/``.
        source_kind: Kind of source (TDOC, SPEC, OTHER).
        source_path: Optional explicit path to the source document/directory.
        profile: Extraction profile. Defaults to ``DEFAULT_EXTRACTION_PROFILE``.
        force: Force reconversion.
        docling_config: Optional Docling-specific configuration (figure/table modes).

    Returns:
        Path to the primary output file (PDF for pdf-only, MD for default/advanced),
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

    # Step 2b: default/advanced → ensure PDF first, then Docling
    pdf_path = ensure_pdf(primary, wiki_source_dir, force=force)

    with timed_operation(get_metrics_tracker(), document_id, MetricType.CONVERSION):
        _, json_path, _ = _run_docling(
            pdf_path,
            wiki_source_dir,
            profile=profile,
            config=docling_config,
        )

    # Write final markdown
    md_file = wiki_source_dir / f"{primary.stem}.md"
    if not md_file.exists():
        # _run_docling already wrote it; this is a safety net
        pass

    return md_file
