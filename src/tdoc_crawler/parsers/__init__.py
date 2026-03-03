"""Data parsers for HTML, Excel, and other formats."""

from __future__ import annotations

from tdoc_crawler.parsers.meetings import MeetingParser
from tdoc_crawler.parsers.portal import PortalParser, PortalParsingError, parse_tdoc_portal_page

__all__ = [
    "MeetingParser",
    "PortalParser",
    "PortalParsingError",
    "parse_tdoc_portal_page",
]
