"""TDoc metadata sources.

This package provides abstractions for fetching TDoc metadata from various sources:
- WhatTheSpec community API (unauthenticated)
- 3GPP Portal (authenticated)
- Meeting Document Lists (unauthenticated bulk)
"""

from __future__ import annotations

from tdoc_crawler.tdocs.sources.base import TDocSource, TDocSourceConfig
from tdoc_crawler.tdocs.sources.doclist import DocumentListSource
from tdoc_crawler.tdocs.sources.portal import PortalSource
from tdoc_crawler.tdocs.sources.whatthespec import WhatTheSpecSource

__all__ = [
    "DocumentListSource",
    "PortalSource",
    "TDocSource",
    "TDocSourceConfig",
    "WhatTheSpecSource",
]
