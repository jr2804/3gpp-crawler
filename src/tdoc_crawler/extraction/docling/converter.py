"""Docling converter — cached instances, structured extraction (MD + JSON)."""

from __future__ import annotations

import csv
import json
import logging
import os
from pathlib import Path
from typing import Any, Literal

from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter, PdfFormatOption, WordFormatOption
from docling_core.types.doc.base import ImageRefMode

from tdoc_crawler.extraction.docling.filter import _DOCLING_PIPELINE_LOGGER, _DoclingBadAllocFilter
from tdoc_crawler.extraction.docling.pipeline import _build_pipeline_options
from tdoc_crawler.extraction.errors import ConversionError
from tdoc_crawler.extraction.profiles import ExtractionProfile

logger = logging.getLogger(__name__)

# Reusing the same converter across documents avoids reloading model weights
# (~700 MB) for every file, eliminating repeated "Loading weights" tqdm bars
# and saving several seconds per document.
_converter_cache: dict[tuple, DocumentConverter] = {}


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


def _get_or_create_converter(
    profile: ExtractionProfile,
    *,
    device: Literal["auto", "cpu", "cuda", "mps"] = "auto",
    docx_direct: bool = False,
) -> DocumentConverter:
    """Return a cached ``DocumentConverter`` matching *profile*, *device*, and *docx_direct*.

    Creates a new converter on first call (or when the key changes) and
    suppresses the noisy tqdm "Loading weights" progress bars during creation.
    """
    key = (profile, device, docx_direct)
    if key in _converter_cache:
        return _converter_cache[key]

    pipeline_opts = _build_pipeline_options(profile, device=device, docx_direct=docx_direct)

    format_options: dict[InputFormat, Any] = {
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts),
    }
    if docx_direct:
        format_options[InputFormat.DOCX] = WordFormatOption(pipeline_options=pipeline_opts)

    # Suppress tqdm "Loading weights" bars during model initialisation.
    old_tqdm = os.environ.get("TQDM_DISABLE")
    os.environ["TQDM_DISABLE"] = "1"
    try:
        converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF, InputFormat.DOCX],
            format_options=format_options,
        )
    finally:
        if old_tqdm is None:
            os.environ.pop("TQDM_DISABLE", None)
        else:
            os.environ["TQDM_DISABLE"] = old_tqdm

    _converter_cache.clear()
    _converter_cache[key] = converter
    return converter


def _run_docling(
    input_file: Path,
    output_dir: Path,
    *,
    profile: ExtractionProfile,
    config: DoclingConfig | None = None,
    docx_direct: bool = False,
) -> tuple[str, Path, int]:
    """Run Docling conversion on a document file.

    Args:
        input_file: Path to the input document (PDF, or DOCX if docx_direct).
        output_dir: Directory for output files (``.md``, ``.json``).
        profile: Extraction profile to use.
        config: Optional Docling configuration.
        docx_direct: Feed .docx/.doc directly to Docling (skip PDF step).

    Returns:
        Tuple of ``(markdown_content, json_path, page_count)``.

    Raises:
        ConversionError: If conversion fails.
    """
    config = config or DoclingConfig()

    converter = _get_or_create_converter(
        profile,
        device=config.device,
        docx_direct=docx_direct,
    )

    # Suppress noisy std::bad_alloc errors from Docling's C++ backend.
    bad_alloc_filter = _DoclingBadAllocFilter()
    docling_pipeline_log = logging.getLogger(_DOCLING_PIPELINE_LOGGER)
    docling_pipeline_log.addFilter(bad_alloc_filter)

    try:
        result = converter.convert(input_file)
    except Exception as e:
        msg = f"Docling conversion failed for {input_file.name}: {e}"
        logger.exception(msg)
        raise ConversionError(msg) from e
    finally:
        docling_pipeline_log.removeFilter(bad_alloc_filter)

    stem = input_file.stem
    md_path = output_dir / f"{stem}.md"
    json_path = output_dir / f"{stem}.json"

    # --- Export markdown with figure images ---
    image_mode = ImageRefMode.PLACEHOLDER if config.figures_mode == "embed" else ImageRefMode.REFERENCED
    result.document.save_as_markdown(
        md_path,
        image_mode=image_mode,
    )
    markdown_content = md_path.read_text(encoding="utf-8")

    # --- Export JSON with metadata ---
    doc_data = result.document.export_to_dict()
    doc_data["extraction_profile"] = profile.value
    doc_data["source_file"] = str(input_file)
    json_path.write_text(
        json.dumps(doc_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # --- Export tables as CSV if requested ---
    if config.tables_mode == "csv":
        _export_tables_as_csv(result, output_dir, stem)

    page_count = getattr(result.input, "page_count", 0) or 0

    return markdown_content, json_path, page_count


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
