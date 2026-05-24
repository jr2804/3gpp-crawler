"""Document conversion orchestrator — PDF generation + structured extraction.

After checkout/fetch, all source types (TDocs, Specs, Other) are treated as
generic documents.  Four extraction profiles are supported:

- **pdf-only**:  Convert to PDF only (via LibreOffice).  No structured extraction.
- **markdown-only**:  Fast pymupdf4llm extraction (.md only, no ML).
- **default**:   PDF → Docling structured output (Markdown + JSON).
- **advanced**:  Same as default + picture descriptions, code/formula enrichment.
"""

from __future__ import annotations

import base64
import logging
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

import pandas as pd
import pdf_remote_converter.converter
import pdf_remote_converter.router
import pymupdf4llm
from convert_lo import LibreOfficeFormat
from convert_lo.converter import Converter
from markdownify import markdownify as md
from pdf_remote_converter.config import ProviderSettings

from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.extraction.docling import (
    DoclingConfig,
    _run_docling,
)
from tdoc_crawler.extraction.errors import ConversionError
from tdoc_crawler.extraction.fetch_tdoc import fetch_spec_files as fetch_spec_files_from_tdoc
from tdoc_crawler.extraction.fetch_tdoc import fetch_tdoc_files
from tdoc_crawler.extraction.metrics import MetricType, get_metrics_tracker, timed_operation
from tdoc_crawler.extraction.profiles import DEFAULT_EXTRACTION_PROFILE, ExtractionProfile, FiguresMode, SpreadsheetMode
from tdoc_crawler.models.workspaces import SourceKind
from tdoc_crawler.utils.async_helpers import run_async
from tdoc_crawler.utils.normalization import normalize_tdoc_id, sanitize_filename_stem
from tdoc_crawler.workspaces import checkout_spec_to_workspace

logger = logging.getLogger(__name__)

# File suffixes that can be fed directly to backends (no LibreOffice PDF step).
_DOCX_SUFFIXES: frozenset[str] = frozenset({".docx"})

# Formats treated as plain text/markdown that don't need LibreOffice conversion.
_TEXT_FORMATS: frozenset[str] = frozenset({".txt", ".md", ".html", ".htm"})

# Spreadsheet formats.
_SPREADSHEET_FORMATS: frozenset[str] = frozenset({".xls", ".xlsx", ".ods", ".csv"})


# ---------------------------------------------------------------------------
# PDF conversion (LibreOffice / remote API)
# ---------------------------------------------------------------------------

# File formats that need PDF conversion.
OFFICE_FORMATS: frozenset[str] = frozenset(
    {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".rtf", ".odt", ".odp", ".ods"},
)


class ConverterBackend(Enum):
    """PDF conversion backends."""

    LIBREOFFICE = "libreoffice"
    AUTO = "auto"


def _is_remote_converter_available() -> bool:
    """Check if pdf-remote-converter has at least one provider configured."""
    return bool(pdf_remote_converter.router.get_configured_providers(ProviderSettings()))


def _convert_via_remote(source_file: Path, output_file: Path) -> Path:
    """Convert Office document to PDF via pdf-remote-converter (online fallback)."""
    converter = pdf_remote_converter.converter.Converter()
    result = converter.convert(source_file, output_file)
    logger.info(
        "Converted %s to PDF via %s (remote fallback)",
        source_file.name,
        result.provider,
    )
    return output_file


@dataclass
class ConverterConfig:
    """PDF converter configuration."""

    backend: ConverterBackend = ConverterBackend.AUTO

    @classmethod
    def from_env(cls) -> ConverterConfig:
        """Build converter config from environment variables."""
        return cls()


def is_office_format(source_file: Path) -> bool:
    """Check if a file is an Office document that needs PDF conversion."""
    return source_file.suffix.lower() in OFFICE_FORMATS


def ensure_pdf(
    source_file: Path,
    output_dir: Path,
    *,
    force: bool = False,
    config: ConverterConfig | None = None,
    output_stem: str | None = None,
    remote_fallback: bool = True,
) -> Path:
    """Ensure a PDF version of *source_file* exists in *output_dir*.

    For office documents, converts via LibreOffice (or remote fallback).
    For native PDFs, copies.  Uses cached conversion when available.
    """
    stem = output_stem or source_file.stem
    pdf_path = output_dir / f"{stem}.pdf"

    if pdf_path.exists() and not force:
        return pdf_path

    if is_office_format(source_file):
        return convert_to_pdf(source_file, output_dir, force=force, config=config, output_stem=stem, remote_fallback=remote_fallback)

    # Native PDF — copy to output.
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_file, pdf_path)
    return pdf_path


def convert_to_pdf(
    source_file: Path,
    output_dir: Path,
    *,
    force: bool = False,
    config: ConverterConfig | None = None,
    output_stem: str | None = None,
    remote_fallback: bool = True,
) -> Path:
    """Convert an Office document to PDF.

    Selects the appropriate backend and falls back from local to remote
    when using ``AUTO`` and ``remote_fallback`` is enabled.

    Raises:
        ConversionError: If conversion fails with all available backends.
        FileNotFoundError: If the input file does not exist.
    """
    if not source_file.exists():
        msg = f"Input file not found: {source_file}"
        raise FileNotFoundError(msg)

    if not is_office_format(source_file):
        msg = f"Unsupported file format: {source_file.suffix}"
        raise ConversionError(msg)

    config = config or ConverterConfig.from_env()
    stem = output_stem or source_file.stem
    output_file = output_dir / f"{stem}.pdf"

    if not force and output_file.exists():
        logger.debug("Using cached PDF: %s", output_file)
        return output_file

    output_dir.mkdir(parents=True, exist_ok=True)

    if config.backend == ConverterBackend.LIBREOFFICE:
        return _convert_via_libreoffice(source_file, output_dir, output_stem=stem)

    # AUTO: try LibreOffice, optionally fall back to remote converter.
    try:
        return _convert_via_libreoffice(source_file, output_dir, output_stem=stem)
    except ConversionError:
        if not remote_fallback or not _is_remote_converter_available():
            raise
        logger.warning(
            "LibreOffice conversion failed for %s, falling back to remote converter",
            source_file.name,
        )
        return _convert_via_remote(source_file, output_file)


def _convert_via_libreoffice(source_file: Path, output_dir: Path, *, output_stem: str | None = None) -> Path:
    """Convert Office document to PDF via local LibreOffice (headless mode)."""
    stem = output_stem or source_file.stem
    output_file = output_dir / f"{stem}.pdf"

    try:
        converter = Converter()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = converter.convert(source_file, LibreOfficeFormat.PDF, Path(tmpdir))
            if result is None or result.output_file is None:
                msg = f"LibreOffice returned empty result for {source_file.name}"
                raise ConversionError(msg)
            output_file.write_bytes(result.output_file.read_bytes())

        logger.info("Converted %s to PDF via LibreOffice: %s", source_file.name, output_file)
        return output_file

    except ConversionError:
        raise
    except Exception as e:
        msg = f"LibreOffice conversion failed for {source_file.name}: {e}"
        logger.warning(msg)
        raise ConversionError(msg) from e


# ---------------------------------------------------------------------------
# pymupdf4llm markdown extraction (fast, no ML)
# ---------------------------------------------------------------------------

# Matches ``![alt](media/image_NNN.png)`` — pymupdf4llm output with write_images=True.
# Also matches absolute paths like ``![alt](C:/.../media/image_NNN.png)``.
_MEDIA_REF_PATTERN_ABS = re.compile(r"!\[([^\]]*)\]\(([^)]*media/[^)]+)\)")
_SUFFIX_TO_MIME: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
}


def _embed_media_as_base64(text: str, output_dir: Path) -> str:
    """Replace ``media/`` file references with base64 data URIs.

    Handles both relative ``media/...`` and absolute paths emitted by pymupdf4llm.
    After embedding, the ``media/`` directory is removed.
    """
    media_dir = output_dir / "media"

    def _replacement(match: re.Match) -> str:
        alt_text = match.group(1)
        img_ref = match.group(2)
        img_path = Path(img_ref)
        if not img_path.is_absolute():
            img_path = output_dir / img_ref
        try:
            data = img_path.read_bytes()
            b64 = base64.b64encode(data).decode("ascii")
            mime = _SUFFIX_TO_MIME.get(img_path.suffix.lower(), "application/octet-stream")
            return f"![{alt_text}](data:{mime};base64,{b64})"
        except (OSError, ValueError):
            logger.warning("Failed to embed image: %s", img_path, exc_info=True)
            return match.group(0)

    # Match both relative ``media/...`` and absolute ``C:/.../media/...`` paths.
    result = _MEDIA_REF_PATTERN_ABS.sub(_replacement, text)
    if media_dir.exists():
        shutil.rmtree(media_dir, ignore_errors=True)
    return result


def _build_yaml_frontmatter(
    *,
    document_id: str,
    source_kind: SourceKind,
    profile: ExtractionProfile,
    db_metadata: dict[str, object] | None = None,
) -> str:
    """Build YAML frontmatter string for a Markdown file."""
    import yaml  # noqa: PLC0415

    frontmatter_data: dict[str, object] = {
        "document_id": document_id,
        "source_kind": source_kind.value,
        "profile": profile.value,
        "extraction_date": datetime.now(UTC).isoformat(),
    }
    if db_metadata:
        frontmatter_data["metadata"] = db_metadata

    return f"---\n{yaml.dump(frontmatter_data, default_flow_style=False, allow_unicode=True).strip()}\n---\n\n"


def _add_yaml_frontmatter(
    md_path: Path,
    *,
    document_id: str,
    source_kind: SourceKind,
    profile: ExtractionProfile,
    db_metadata: dict[str, object] | None = None,
) -> None:
    """Prepend YAML frontmatter to a Markdown file."""
    header = _build_yaml_frontmatter(
        document_id=document_id,
        source_kind=source_kind,
        profile=profile,
        db_metadata=db_metadata,
    )
    content = md_path.read_text(encoding="utf-8")
    md_path.write_text(header + content, encoding="utf-8")


def _run_markdown_only(
    primary: Path,
    output_dir: Path,
    *,
    figures_mode: FiguresMode = FiguresMode.EMBED,
    use_layout_mode: bool = False,
    output_stem: str | None = None,
) -> Path:
    """Convert a PDF document to Markdown using pymupdf4llm."""
    media_dir = output_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    # by default, pymupdf4llm's layout mode is enabled for better text flow in multi-column documents.
    # For LLM-based extraction, the page layout does not need to be preserved, so layout mode can be disabled by default for simpler output.
    pymupdf4llm.use_layout(use_layout_mode)

    md_text = pymupdf4llm.to_markdown(
        str(primary),
        write_images=True,
        image_path=str(media_dir),
        image_format="png",
    )

    # pymupdf4llm may emit absolute paths — normalize to relative ``media/``.
    media_prefix = str(media_dir).replace("\\", "/")
    md_text = md_text.replace(media_prefix + "/", "media/")

    if figures_mode == FiguresMode.EMBED:
        md_text = _embed_media_as_base64(md_text, output_dir)

    stem = output_stem or primary.stem
    md_path = output_dir / f"{stem}.md"
    md_path.write_text(md_text, encoding="utf-8")
    return md_path


def _is_text_format(source_file: Path) -> bool:
    """Check if a file is a plain text/markdown/HTML format."""
    return source_file.suffix.lower() in _TEXT_FORMATS


def _is_spreadsheet_format(source_file: Path) -> bool:
    """Check if a file is a spreadsheet format."""
    return source_file.suffix.lower() in _SPREADSHEET_FORMATS


def _convert_html_to_markdown(html_path: Path) -> str:
    """Convert an HTML file to clean Markdown via markdownify."""
    html_content = html_path.read_text(encoding="utf-8", errors="replace")
    return md(html_content, heading_style="ATX")


def _convert_text_to_markdown(text_path: Path) -> str:
    """Wrap a plain text file in Markdown code block."""
    text_content = text_path.read_text(encoding="utf-8", errors="replace")
    return f"```text\n{text_content}\n```\n"


def _convert_spreadsheet_to_markdown(
    spreadsheet_path: Path,
    mode: SpreadsheetMode = SpreadsheetMode.DATA,
) -> str:
    """Convert a spreadsheet to Markdown tables (data mode) or return empty for visual mode.

    In **data** mode, each sheet is extracted as a Markdown table.
    In **visual** mode, the caller should convert to PDF via LibreOffice instead.

    """
    if mode == SpreadsheetMode.VISUAL:
        return ""

    suffix = spreadsheet_path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(spreadsheet_path)
        return df.to_markdown(index=False)

    engine = "openpyxl" if suffix in (".xlsx", ".xls") else "odf"
    try:
        xl = pd.ExcelFile(spreadsheet_path, engine=engine)
    except Exception:
        logger.warning("Failed to read %s with engine %s", spreadsheet_path, engine)
        return ""

    parts: list[str] = []
    for sheet_name in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name=sheet_name)
        parts.append(f"## Sheet: {sheet_name}\n")
        parts.append(df.to_markdown(index=False))
        parts.append("")
    return "\n".join(parts)


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

    Raises:
        ConversionError: If no document files can be found.
    """
    if source_kind == SourceKind.OTHER:
        if source_path:
            actual_path = Path(str(source_path))
            if actual_path.exists():
                return actual_path
        msg = f"OTHER source {document_id} not found on disk"
        raise ConversionError(msg)

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
                checkout_spec_to_workspace(spec_number, checkout_base, release=spec_release),
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
    docx_direct: bool = False,
    md_yaml_frontmatter: bool = True,
    db_metadata: dict[str, object] | None = None,
    remote_fallback: bool = True,
    spreadsheet_mode: SpreadsheetMode = SpreadsheetMode.DATA,
) -> Path:
    """Convert a document for wiki ingestion using the specified profile.

    For **markdown-only** the pipeline is:
    1. Convert Office documents to PDF (via LibreOffice); native PDFs pass through.
    2. Feed PDF to :func:`pymupdf4llm.to_markdown` for layout-aware extraction
       with inline images, tables, and multi-column support.
    3. Write ``.md`` to *wiki_source_dir*.

    For **default** and **advanced** profiles the pipeline is:
    1. Convert to PDF (via LibreOffice) if not already PDF, unless docx_direct.
    2. Feed to Docling for structured extraction.
    3. Write Markdown + JSON to *wiki_source_dir*.

    Args:
        document_id: Document identifier (TDoc ID, spec number, etc.).
        wiki_source_dir: Target directory under ``wiki/<workspace>/sources/<doc-id>/``.
        source_kind: Kind of source (TDOC, SPEC, OTHER).
        source_path: Optional explicit path to the source document/directory.
        profile: Extraction profile. Defaults to ``DEFAULT_EXTRACTION_PROFILE``.
        force: Force reconversion.
        docling_config: Optional Docling-specific configuration (figure/table modes).
        docx_direct: Feed .docx directly to backend, skip LibreOffice PDF step.
        md_yaml_frontmatter: Prepend YAML frontmatter to generated Markdown.
        db_metadata: Optional DB metadata dict to embed in YAML frontmatter.
        remote_fallback: Use online PDF service when LibreOffice fails.
        spreadsheet_mode: How to handle spreadsheet files (data vs visual).

    Returns:
        Path to the primary output file (PDF for pdf-only, MD for others).

    Raises:
        ConversionError: If no document files are found for the given document_id.
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
    safe_stem = sanitize_filename_stem(primary.stem)

    # --- OTHER source special handling (HTML / text / spreadsheets) ---
    if source_kind == SourceKind.OTHER:
        if _is_text_format(primary):
            md_file = wiki_source_dir / f"{safe_stem}.md"
            if not force and md_file.exists():
                logger.debug("Skipping %s — markdown already exists", document_id)
                return md_file

            md_text = _convert_html_to_markdown(primary) if primary.suffix.lower() in (".html", ".htm") else _convert_text_to_markdown(primary)

            if md_yaml_frontmatter:
                fm = _build_yaml_frontmatter(
                    document_id=document_id,
                    source_kind=source_kind,
                    profile=profile,
                    db_metadata=db_metadata,
                )
                md_text = fm + "\n" + md_text

            md_file.write_text(md_text, encoding="utf-8")

            if profile == ExtractionProfile.PDF_ONLY:
                # PDF-only on HTML/text: return Markdown (no direct Markdown→PDF pipeline yet)
                logger.warning("PDF-only profile on HTML/text source %s — returning Markdown", document_id)
            return md_file

        if _is_spreadsheet_format(primary):
            if spreadsheet_mode == SpreadsheetMode.DATA and profile != ExtractionProfile.PDF_ONLY:
                md_file = wiki_source_dir / f"{safe_stem}.md"
                if not force and md_file.exists():
                    logger.debug("Skipping %s — markdown already exists", document_id)
                    return md_file
                md_text = _convert_spreadsheet_to_markdown(primary, mode=SpreadsheetMode.DATA)
                if md_yaml_frontmatter:
                    fm = _build_yaml_frontmatter(
                        document_id=document_id,
                        source_kind=source_kind,
                        profile=profile,
                        db_metadata=db_metadata,
                    )
                    md_text = fm + "\n" + md_text
                md_file.write_text(md_text, encoding="utf-8")
                return md_file
            # visual mode or pdf-only → fall through to LibreOffice PDF conversion
            return ensure_pdf(primary, wiki_source_dir, force=force, output_stem=safe_stem, remote_fallback=remote_fallback)

    # Step 2a: pdf-only → just ensure PDF
    if profile == ExtractionProfile.PDF_ONLY:
        return ensure_pdf(primary, wiki_source_dir, force=force, output_stem=safe_stem, remote_fallback=remote_fallback)

    # Step 2b: markdown-only → pymupdf4llm (fast, no ML, layout-aware)
    if profile == ExtractionProfile.MARKDOWN_ONLY:
        md_file = wiki_source_dir / f"{safe_stem}.md"
        if not force and md_file.exists():
            logger.debug("Skipping %s — markdown already exists", document_id)
            return md_file
        # Office formats → LibreOffice PDF first; native PDFs pass through.
        input_for_md = ensure_pdf(primary, wiki_source_dir, force=force, output_stem=safe_stem, remote_fallback=remote_fallback)
        figures_mode = docling_config.figures_mode if docling_config else FiguresMode.EMBED
        with timed_operation(get_metrics_tracker(), document_id, MetricType.CONVERSION):
            result = _run_markdown_only(input_for_md, wiki_source_dir, figures_mode=figures_mode, output_stem=safe_stem)
        if md_yaml_frontmatter:
            _add_yaml_frontmatter(result, document_id=document_id, source_kind=source_kind, profile=profile, db_metadata=db_metadata)
        return result

    # Step 2c: default/advanced → check existing output before running Docling
    md_file = wiki_source_dir / f"{safe_stem}.md"
    json_file = wiki_source_dir / f"{safe_stem}.json"
    if not force and md_file.exists() and json_file.exists():
        logger.debug("Skipping %s — output already exists", document_id)
        return md_file

    # Step 2d: ensure PDF first (unless docx-direct), then Docling
    is_docx_direct = docx_direct and primary.suffix.lower() in _DOCX_SUFFIXES
    input_for_docling = primary if is_docx_direct else ensure_pdf(primary, wiki_source_dir, force=force, output_stem=safe_stem, remote_fallback=remote_fallback)

    with timed_operation(get_metrics_tracker(), document_id, MetricType.CONVERSION):
        _, _, _ = _run_docling(
            input_for_docling,
            wiki_source_dir,
            profile=profile,
            config=docling_config,
            docx_direct=is_docx_direct,
            output_stem=safe_stem,
        )

    if md_yaml_frontmatter:
        _add_yaml_frontmatter(md_file, document_id=document_id, source_kind=source_kind, profile=profile, db_metadata=db_metadata)
    return md_file


__all__ = [
    "OFFICE_FORMATS",
    "ConversionError",
    "ConverterBackend",
    "ConverterConfig",
    "DoclingConfig",
    "SpreadsheetMode",
    "convert_for_wiki",
    "convert_to_pdf",
    "ensure_pdf",
    "is_office_format",
]
