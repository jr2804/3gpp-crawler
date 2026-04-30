"""TDoc to Markdown conversion operations.

This module provides TDoc-specific conversion functionality using OpenDataLoader.
No wrapper layers - direct use of OpenDataLoader output files.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import opendataloader_pdf

from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.extraction.conversion import ensure_pdf
from tdoc_crawler.extraction.fetch_tdoc import fetch_spec_files, fetch_tdoc_files
from tdoc_crawler.extraction.metrics import MetricType, get_metrics_tracker, timed_operation
from tdoc_crawler.extraction.profiles import DEFAULT_EXTRACTION_PROFILE, ExtractionProfile
from tdoc_crawler.models.workspaces import SourceKind
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec
from tdoc_crawler.utils.async_helpers import run_async
from tdoc_crawler.utils.normalization import normalize_tdoc_id
from tdoc_crawler.workspaces import (
    checkout_spec_to_workspace,
)

logger = logging.getLogger(__name__)

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
        tables.extend(item for item in items if isinstance(item, dict) and item.get("type") == "table")
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to extract tables from JSON: %s", e)
    return tables


def _extract_figures_from_opendataloader_json(json_path: Path) -> list[ExtractedFigure]:
    """Extract figures/images from opendataloader JSON output."""
    figures: list[ExtractedFigure] = []
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("results", [])
        figures.extend(item for item in items if isinstance(item, dict) and item.get("type") in ("image", "figure"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to extract figures from JSON: %s", e)
    return figures


def _extract_formulas_from_opendataloader_json(json_path: Path) -> list[ExtractedEquation]:
    """Extract formulas/equations from opendataloader JSON output."""
    equations: list[ExtractedEquation] = []
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("results", [])
        equations.extend(item for item in items if isinstance(item, dict) and item.get("type") == "formula")
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to extract formulas from JSON: %s", e)
    return equations


def _ensure_converted(
    document_id: str,
    output_dir: Path,
    *,
    primary_path: Path | None = None,
    force: bool = False,
    config: OpendataloaderConfig | None = None,
    source_pdf: Path | None = None,
) -> tuple[str, Path, str]:
    """Ensure markdown conversion exists for a document.

    Handles cache checking and OpenDataLoader conversion.
    Writes only raw content to cache (no metadata) for consistency across callers.

    Args:
        document_id: Document identifier (e.g., "S4-260001")
        output_dir: Directory for output files (.md, .json).
        primary_path: Optional explicit path to the source document.
            If not provided, it will be fetched as a TDoc.
        force: Force reconversion even if cached
        config: Optional OpenDataLoader configuration
        source_pdf: If provided, opendataloader processes this PDF instead of the
            original document. This ensures all profiles use the same PDF that was
            generated for the wiki dir.

    Returns:
        Tuple of (raw_markdown, json_path, normalized_id).
        json_path may not exist on disk — caller must check.

    Raises:
        ConversionError: If no document files found or conversion fails.
    """
    normalized_id = normalize_tdoc_id(document_id) or document_id

    if primary_path is None:
        tdoc_files = fetch_tdoc_files(normalized_id, force_download=force)
        primary = tdoc_files.primary_path
    else:
        primary = primary_path

    if primary is None:
        msg = f"No document files found for {document_id}"
        raise ConversionError(msg)

    md_file = output_dir / f"{primary.stem}.md"
    json_file = output_dir / f"{primary.stem}.json"

    if md_file.exists() and not force:
        markdown_content = md_file.read_text(encoding="utf-8")
    else:
        # Use the provided PDF (from wiki dir) or fall back to original source
        input_file = source_pdf if source_pdf is not None and source_pdf.exists() else primary
        markdown_content, _ = _run_opendataloader(input_file, output_dir, config=config)
        md_file.write_text(markdown_content, encoding="utf-8")

    return markdown_content, json_file, normalized_id


def convert_for_wiki(
    document_id: str,
    wiki_source_dir: Path,
    *,
    source_kind: SourceKind = SourceKind.TDOC,
    source_path: str | Path | None = None,
    profile: ExtractionProfile | None = None,
    force: bool = False,
) -> Path | None:
    """Convert a document for wiki ingestion using the specified profile.

    For default and advanced profiles, always generates the wiki PDF first
    (via ensure_pdf), then opendataloader processes that same PDF. This ensures
    consistency: the source_pdf in JSON points to the actual PDF that was analyzed.

    Args:
        document_id: Document identifier (TDoc ID or spec number).
        wiki_source_dir: Target directory under wiki/<workspace>/sources/<doc-id>/.
        source_kind: Kind of source (TDOC, SPEC, etc.).
        source_path: Optional explicit path to the source document/directory.
        profile: Extraction profile to use. Defaults to DEFAULT_EXTRACTION_PROFILE.
        force: Force reconversion.

    Returns:
        Path to the primary output file (PDF for pdf-only, MD for default/advanced),
        or None if conversion fails.
    """
    if profile is None:
        profile = DEFAULT_EXTRACTION_PROFILE

    wiki_source_dir.mkdir(parents=True, exist_ok=True)

    # Resolve files based on kind
    if source_kind == SourceKind.SPEC:
        # For specs, source_path should be the checkout directory.
        # If the path doesn't exist, auto-checkout the spec first.
        # The document_id may contain a -REL suffix (e.g., "21905-REL19.0.0").
        spec_rel_match = re.match(r"^(\d+(?:\.\d+)?)(?:-REL(.+))?$", document_id)
        spec_number = spec_rel_match.group(1) if spec_rel_match else document_id
        spec_release = spec_rel_match.group(2) if spec_rel_match and spec_rel_match.group(2) else "latest"

        actual_path: Path | None = None
        if source_path and Path(str(source_path)).exists():
            actual_path = Path(str(source_path))
        else:
            # Spec not checked out yet — check it out now
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

        doc_files = fetch_spec_files(actual_path)
    else:
        # TDoc pipeline (default)
        normalized_id = normalize_tdoc_id(document_id)
        doc_files = fetch_tdoc_files(normalized_id, force_download=force)

    primary = doc_files.primary_path
    if primary is None:
        msg = f"No document files found for {document_id}"
        raise ConversionError(msg)

    if profile == ExtractionProfile.PDF_ONLY:
        return ensure_pdf(primary, wiki_source_dir, force=force)

    # default or advanced: generate wiki PDF first, then opendataloader processes it
    pdf_path = ensure_pdf(primary, wiki_source_dir, force=force)

    config = OpendataloaderConfig(
        hybrid="docling-fast",
        hybrid_mode="full" if profile == ExtractionProfile.ADVANCED else None,
    )
    markdown_content, json_path, _ = _ensure_converted(
        document_id,
        wiki_source_dir,
        primary_path=primary,
        force=force,
        config=config,
        source_pdf=pdf_path,
    )

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
    except (OSError, json.JSONDecodeError, KeyError, IndexError) as e:
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
        # For standalone conversion, we use the default AI directory next to the source
        # We need to find the primary path first
        normalized_id = normalize_tdoc_id(document_id)
        tdoc_files = fetch_tdoc_files(normalized_id, force_download=force)
        primary = tdoc_files.primary_path
        if primary is None:
            msg = f"No document files found for {normalized_id}"
            raise ConversionError(msg)

        ai_dir = _get_ai_directory(primary)
        markdown_content, json_file, normalized_id = _ensure_converted(
            document_id,
            ai_dir,
            primary_path=primary,
            force=force,
            config=config,
        )

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


def _is_valid_pdf(file_path: Path) -> bool:
    """Check if a file is a valid PDF by reading its magic bytes."""
    if not file_path.exists() or file_path.stat().st_size == 0:
        return False
    try:
        with file_path.open("rb") as f:
            header = f.read(8)
        return header.startswith(b"%PDF-")
    except OSError:
        return False


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
        ConversionError: If conversion fails or input is not a valid PDF.
    """
    # Validate input is a proper PDF before attempting conversion
    if not _is_valid_pdf(input_file):
        msg = (
            f"Input file is not a valid PDF: {input_file.name} "
            f"(size={input_file.stat().st_size if input_file.exists() else 'N/A'}, "
            f"exists={input_file.exists()})"
        )
        raise ConversionError(
            msg,
        )

    config = config or OpendataloaderConfig()
    formats = "markdown,json,markdown-with-images"

    max_retries = 3
    retry_delays = [1, 3]
    last_exc: Exception | None = None

    for attempt in range(max_retries):
        try:
            opendataloader_pdf.convert(
                input_path=[str(input_file)],
                output_dir=str(output_dir),
                format=formats,
                quiet=True,
                **config.to_convert_kwargs(),
            )
            break
        except (OSError, ConnectionError) as e:
            last_exc = e
            if attempt < max_retries - 1:
                delay = retry_delays[attempt]
                logger.warning(
                    "OpenDataLoader attempt %d/%d failed for %s, retrying in %ds: %s",
                    attempt + 1,
                    max_retries,
                    input_file.name,
                    delay,
                    e,
                )
                time.sleep(delay)
        except Exception as e:
            msg = f"OpenDataLoader conversion failed for {input_file.name}: {e}"
            logger.exception(msg)
            raise ConversionError(msg) from e
    else:
        msg = f"OpenDataLoader conversion failed after {max_retries} attempts for {input_file.name}: {last_exc}"
        logger.error(msg)
        raise ConversionError(msg) from last_exc

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
