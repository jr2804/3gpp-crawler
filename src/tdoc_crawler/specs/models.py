"""Specification data models.

This module contains Pydantic models for specification metadata,
including the canonical spec identity, source records, versions,
and download outcomes.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

from tdoc_crawler.utils.version_types import SpecVersion


class Specification(BaseModel):
    """Canonical spec identity and metadata."""

    spec_number: str
    spec_number_compact: str
    spec_type: str
    title: str
    status: str
    working_group: str
    series: str
    latest_version: SpecVersion | None = None

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        _ = (console, options)
        yield Text(f"{self.spec_number} - {self.title}")


class SpecificationSourceRecord(BaseModel):
    """Source-specific metadata snapshot."""

    record_id: str | None = None
    spec_number: str
    source_name: str
    source_identifier: str | None = None
    metadata_payload: dict[str, Any] = Field(default_factory=dict)
    versions: list[SpecVersion] = Field(default_factory=list)
    fetched_at: datetime | None = None


class SpecificationVersion(BaseModel):
    """Spec version details."""

    record_id: str | None = None
    spec_number: str
    version: SpecVersion
    file_name: str
    source_name: str


class SpecificationDownload(BaseModel):
    """Download and extraction outcome for a spec version."""

    record_id: str | None = None
    spec_number: str
    version: SpecVersion
    download_url: str
    checkout_path: Path
    document_path: Path
    attachment_paths: list[Path] = Field(default_factory=list)
    doc_only_used: bool = False
    outcome_status: str
    outcome_message: str | None = None
    extracted_at: datetime | None = None


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
