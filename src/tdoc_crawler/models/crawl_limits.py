"""Crawl limit configurations."""

from __future__ import annotations

from pydantic import Field

from .base import BaseConfigModel


class CrawlLimits(BaseConfigModel):
    """Limitations applied during crawl operations."""

    limit_tdocs: int | None = Field(
        None,
        description="Maximum number of TDocs to crawl overall (negative for newest N)",
    )
    limit_meetings: int | None = Field(
        None,
        description="Maximum meetings to crawl overall (negative for newest N)",
    )
    limit_meetings_per_wg: int | None = Field(
        None,
        description="Per working group meeting limit",
    )
    limit_wgs: int | None = Field(None, description="Maximum number of working groups to process")


def _new_crawl_limits() -> CrawlLimits:
    """Return an empty crawl limits instance for Field default factories."""

    return CrawlLimits(
        limit_tdocs=None,
        limit_meetings=None,
        limit_meetings_per_wg=None,
        limit_wgs=None,
    )


__all__ = ["CrawlLimits", "_new_crawl_limits"]
