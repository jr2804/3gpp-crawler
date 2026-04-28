"""Extraction profiles for wiki ingestion.

Defines three tiers of document extraction:
- pdf-only: Raw PDF (office docs converted via LibreOffice)
- default: Structured markdown + JSON via opendataloader-pdf hybrid mode
- advanced: Same as default + AI-assisted picture descriptions
"""

from __future__ import annotations

from enum import StrEnum


class ExtractionProfile(StrEnum):
    """Extraction profile levels for wiki ingestion."""

    PDF_ONLY = "pdf-only"  # raw PDF, no structured extraction
    DEFAULT = "default"  # opendataloader hybrid mode
    ADVANCED = "advanced"  # hybrid + picture descriptions


# Default profile used when none is specified
DEFAULT_EXTRACTION_PROFILE = ExtractionProfile.DEFAULT


__all__ = [
    "DEFAULT_EXTRACTION_PROFILE",
    "ExtractionProfile",
]
