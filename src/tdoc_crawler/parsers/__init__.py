"""Data parsers for HTML, Excel, and other formats."""

from __future__ import annotations

from tdoc_crawler.parsers.portal import PortalParsingError, parse_tdoc_portal_page

__all__ = [
    "PortalParsingError",
    "parse_tdoc_portal_page",
]
