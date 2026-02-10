"""Database facade exports."""

from __future__ import annotations

import logging

from tdoc_crawler.database.connection import SpecDatabase, TDocDatabase
from tdoc_crawler.database.errors import DatabaseError

logger = logging.getLogger(__name__)


__all__ = [
    "DatabaseError",
    "SpecDatabase",
    "TDocDatabase",
]
