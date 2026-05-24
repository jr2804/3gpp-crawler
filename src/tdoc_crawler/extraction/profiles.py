"""Extraction profiles for wiki ingestion.

Defines four tiers of document extraction:
- pdf-only: Raw PDF (office docs converted via LibreOffice)
- markdown-only: Layout-aware Markdown via pymupdf4llm (no ML, .md only)
- default: Structured markdown + JSON via Docling
- advanced: Same as default + picture descriptions, code/formula enrichment
"""

from __future__ import annotations

from enum import StrEnum


class ExtractionProfile(StrEnum):
    """Extraction profile levels for wiki ingestion."""

    PDF_ONLY = "pdf-only"  # raw PDF, no structured extraction
    MARKDOWN_ONLY = "markdown-only"  # layout-aware pymupdf4llm, .md only, no ML
    DEFAULT = "default"  # Docling structured extraction
    ADVANCED = "advanced"  # Docling + picture descriptions, code/formula enrichment


class FiguresMode(StrEnum):
    """How to handle figures/images in extraction output."""

    EMBED = "embed"  # images embedded as base64 / placeholder in markdown
    REFERENCE = "reference"  # images extracted as separate files


class TablesMode(StrEnum):
    """How to handle tables in extraction output."""

    EMBED = "embed"  # tables embedded in markdown
    CSV = "csv"  # tables exported as separate CSV files


class DeviceType(StrEnum):
    """Accelerator device for ML-based extraction backends."""

    AUTO = "auto"  # auto-detect (CUDA if available, else CPU)
    CPU = "cpu"  # force CPU-only
    CUDA = "cuda"  # force NVIDIA CUDA GPU
    MPS = "mps"  # force Apple Metal Performance Shaders


class SpreadsheetMode(StrEnum):
    """How to handle spreadsheet documents in extraction output."""

    DATA = "data"  # extract tables/data as markdown/CSV
    VISUAL = "visual"  # convert to PDF via LibreOffice to preserve layout/charts


# Default profile used when none is specified
DEFAULT_EXTRACTION_PROFILE = ExtractionProfile.DEFAULT


__all__ = [
    "DEFAULT_EXTRACTION_PROFILE",
    "DeviceType",
    "ExtractionProfile",
    "FiguresMode",
    "SpreadsheetMode",
    "TablesMode",
]
