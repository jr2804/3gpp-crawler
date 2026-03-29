"""Specification data models.

This module contains Pydantic models for specification metadata,
including the canonical spec identity, source records, versions,
and download outcomes.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from packaging.version import Version
from pydantic import BaseModel, Field, field_validator
from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

from tdoc_crawler.utils.parse import SpecificationVersionNumber, parse_spec_version_nbr


class Specification(BaseModel):
    """Canonical spec identity and metadata."""

    spec_number: str
    spec_number_compact: str
    spec_type: str
    title: str
    status: str
    working_group: str
    series: str
    latest_version: SpecificationVersionNumber | None = None

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        _ = (console, options)
        yield Text(f"{self.spec_number} - {self.title}")

    @field_validator("latest_version", mode="before")
    @classmethod
    def _normalize_latest_version(cls, value: Version | SpecificationVersionNumber | None) -> SpecificationVersionNumber | None:
        """Normalize latest version to canonical three-part string when provided."""
        if value is None:
            return None
        return parse_spec_version_nbr(value)


class SpecificationSourceRecord(BaseModel):
    """Source-specific metadata snapshot."""

    record_id: str | None = None
    spec_number: str
    source_name: str
    source_identifier: str | None = None
    metadata_payload: dict[str, Any] = Field(default_factory=dict)
    versions: list[SpecificationVersionNumber] = Field(default_factory=list)
    fetched_at: datetime | None = None

    @field_validator("versions", mode="before")
    @classmethod
    def _normalize_versions(cls, value: list[Version | SpecificationVersionNumber] | None) -> list[SpecificationVersionNumber]:
        """Normalize source versions to canonical three-part strings."""
        if value is None:
            return []
        return [parse_spec_version_nbr(item) for item in value]


class SpecificationVersion(BaseModel):
    """Spec version details."""

    record_id: str | None = None
    spec_number: str
    version: SpecificationVersionNumber
    file_name: str
    source_name: str

    @field_validator("version", mode="before")
    @classmethod
    def _normalize_version(cls, value: Version | SpecificationVersionNumber) -> SpecificationVersionNumber:
        """Normalize version to canonical three-part string."""
        return parse_spec_version_nbr(value)


class SpecificationDownload(BaseModel):
    """Download and extraction outcome for a spec version."""

    record_id: str | None = None
    spec_number: str
    version: SpecificationVersionNumber
    download_url: str
    checkout_path: Path
    document_path: Path
    attachment_paths: list[Path] = Field(default_factory=list)
    doc_only_used: bool = False
    outcome_status: str
    outcome_message: str | None = None
    extracted_at: datetime | None = None

    @field_validator("version", mode="before")
    @classmethod
    def _normalize_version(cls, value: Version | SpecificationVersionNumber) -> SpecificationVersionNumber:
        """Normalize downloaded version to canonical three-part string."""
        return parse_spec_version_nbr(value)


@dataclass
class SpecQueryFilters:
    """Filter inputs for spec queries."""

    spec_numbers: list[str] | None = None
    title: str | None = None
    working_group: str | None = None
    status: str | None = None

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        _ = (console, options)
        yield Text(f"SpecQueryFilters(spec_numbers={self.spec_numbers})")


@dataclass
class SpecQueryResult:
    """Query result row for a spec."""

    spec_number: str
    title: str | None = None
    status: str | None = None
    working_group: str | None = None
    source_differences: dict[str, dict[str, str | None]] = field(default_factory=dict)

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        _ = (console, options)
        yield Text(f"{self.spec_number} - {self.title or 'Unknown'}")


__all__ = [
    "SpecQueryFilters",
    "SpecQueryResult",
    "Specification",
    "SpecificationDownload",
    "SpecificationSourceRecord",
    "SpecificationVersion",
]
