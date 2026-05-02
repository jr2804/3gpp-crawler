"""TDoc to Markdown conversion operations.

This module provides TDoc-specific conversion functionality using OpenDataLoader.
No wrapper layers - direct use of OpenDataLoader output files.
"""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from pathlib import Path
from typing import Any

import opendataloader_pdf
from rich.console import Console

from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.database.oxyde_models import Specification as OxydeSpecification
from tdoc_crawler.database.oxyde_models import TDocMetadata as OxydeTDocMetadata
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.extraction.conversion import ensure_pdf
from tdoc_crawler.extraction.fetch_spec import fetch_spec_files
from tdoc_crawler.extraction.fetch_tdoc import _lookup_tdoc_in_db, fetch_tdoc_files
from tdoc_crawler.extraction.hybrid_server import ensure_hybrid_server
from tdoc_crawler.extraction.metrics import MetricType, get_metrics_tracker, timed_operation
from tdoc_crawler.extraction.profiles import DEFAULT_EXTRACTION_PROFILE, ExtractionProfile
from tdoc_crawler.models.workspaces import SourceKind
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec
from tdoc_crawler.utils.normalization import extract_base_spec_number, extract_release_suffix, normalize_spec_number, normalize_tdoc_id

logger = logging.getLogger(__name__)
console = Console()

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


class ConversionError(Exception):
    """Raised when document conversion fails."""

    pass


class OpendataloaderConfig:
    """Configuration for OpenDataLoader conversion."""

    def __init__(
        self,
        hybrid: str | None = None,
        hybrid_mode: str | None = None,
        page_range: str | None = None,
        workers: int | None = None,
    ) -> None:
        self.hybrid = hybrid
        self.hybrid_mode = hybrid_mode
        self.page_range = page_range
        self.workers = workers

    def to_convert_kwargs(self) -> dict[str, object]:
        """Convert config to kwargs for opendataloader_pdf.convert()."""
        kwargs: dict[str, object] = {}
        if self.hybrid is not None:
            kwargs["hybrid"] = self.hybrid
        if self.hybrid_mode is not None:
            kwargs["hybrid_mode"] = self.hybrid_mode
        if self.page_range is not None:
            kwargs["page_range"] = self.page_range
        if self.workers is not None:
            kwargs["workers"] = self.workers
        return kwargs


ExtractedTable = dict[str, object]
ExtractedFigure = dict[str, object]
ExtractedEquation = dict[str, object]
ExtractionResult = dict[str, object | list[ExtractedTable] | list[ExtractedFigure] | list[ExtractedEquation]]


def _format_tdoc_metadata(metadata: object) -> str:
    """Format TDoc metadata as a markdown header."""
    if not isinstance(metadata, dict):
        return ""
    lines = ["---", "title: TDoc Metadata", "---", ""]
    for key, value in metadata.items():
        lines.append(f"- **{key}**: {value}")
    return "\n".join(lines)


def _extract_tables_from_opendataloader_json(json_path: Path) -> list[ExtractedTable]:
    """Extract tables from opendataloader JSON output."""
    tables: list[ExtractedTable] = []
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("results", [])
        for item in items:
            if isinstance(item, dict) and item.get("type") == "table":
                tables.append(item)
    except Exception as e:
        logger.warning("Failed to extract tables from JSON: %s", e)
    return tables


def _extract_figures_from_opendataloader_json(json_path: Path) -> list[ExtractedFigure]:
    """Extract figures/images from opendataloader JSON output."""
    figures: list[ExtractedFigure] = []
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("results", [])
        for item in items:
            if isinstance(item, dict) and item.get("type") in ("image", "figure"):
                figures.append(item)
    except Exception as e:
        logger.warning("Failed to extract figures from JSON: %s", e)
    return figures


def _extract_formulas_from_opendataloader_json(json_path: Path) -> list[ExtractedEquation]:
    """Extract formulas/equations from opendataloader JSON output."""
    equations: list[ExtractedEquation] = []
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("results", [])
        for item in items:
            if isinstance(item, dict) and item.get("type") == "formula":
                equations.append(item)
    except Exception as e:
        logger.warning("Failed to extract formulas from JSON: %s", e)
    return equations


def _ensure_converted(
    document_id: str,
    force: bool = False,
    config: OpendataloaderConfig | None = None,
    source_pdf: Path | None = None,
    output_dir: Path | None = None,
) -> tuple[str, Path, str]:
    """Fetch TDoc and ensure markdown conversion exists.

    Handles file fetching, cache checking, and OpenDataLoader conversion.
    Writes only raw content to cache (no metadata) for consistency across callers.

    Args:
        document_id: TDoc identifier (e.g., "S4-260001")
        force: Force reconversion even if cached
        config: Optional OpenDataLoader configuration
        source_pdf: If provided, opendataloader processes this PDF instead of the
            original DOCX. This ensures all profiles use the same PDF that was
            generated for the wiki dir. When provided and exists, the fetch step
            is skipped entirely (the caller already resolved the document).
        output_dir: Directory for conversion artifacts. If None, uses a temp dir.

    Returns:
        Tuple of (raw_markdown, json_path, normalized_id).
        json_path may not exist on disk — caller must check.

    Raises:
        ConversionError: If no document files found or conversion fails.
    """
    normalized_id = normalize_tdoc_id(document_id)

    if source_pdf is not None and source_pdf.exists():
        primary = source_pdf
    else:
        tdoc_files = fetch_tdoc_files(normalized_id, force_download=force)
        primary = tdoc_files.primary_path
        if primary is None:
            raise ConversionError(f"No document files found for {normalized_id}")

    artifact_dir = output_dir or Path(tempfile.mkdtemp(prefix="3gpp-conv-"))
    artifact_dir.mkdir(parents=True, exist_ok=True)
    md_file = artifact_dir / f"{primary.stem}.md"
    json_file = artifact_dir / f"{primary.stem}.json"

    if md_file.exists() and not force:
        markdown_content = md_file.read_text(encoding="utf-8")
    else:
        markdown_content, _ = _run_opendataloader(primary, artifact_dir, config=config)
        md_file.write_text(markdown_content, encoding="utf-8")

    return markdown_content, json_file, normalized_id


async def _resolve_spec_metadata(spec_number: str) -> OxydeSpecification | None:
    """Look up specification metadata in the local database."""
    db_file = PathConfig().db_file
    async with SpecDatabase(db_file) as db:
        return await db._get_specification(spec_number)


def _enrich_with_metadata(
    markdown_content: str,
    json_path: Path,
    metadata: OxydeSpecification | OxydeTDocMetadata,
    *,
    source_kind: SourceKind,
    md_yaml_frontmatter: bool = True,
) -> str:
    """Inject document metadata into JSON and optionally prepend YAML frontmatter.

    JSON enrichment always happens. YAML frontmatter is controlled by
    *md_yaml_frontmatter*. Uses the Oxyde model's own serialization
    (model_dump) and field metadata (model_fields) — no hardcoded field names.
    """
    metadata_dict = metadata.model_dump()
    metadata_dict["kind"] = source_kind.value

    # Merge into JSON at top level
    if json_path.exists():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.update(metadata_dict)
            json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    if not md_yaml_frontmatter:
        return markdown_content

    # Generate YAML frontmatter from model fields
    lines = ["---"]
    for field_name in metadata.model_fields:
        value = metadata_dict.get(field_name)
        if value is not None:
            lines.append(f"{field_name}: {value}")
    lines.extend(["kind: " + source_kind.value, "---", ""])

    return "\n".join(lines) + markdown_content


def convert_for_wiki(
    document_id: str,
    wiki_source_dir: Path,
    *,
    source_kind: SourceKind = SourceKind.TDOC,
    profile: ExtractionProfile | None = None,
    force: bool = False,
    release: str | None = None,
    md_yaml_frontmatter: bool = True,
) -> Path | None:
    """Convert a document for wiki ingestion using the specified profile.

    For default and advanced profiles, always generates the wiki PDF first
    (via ensure_pdf), then opendataloader processes that same PDF. This ensures
    consistency: the source_pdf in JSON points to the actual PDF that was analyzed.

    Args:
        document_id: Document identifier (TDoc ID or spec number).
        wiki_source_dir: Target directory under wiki/<workspace>/sources/<doc-id>/.
        source_kind: Type of source document (TDOC or SPEC). Defaults to TDOC.
        profile: Extraction profile to use. Defaults to DEFAULT_EXTRACTION_PROFILE.
        force: Force reconversion.
        release: Release identifier for spec downloads (e.g., "19.0.0", "latest").

    Returns:
        Path to the primary output file (PDF for pdf-only, MD for default/advanced),
        or None if conversion fails.
    """
    if profile is None:
        profile = DEFAULT_EXTRACTION_PROFILE

    wiki_source_dir.mkdir(parents=True, exist_ok=True)

    # Resolve primary document based on source kind and collect metadata
    primary: Path | None = None
    metadata: OxydeSpecification | OxydeTDocMetadata | None = None
    if source_kind == SourceKind.SPEC:
        base_spec = extract_base_spec_number(document_id)
        normalized_id = normalize_spec_number(base_spec)
        # Resolve release: prefer suffix from document_id, fall back to explicit param
        resolved_release = extract_release_suffix(document_id) or release
        spec_files = fetch_spec_files(normalized_id, release=resolved_release, force_download=force)
        primary = spec_files.primary_path
        if primary is None:
            raise ConversionError(f"No document files found for spec {normalized_id}")
        metadata = asyncio.run(_resolve_spec_metadata(normalized_id))
    elif source_kind == SourceKind.TDOC:
        normalized_id = normalize_tdoc_id(document_id)
        tdoc_files = fetch_tdoc_files(normalized_id, force_download=force)
        primary = tdoc_files.primary_path
        if primary is None:
            raise ConversionError(f"No document files found for {normalized_id}")
        metadata = asyncio.run(_lookup_tdoc_in_db(normalized_id))
    else:
        # SourceKind.OTHER — resolve document but skip metadata enrichment
        normalized_id = document_id
        tdoc_files = fetch_tdoc_files(normalized_id, force_download=force)
        primary = tdoc_files.primary_path
        if primary is None:
            raise ConversionError(f"No document files found for {normalized_id}")

    if profile == ExtractionProfile.PDF_ONLY:
        pdf_path = ensure_pdf(primary, wiki_source_dir, force=force)
        return pdf_path

    # default or advanced: generate wiki PDF first, then opendataloader processes it
    pdf_path = ensure_pdf(primary, wiki_source_dir, force=force)

    config = OpendataloaderConfig(
        hybrid="docling-fast",
        hybrid_mode="full" if profile == ExtractionProfile.ADVANCED else None,
    )
    markdown_content, json_path, _ = _ensure_converted(document_id, force=force, config=config, source_pdf=pdf_path, output_dir=wiki_source_dir)

    # Enrich markdown and JSON with document metadata
    if metadata:
        markdown_content = _enrich_with_metadata(markdown_content, json_path, metadata, source_kind=source_kind, md_yaml_frontmatter=md_yaml_frontmatter)

    # Write markdown to wiki source dir
    md_file = wiki_source_dir / f"{primary.stem}.md"
    md_file.write_text(markdown_content, encoding="utf-8")

    # Add source_pdf reference to JSON if it exists (pdf_path is already in wiki dir)
    if json_path and json_path.exists():
        _add_source_pdf_to_json(json_path, pdf_path)

    return md_file


def _add_source_pdf_to_json(json_path: Path, pdf_path: Path) -> None:
    """Add source_pdf reference to opendataloader JSON output."""
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data["source_pdf"] = str(pdf_path)
        elif isinstance(data, list) and len(data) > 0:
            data[0]["source_pdf"] = str(pdf_path)
        json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to add source_pdf to JSON: %s", e)


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
) -> ExtractionResult:
    """Convert a TDoc to markdown using OpenDataLoader.

    Args:
        document_id: TDoc identifier (e.g., "S4-260001")
        output_file: Optional path to write markdown directly
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


def convert_tdoc_metadata(
    document_id: str,
    force: bool = False,
    config: OpendataloaderConfig | None = None,
) -> ExtractionResult:
    """Backward-compatible alias for convert_document_to_markdown."""
    return convert_document_to_markdown(document_id, force=force, config=config)


def _ensure_hybrid_server_if_needed(config: OpendataloaderConfig) -> None:
    """Auto-start the hybrid server if the config requires hybrid mode.

    Raises:
        ConversionError: If the hybrid server cannot be started.
    """
    if config.hybrid is None:
        return

    _manager, status = ensure_hybrid_server()
    if not status.running:
        msg = f"Hybrid server is not available: {status.error}"
        logger.error(msg)
        raise ConversionError(msg)


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
    _ensure_hybrid_server_if_needed(config)
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


# Alias maintained for backward compatibility
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
    return convert_document_to_markdown(document_id, force=force, config=config)


# Public alias for convert operation.
convert_tdoc_to_markdown = convert_document_to_markdown
