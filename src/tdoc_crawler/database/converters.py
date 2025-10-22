"""Date and datetime conversion utilities."""

from __future__ import annotations

from datetime import date, datetime

from tdoc_crawler.database.errors import DatabaseError


def date_to_text(value: date | None) -> str | None:
    """Convert date to ISO format text."""
    return value.isoformat() if value is not None else None


def datetime_to_text(value: datetime | None) -> str | None:
    """Convert datetime to ISO format text."""
    return value.isoformat() if value is not None else None


def text_to_datetime(value: str | None) -> datetime | None:
    """Convert ISO format text to datetime."""
    return datetime.fromisoformat(value) if value is not None else None


def text_to_datetime_required(value: str | None) -> datetime:
    """Convert ISO format text to datetime, raise if None."""
    dt_value = text_to_datetime(value)
    if dt_value is None:
        raise DatabaseError.missing_datetime()
    return dt_value


def text_to_date(value: str | None) -> date | None:
    """Convert ISO format text to date."""
    return date.fromisoformat(value) if value is not None else None
