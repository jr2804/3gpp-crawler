import calendar
from datetime import date


def parse_partial_date(value: str, is_end: bool = False) -> date:
    """Parse partial dates to full date boundaries.

    Args:
        value: Date string (2024, 2024-10, or 2024-10-28)
        is_end: If True, return last day of period; else first day

    Returns:
        date object representing start or end of period

    Raises:
        ValueError: If format is invalid

    Examples:
        parse_partial_date("2024") -> date(2024, 1, 1)
        parse_partial_date("2024", is_end=True) -> date(2024, 12, 31)
        parse_partial_date("2024-10") -> date(2024, 10, 1)
        parse_partial_date("2024-10", is_end=True) -> date(2024, 10, 31)
        parse_partial_date("2024-10-28") -> date(2024, 10, 28)
    """
    parts = value.split("-")

    if len(parts) == 1:
        # Year only: YYYY
        year = int(parts[0])
        return date(year, 12, 31) if is_end else date(year, 1, 1)

    if len(parts) == 2:
        # Year-Month: YYYY-MM
        year, month = int(parts[0]), int(parts[1])
        if is_end:
            last_day = calendar.monthrange(year, month)[1]
            return date(year, month, last_day)
        return date(year, month, 1)

    if len(parts) == 3:
        # Full date: YYYY-MM-DD
        return date(int(parts[0]), int(parts[1]), int(parts[2]))

    msg = f"Invalid date format: {value}. Use YYYY, YYYY-MM, or YYYY-MM-DD"
    raise ValueError(msg)
