"""Query shared helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import typer

from tdoc_crawler.cli._shared import console
from tdoc_crawler.utils.date_parser import parse_partial_date


def _parse_date_range(start_date: str | None, end_date: str | None) -> tuple[datetime | None, datetime | None]:
    try:
        start = datetime.combine(parse_partial_date(start_date), datetime.min.time(), tzinfo=UTC) if start_date else None
    except ValueError as exc:
        console.print("[red]Invalid start date format; use ISO-8601")
        raise typer.Exit(code=2) from exc
    try:
        end = datetime.combine(parse_partial_date(end_date, is_end=True), datetime.max.time(), tzinfo=UTC) if end_date else None
    except ValueError as exc:
        console.print("[red]Invalid end date format; use ISO-8601")
        raise typer.Exit(code=2) from exc
    return start, end
