"""TEDDI-MCP: FastMCP 3.0 server for ETSI TEDDI search integration."""

from teddi_mcp.client import TeddiClient, TeddiSource
from teddi_mcp.models import (
    DocumentRef,
    SearchIn,
    SearchPattern,
    SearchRequest,
    SearchResponse,
    TechnicalBody,
    TermResult,
)

__version__ = "0.1.0"
__all__ = [
    "TeddiClient",
    "TeddiSource",
    "DocumentRef",
    "SearchIn",
    "SearchPattern",
    "SearchRequest",
    "SearchResponse",
    "TechnicalBody",
    "TermResult",
]
