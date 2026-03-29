"""Unified, document-agnostic extraction pipeline.

This module provides a generic extraction interface that works with various document formats
(PDF, DOCX, DOC, etc.) without TDoc-specific metadata handling.

The functions:
* extract_document_structured: Main unified extraction function
* extract_document_text: Shared docling extraction logic
* _convert_office_to_pdf: Office format conversion helper
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from convert_lo import LibreOfficeFormat
from convert_lo.converter import Converter
from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    CodeFormulaVlmOptions,
    TableStructureOptions,
    ThreadedPdfPipelineOptions,
    VlmConvertOptions,
    VlmPipelineOptions,
)
from docling.document_converter import DocumentConverter, FormatOption
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
from docling.pipeline.vlm_pipeline import VlmPipeline
from tdoc_crawler.logging import get_logger

from threegpp_ai.models import ConversionError, ExtractionError
from threegpp_ai.operations.extraction_result import (
    StructuredExtractionResult,
    build_structured_extraction_result,
    from_docling_result,
    persist_equations_from_extraction,
    persist_figures_from_docling_result,
    persist_figures_from_extraction,
    persist_tables_from_extraction,
    read_cached_artifacts,
)
from threegpp_ai.operations.figure_descriptor import describe_figures

logger = get_logger(__name__)


@dataclass
class VlmOptions:
    """Optional VLM features for extraction.

    When any feature is enabled, the VlmPipeline is used instead of StandardPdfPipeline.
    VLM features require GPU but provide better picture descriptions and formula enrichment.
    """

    enable_picture_description: bool = False
    enable_formula_enrichment: bool = False


# Map of user-facing device strings to AcceleratorDevice enum values
_DEVICE_MAP: dict[str, AcceleratorDevice] = {
    "auto": AcceleratorDevice.AUTO,
    "cpu": AcceleratorDevice.CPU,
    "cuda": AcceleratorDevice.CUDA,
    "mps": AcceleratorDevice.MPS,
    "xpu": AcceleratorDevice.XPU,
}


@dataclass
class AcceleratorConfig:
    """Accelerator configuration for Docling document processing.

    Controls GPU/CPU device selection, thread count, and batch sizes.
    All fields have sensible defaults — Docling auto-detects CUDA when available.

    Attributes:
        device: Compute device — one of: auto, cpu, cuda, mps, xpu, or cuda:N.
        num_threads: Thread count for CPU-bound operations.
        batch_size: Unified batch size for OCR, layout, and table structure.
            None leaves each at Docling's default. Higher values benefit GPU.
    """

    device: str = "auto"
    num_threads: int = 4
    batch_size: int | None = None

    def to_accelerator_options(self) -> AcceleratorOptions:
        """Convert to Docling's AcceleratorOptions."""
        device_lower = self.device.strip().lower()
        device = _DEVICE_MAP.get(device_lower, AcceleratorDevice.AUTO)
        return AcceleratorOptions(num_threads=self.num_threads, device=device)

    def apply_batch_sizes(self, options: ThreadedPdfPipelineOptions) -> None:
        """Apply batch size overrides to pipeline options if configured."""
        if self.batch_size is not None and self.batch_size > 0:
            options.ocr_batch_size = self.batch_size
            options.layout_batch_size = self.batch_size
            options.table_batch_size = max(1, self.batch_size // 16)


def _create_pdf_converter(
    vlm_options: VlmOptions | None = None,
    accelerator_config: AcceleratorConfig | None = None,
) -> DocumentConverter:
    """Create a DocumentConverter for PDF extraction.

    Args:
        vlm_options: Optional VLM features. If None, uses StandardPdfPipeline with
            enhanced options (table structure, accelerator). If any VLM feature is
            enabled, uses VlmPipeline with Granite Docling.
        accelerator_config: Optional accelerator settings for GPU/CPU and threading.
            If None, uses defaults (auto device, 4 threads).

    Returns:
        Configured DocumentConverter for PDF processing.
    """
    accel = accelerator_config or AcceleratorConfig()
    accelerator_options = accel.to_accelerator_options()

    if vlm_options is None or (not vlm_options.enable_picture_description and not vlm_options.enable_formula_enrichment):
        # Standard pipeline with enhanced options
        options = ThreadedPdfPipelineOptions(
            do_table_structure=True,
            table_structure_options=TableStructureOptions(do_cell_matching=True),
            accelerator_options=accelerator_options,
            do_formula_enrichment=True,
            code_formula_options=CodeFormulaVlmOptions.from_preset("granite_docling"),
        )
        accel.apply_batch_sizes(options)
        pdf_format_option = FormatOption(
            pipeline_cls=StandardPdfPipeline,
            backend=DoclingParseDocumentBackend,
            pipeline_options=options,
        )
    else:
        # VLM pipeline with Granite Docling
        vlm_opts = VlmPipelineOptions(
            do_picture_description=vlm_options.enable_picture_description,
            images_scale=2.0,
            generate_picture_images=True,
            vlm_options=VlmConvertOptions.from_preset("granite_docling"),
            accelerator_options=accelerator_options,
        )
        pdf_format_option = FormatOption(
            pipeline_cls=VlmPipeline,
            backend=DoclingParseDocumentBackend,
            pipeline_options=vlm_opts,
        )
    return DocumentConverter(format_options={InputFormat.PDF: pdf_format_option})


# File formats that need PDF conversion
OFFICE_FORMATS = {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}
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
) -> tuple[bool, str | None]:
    """Check if cached extraction exists (markdown + artifacts).

    Args:
        ai_dir: The .ai directory.
        doc_stem: Document stem.
        extract_types: Types to check: {"tables", "figures", "equations"}.

    Returns:
        Tuple of (has_valid_cache, cached_content or None).
        has_valid_cache: True if markdown exists and has artifacts.
        cached_content: Cached markdown content if available.
    """
    md_path = ai_dir / f"{doc_stem}.md"
    has_cached_md = md_path.exists()
    cached_content = None

    if has_cached_md:
        content = md_path.read_text(encoding="utf-8")
        if len(content) > 100:
            cached_content = content

    if cached_content:
        # Check for cached artifacts using folder-based storage
        cached = read_cached_artifacts(ai_dir, doc_stem)
        if cached is not None and (cached.tables or cached.figures or cached.equations):
            return True, cached_content

    return False, None


def _build_structured_from_result(
    result: Any,
    ai_dir: Path | None = None,
    doc_stem: str | None = None,
    extract_types: set[str] | None = None,
) -> StructuredExtractionResult:
    """Build structured extraction from docling result.

    Args:
        result: Object returned by docling DocumentConverter.convert().
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
        persisted = persist_figures_from_docling_result(result, figures_dir, doc_stem=doc_stem)
        figure_paths = {key: str(path) for key, path in persisted.items()}
        figure_descriptions = describe_figures(persisted, enabled=True)

    return from_docling_result(
        result,
        figure_paths=figure_paths,
        figure_descriptions=figure_descriptions,
    )


def _convert_via_libreoffice(
    file_path: Path,
    ai_dir: Path | None = None,
    doc_stem: str | None = None,
    extract_types: set[str] | None = None,
    vlm_options: VlmOptions | None = None,
    accelerator_config: AcceleratorConfig | None = None,
) -> StructuredExtractionResult:
    """Convert non-PDF document to structured extraction via LibreOffice.

    Args:
        file_path: Path to source document (DOCX, DOC, etc.).
        ai_dir: Optional .ai directory for artifact storage.
        doc_stem: Document stem for naming artifacts.
        extract_types: Optional set of artifact types to extract/persist.
        vlm_options: Optional VLM features for PDF extraction.
        accelerator_config: Optional accelerator settings.

    Returns:
        Structured extraction payload.

    Raises:
        ConversionError: If LibreOffice conversion fails.
    """
    try:
        converter = Converter()
        with tempfile.TemporaryDirectory() as tmpdir:
            conversion_result = converter.convert(file_path, LibreOfficeFormat.PDF, Path(tmpdir))
            converter_docling = _create_pdf_converter(vlm_options=vlm_options, accelerator_config=accelerator_config)
            docling_result = converter_docling.convert(str(conversion_result.output_path))
            return _build_structured_from_result(
                docling_result,
                ai_dir=ai_dir,
                doc_stem=doc_stem,
                extract_types=extract_types,
            )
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


def extract_document_structured(
    file_path: Path,
    metadata: dict[str, Any] | None = None,
    force: bool = False,
    extract_types: set[str] | None = None,
    vlm_options: VlmOptions | None = None,
    accelerator_config: AcceleratorConfig | None = None,
) -> StructuredExtractionResult:
    """Extract a document into a canonical structured payload.

    This is the main unified extraction function that handles:
    - PDF files: Direct extraction via docling
    - Office files (DOCX, DOC, etc.): Convert to PDF, then extract
    - Text files (TXT, MD): Direct extraction via docling

    Caching:
    - Checks for existing .md file in .ai subdirectory
    - Checks for folder-based artifacts (tables/, figures/, equations/)
    - Only re-extracts if force=True or cache miss

    Args:
        file_path: Path to the source document file.
        metadata: Optional document metadata (passed through but not
            processed by this function - use for RAGMetadata enrichment
            at a higher level).
        force: If True, re-extract even if cached artifacts exist.
        extract_types: Optional set of artifact types to extract/persist.
            If None, extracts all types. Supported types: "tables", "figures", "equations".
        vlm_options: Optional VLM features for extraction. Enables picture description
            and/or formula enrichment using VLM pipelines. If None, uses standard
            extraction with formula enrichment.
        accelerator_config: Optional accelerator settings for GPU/CPU and threading.

    Returns:
        StructuredExtractionResult with content, tables, figures, and equations.

    Raises:
        ExtractionError: If the source file does not exist or extraction fails.
        ConversionError: If Office document conversion fails.
    """
    if extract_types is None:
        extract_types = {"tables", "figures", "equations"}

    if not file_path.exists():
        raise ExtractionError(f"Source file does not exist: {file_path}")

    if not _is_supported_format(file_path):
        raise ExtractionError(f"Unsupported file format: {file_path.suffix}")

    ai_dir = _get_ai_directory(file_path)
    doc_stem = _get_doc_stem(file_path)

    # Check for cached extraction
    has_cache, cached_content = _check_cached_extraction(ai_dir, doc_stem, extract_types)
    if has_cache and cached_content is not None and not force:
        cached = read_cached_artifacts(ai_dir, doc_stem)
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

    # No valid cache found, perform fresh extraction
    if file_path.suffix.lower() == ".pdf":
        converter = _create_pdf_converter(vlm_options=vlm_options, accelerator_config=accelerator_config)
        result = converter.convert(str(file_path))
        extraction = _build_structured_from_result(
            result,
            ai_dir=ai_dir,
            doc_stem=doc_stem,
            extract_types=extract_types,
        )
    elif file_path.suffix.lower() in {".txt", ".md"}:
        converter = DocumentConverter()
        result = converter.convert(str(file_path))
        extraction = _build_structured_from_result(
            result,
            ai_dir=ai_dir,
            doc_stem=doc_stem,
            extract_types=extract_types,
        )
    else:
        # Office formats (DOCX, DOC, etc.) - convert to PDF first
        extraction = _convert_via_libreoffice(
            file_path,
            ai_dir=ai_dir,
            doc_stem=doc_stem,
            extract_types=extract_types,
            vlm_options=vlm_options,
            accelerator_config=accelerator_config,
        )

    # Ensure .ai directory exists
    ai_dir.mkdir(parents=True, exist_ok=True)

    # Save markdown (only if we don't have cached content)
    md_path = ai_dir / f"{doc_stem}.md"
    if not cached_content:
        md_path.write_text(extraction.content, encoding="utf-8")
        logger.info("Saved markdown: %s", md_path)
    # Persist artifacts
    _persist_extraction_artifacts(ai_dir, doc_stem, extraction, extract_types=extract_types)
    return extraction


def extract_document_text(
    file_path: Path,
    force: bool = False,
    vlm_options: VlmOptions | None = None,
    accelerator_config: AcceleratorConfig | None = None,
) -> str:
    """Extract plain text content from a document using docling.

    For office documents, first converts to PDF using convert-lo.
    Returns just the text content without structured artifacts.

    Args:
        file_path: Path to the document file.
        force: If True, re-extract even if cached markdown exists.
        vlm_options: Optional VLM features for extraction.
        accelerator_config: Optional accelerator settings for GPU/CPU and threading.

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
]
