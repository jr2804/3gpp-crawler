"""Oxyde ORM models for database persistence.

This module contains all ORM models using Oxyde for database storage.
These models replace the previous pydantic-sqlite based persistence layer.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from oxyde import Field, Model


class WorkingGroupRecord(Model):
    """Reference data for working groups."""

    tbid: int = Field(primary_key=True)
    code: str
    name: str


class SubWorkingGroupRecord(Model):
    """Reference data for subworking groups."""

    subtb: int = Field(primary_key=True)
    tbid: int
    code: str
    name: str


class CrawlLogEntry(Model):
    """Log entry for crawl operations."""

    log_id: str = Field(primary_key=True)
    crawl_type: str
    start_time: datetime
    end_time: datetime | None = None
    working_groups: list[str] = Field(default_factory=list)
    incremental: bool = Field(default=False)
    items_added: int = Field(default=0, ge=0)
    items_updated: int = Field(default=0, ge=0)
    errors_count: int = Field(default=0, ge=0)
    status: str = Field(default="RUNNING")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MeetingMetadata(Model):
    """Metadata for 3GPP meetings."""

    meeting_id: int = Field(primary_key=True)
    tbid: int
    subtb: int | None = None
    short_name: str
    title: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    location: str | None = None
    files_url: str | None = None
    portal_url: str | None = None
    tdoc_count: int = Field(default=0, ge=0)
    last_synced: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TDocMetadata(Model):
    """Metadata for TDoc documents."""

    tdoc_id: str = Field(primary_key=True)
    meeting_id: int
    title: str
    url: str | None = None
    source: str
    contact: str
    tdoc_type: str = Field(default="unknown")
    for_purpose: str = Field(default="unknown")
    agenda_item_nbr: str
    agenda_item_text: str = Field(default="Unknown")
    status: str | None = None
    is_revision_of: str | None = None
    file_size: int | None = None
    date_created: datetime | None = None
    date_retrieved: datetime = Field(default_factory=datetime.utcnow)
    date_updated: datetime = Field(default_factory=datetime.utcnow)
    validated: bool = Field(default=False)
    validation_failed: bool = Field(default=False)


class Specification(Model):
    """Canonical specification identity and metadata."""

    spec_number: str = Field(primary_key=True)
    spec_number_compact: str
    spec_type: str
    title: str
    status: str
    working_group: str
    series: str
    latest_version: str | None = None


class SpecificationSourceRecord(Model):
    """Source-specific metadata snapshot for specifications."""

    record_id: str = Field(primary_key=True)
    spec_number: str
    source_name: str
    source_identifier: str | None = None
    metadata_payload: dict[str, Any] = Field(default_factory=dict)
    versions: list[str] = Field(default_factory=list)
    fetched_at: datetime | None = None


class SpecificationVersion(Model):
    """Version details for specifications."""

    record_id: str = Field(primary_key=True)
    spec_number: str
    version: str
    file_name: str
    source_name: str


class SpecificationDownload(Model):
    """Download and extraction outcome for spec versions."""

    record_id: str = Field(primary_key=True)
    spec_number: str
    version: str
    download_url: str
    checkout_path: str
    document_path: str
    attachment_paths: list[str] = Field(default_factory=list)
    doc_only_used: bool = Field(default=False)
    outcome_status: str
    outcome_message: str | None = None
    extracted_at: datetime | None = None


__all__ = [
    "CrawlLogEntry",
    "MeetingMetadata",
    "Specification",
    "SpecificationDownload",
    "SpecificationSourceRecord",
    "SpecificationVersion",
    "SubWorkingGroupRecord",
    "TDocMetadata",
    "WorkingGroupRecord",
]
