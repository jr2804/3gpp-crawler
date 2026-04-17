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

from threegpp_ai.config import AiConfig, ExtractionProfile
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

_PROFILE_PRESETS: dict[ExtractionProfile, dict[str, bool]] = {
    "default": {"ocr": True, "layout": True, "tables": True, "figures": True, "equations": True, "enrichment": False},
    "balanced": {"ocr": True, "layout": True, "tables": True, "figures": True, "equations": True, "enrichment": True},
    "optimum": {"ocr": True, "layout": True, "tables": True, "figures": True, "equations": True, "enrichment": True},
    "custom": {"ocr": True, "layout": True, "tables": True, "figures": True, "equations": True, "enrichment": True},
}


def _score_document_complexity(file_path: Path) -> int:
    """Return deterministic complexity score used for auto profile selection."""
    score = 0
    suffix = file_path.suffix.lower()
    size_mb = file_path.stat().st_size / (1024 * 1024)

    if suffix == ".pdf":
        score += 1
    elif suffix in OFFICE_FORMATS:
        score += 2

    if size_mb >= 20:
        score += 2
    elif size_mb >= 8:
        score += 1

    return score


def _auto_select_profile(file_path: Path) -> ExtractionProfile:
    """Select profile from static thresholds with no stochastic behavior."""
    score = _score_document_complexity(file_path)
    if score >= 4:
        return "optimum"
    if score >= 2:
        return "balanced"
    return "default"


def resolve_extraction_policy(
    file_path: Path,
    *,
    profile: str | None = None,
    ai_config: AiConfig | None = None,
    custom_extract_ocr: bool | None = None,
    custom_extract_layout: bool | None = None,
    custom_extract_tables: bool | None = None,
    custom_extract_figures: bool | None = None,
    custom_extract_equations: bool | None = None,
    custom_extract_enrichment: bool | None = None,
) -> tuple[ExtractionProfile, dict[str, bool]]:
    """Resolve selected profile and effective extraction settings."""
    config = ai_config or AiConfig()
    selected = profile if profile is not None else config.extraction_profile

    if selected is None:
        selected = _auto_select_profile(file_path)

    profile_value: ExtractionProfile = selected  # type: ignore[assignment]
    if profile_value != "custom":
        return profile_value, dict(_PROFILE_PRESETS[profile_value])

    effective = {
        "ocr": config.custom_extract_ocr if custom_extract_ocr is None else custom_extract_ocr,
        "layout": config.custom_extract_layout if custom_extract_layout is None else custom_extract_layout,
        "tables": config.custom_extract_tables if custom_extract_tables is None else custom_extract_tables,
        "figures": config.custom_extract_figures if custom_extract_figures is None else custom_extract_figures,
        "equations": config.custom_extract_equations if custom_extract_equations is None else custom_extract_equations,
        "enrichment": config.custom_extract_enrichment if custom_extract_enrichment is None else custom_extract_enrichment,
    }
    return profile_value, effective


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
    effective_settings: dict[str, bool] | None = None,
) -> DocumentConverter:
    """Create a DocumentConverter for PDF extraction.

    Args:
        vlm_options: Optional VLM features. If None, uses StandardPdfPipeline with
            enhanced options (table structure, accelerator). If any VLM feature is
            enabled, uses VlmPipeline with Granite Docling.
        accelerator_config: Optional accelerator settings for GPU/CPU and threading.
            If None, uses defaults (auto device, 4 threads).
        effective_settings: Effective profile settings controlling OCR/layout/table and enrichment behavior.

    Returns:
        Configured DocumentConverter for PDF processing.
    """
    accel = accelerator_config or AcceleratorConfig()
    accelerator_options = accel.to_accelerator_options()
    settings = effective_settings or _PROFILE_PRESETS["default"]

    if vlm_options is None or (not vlm_options.enable_picture_description and not vlm_options.enable_formula_enrichment):
        # Standard pipeline with enhanced options
        options = ThreadedPdfPipelineOptions(
            do_table_structure=settings["tables"],
            table_structure_options=TableStructureOptions(do_cell_matching=True),
            accelerator_options=accelerator_options,
            do_formula_enrichment=settings["equations"] and settings["enrichment"],
            code_formula_options=CodeFormulaVlmOptions.from_preset("granite_docling"),
        )
        if hasattr(options, "do_ocr"):
            options.do_ocr = settings["ocr"]
        if hasattr(options, "do_layout"):
            options.do_layout = settings["layout"]
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
    effective_settings: dict[str, bool] | None = None,
) -> StructuredExtractionResult:
    """Convert non-PDF document to structured extraction via LibreOffice.

    Args:
        file_path: Path to source document (DOCX, DOC, etc.).
        ai_dir: Optional .ai directory for artifact storage.
        doc_stem: Document stem for naming artifacts.
        extract_types: Optional set of artifact types to extract/persist.
        vlm_options: Optional VLM features for PDF extraction.
        accelerator_config: Optional accelerator settings.
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
            converter_docling = _create_pdf_converter(
                vlm_options=vlm_options,
                accelerator_config=accelerator_config,
                effective_settings=effective_settings,
            )
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
    profile: str | None = None,
    custom_extract_ocr: bool | None = None,
    custom_extract_layout: bool | None = None,
    custom_extract_tables: bool | None = None,
    custom_extract_figures: bool | None = None,
    custom_extract_equations: bool | None = None,
    custom_extract_enrichment: bool | None = None,
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
        metadata: Optional document metadata passed through to the result
            envelope for downstream consumers.
        force: If True, re-extract even if cached artifacts exist.
        extract_types: Optional set of artifact types to extract/persist.
            If None, extracts all types. Supported types: "tables", "figures", "equations".
        vlm_options: Optional VLM features for extraction. Enables picture description
            and/or formula enrichment using VLM pipelines. If None, uses standard
            extraction with formula enrichment.
        accelerator_config: Optional accelerator settings for GPU/CPU and threading.
        profile: Extraction profile override.
        custom_extract_ocr: Optional custom OCR toggle.
        custom_extract_layout: Optional custom layout toggle.
        custom_extract_tables: Optional custom table extraction toggle.
        custom_extract_figures: Optional custom figure extraction toggle.
        custom_extract_equations: Optional custom equation extraction toggle.
        custom_extract_enrichment: Optional custom enrichment toggle.

    Returns:
        StructuredExtractionResult with content, tables, figures, and equations.

    Raises:
        ExtractionError: If the source file does not exist or extraction fails.
        ConversionError: If Office document conversion fails.
    """
    if not file_path.exists():
        raise ExtractionError(f"Source file does not exist: {file_path}")

    if not _is_supported_format(file_path):
        raise ExtractionError(f"Unsupported file format: {file_path.suffix}")

    selected_profile, effective_settings = resolve_extraction_policy(
        file_path,
        profile=profile,
        custom_extract_ocr=custom_extract_ocr,
        custom_extract_layout=custom_extract_layout,
        custom_extract_tables=custom_extract_tables,
        custom_extract_figures=custom_extract_figures,
        custom_extract_equations=custom_extract_equations,
        custom_extract_enrichment=custom_extract_enrichment,
    )

    if extract_types is None:
        extract_types = set()
        if effective_settings["tables"]:
            extract_types.add("tables")
        if effective_settings["figures"]:
            extract_types.add("figures")
        if effective_settings["equations"]:
            extract_types.add("equations")

    merged_metadata: dict[str, Any] = {
        "extraction_profile": selected_profile,
        "effective_extraction_settings": effective_settings,
    }
    if metadata:
        merged_metadata.update(metadata)

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
                metadata=merged_metadata | {"cache_hit": True},
            )

    # No valid cache found, perform fresh extraction
    if file_path.suffix.lower() == ".pdf":
        effective_vlm = vlm_options
        if not effective_settings["enrichment"]:
            effective_vlm = None

        converter = _create_pdf_converter(
            vlm_options=effective_vlm,
            accelerator_config=accelerator_config,
            effective_settings=effective_settings,
        )
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
            effective_settings=effective_settings,
        )

    extraction = extraction.model_copy(update={"metadata": merged_metadata | dict(extraction.metadata)})

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
    "resolve_extraction_policy",
]
