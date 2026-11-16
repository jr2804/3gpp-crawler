"""Database facade exports."""

from __future__ import annotations

from tdoc_crawler.database.base import DocDatabase
from tdoc_crawler.database.errors import DatabaseError
from tdoc_crawler.database.main_files import (
    clear_main_file_override,
    clear_main_file_record,
    get_main_file_override,
    get_main_file_record,
    list_main_file_overrides,
    list_main_file_records,
    save_main_file_record,
    set_main_file_override,
)
from tdoc_crawler.database.meetings import MeetingDatabase
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.database.tdocs import TDocDatabase

__all__ = [
    "DatabaseError",
    "DocDatabase",
    "MeetingDatabase",
    "SpecDatabase",
    "TDocDatabase",
    "clear_main_file_override",
    "clear_main_file_record",
    "get_main_file_override",
    "get_main_file_record",
    "list_main_file_overrides",
    "list_main_file_records",
    "save_main_file_record",
    "set_main_file_override",
]
