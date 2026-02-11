"""Database facade exports."""

from __future__ import annotations

import logging

from tdoc_crawler.database.base import DocDatabase
from tdoc_crawler.database.errors import DatabaseError
from tdoc_crawler.database.meetings import MeetingDatabase
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.database.tdocs import TDocDatabase

logger = logging.getLogger(__name__)


__all__ = [
    "DatabaseError",
    "DocDatabase",
    "MeetingDatabase",
    "SpecDatabase",
    "TDocDatabase",
]
