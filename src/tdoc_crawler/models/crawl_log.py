"""Crawl log database model."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from tdoc_crawler.utils.misc import utc_now


class CrawlLogEntry(BaseModel):
    """Persistent representation of a crawl operation log entry."""

    log_id: str = Field(default_factory=lambda: uuid4().hex, description="Primary identifier for the crawl entry")
    crawl_type: str = Field(..., description="Type of crawl operation (e.g., 'meeting', 'tdoc')")
    start_time: datetime = Field(default_factory=utc_now, description="Start timestamp of the crawl run")
    end_time: datetime | None = Field(None, description="Completion timestamp of the crawl run")
    working_groups: list[str] = Field(default_factory=list, description="List of working group codes involved in the crawl")
    incremental: bool = Field(False, description="Flag indicating incremental mode")
    items_added: int = Field(0, ge=0, description="Number of newly inserted records")
    items_updated: int = Field(0, ge=0, description="Number of updated records")
    errors_count: int = Field(0, ge=0, description="Number of errors encountered")
    status: str = Field("RUNNING", description="Current status of the crawl entry")
    created_at: datetime = Field(default_factory=utc_now, description="Timestamp when the entry was created")

    @field_validator("working_groups", mode="after")
    @classmethod
    def _normalize_working_groups(cls, value: list[str]) -> list[str]:
        """Ensure codes are stored as unique uppercase values."""
        return sorted({item.strip().upper() for item in value if item})


__all__ = ["CrawlLogEntry"]
