"""HTTP and API clients."""

from __future__ import annotations

from tdoc_crawler.clients.portal import PortalAuthenticationError, PortalClient

# Re-export PortalParsingError from parsers for backward compatibility
from tdoc_crawler.parsers.portal import PortalParsingError

__all__ = [
    "PortalAuthenticationError",
    "PortalClient",
    "PortalParsingError",
]
