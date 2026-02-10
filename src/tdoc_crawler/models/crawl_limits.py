"""Crawl limit configurations."""

from __future__ import annotations

from typing import Self

from pydantic import Field

from tdoc_crawler.models.base import BaseConfigModel


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

    @classmethod
    def build(
        cls,
        limit_tdocs: int | None,
        limit_meetings: int | None,
        limit_meetings_per_wg: int | None,
        limit_wgs: int | None,
    ) -> Self:
        """Build CrawlLimits configuration from individual parameters."""
        return cls(
            limit_tdocs=limit_tdocs,
            limit_meetings=limit_meetings,
            limit_meetings_per_wg=limit_meetings_per_wg,
            limit_wgs=limit_wgs,
        )


def _new_crawl_limits() -> CrawlLimits:
    """Return an empty crawl limits instance for Field default factories."""
    return CrawlLimits(
        limit_tdocs=None,
        limit_meetings=None,
        limit_meetings_per_wg=None,
        limit_wgs=None,
    )


__all__ = ["CrawlLimits", "_new_crawl_limits"]
