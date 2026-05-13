"""Extraction profiles for wiki ingestion.

Defines four tiers of document extraction:
- pdf-only: Raw PDF (office docs converted via LibreOffice)
- markdown-only: Fast markdown via markitdown (no ML, .md only)
- default: Structured markdown + JSON via Docling
- advanced: Same as default + picture descriptions, code/formula enrichment
"""

from __future__ import annotations

from enum import StrEnum


class ExtractionProfile(StrEnum):
    """Extraction profile levels for wiki ingestion."""

    PDF_ONLY = "pdf-only"  # raw PDF, no structured extraction
    MARKDOWN_ONLY = "markdown-only"  # fast markitdown, .md only, no ML
    DEFAULT = "default"  # Docling structured extraction
    ADVANCED = "advanced"  # Docling + picture descriptions, code/formula enrichment


# Default profile used when none is specified
DEFAULT_EXTRACTION_PROFILE = ExtractionProfile.DEFAULT


__all__ = [
    "DEFAULT_EXTRACTION_PROFILE",
    "ExtractionProfile",
]
