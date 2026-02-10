"""HTTP and API clients."""

from __future__ import annotations

from tdoc_crawler.clients.portal import (
    PortalAuthenticationError,
    PortalClient,
    PortalSession,
    create_portal_client,
    extract_tdoc_url_from_portal,
)

# Re-export PortalParsingError from parsers for backward compatibility
from tdoc_crawler.parsers.portal import PortalParsingError

__all__ = [
    "PortalAuthenticationError",
    "PortalClient",
    "PortalParsingError",
    "PortalSession",
    "create_portal_client",
    "extract_tdoc_url_from_portal",
]
