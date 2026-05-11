"""Extraction profiles for wiki ingestion.

Defines three tiers of document extraction:
- pdf-only: Raw PDF (office docs converted via LibreOffice)
- default: Structured markdown + JSON via Docling
- advanced: Same as default + picture descriptions, code/formula enrichment
"""

from __future__ import annotations

from enum import StrEnum


class ExtractionProfile(StrEnum):
    """Extraction profile levels for wiki ingestion."""

    PDF_ONLY = "pdf-only"  # raw PDF, no structured extraction
    DEFAULT = "default"  # Docling structured extraction
    ADVANCED = "advanced"  # Docling + picture descriptions, code/formula enrichment


# Default profile used when none is specified
DEFAULT_EXTRACTION_PROFILE = ExtractionProfile.DEFAULT


__all__ = [
    "DEFAULT_EXTRACTION_PROFILE",
    "ExtractionProfile",
]
