"""TDoc utility functions."""

from __future__ import annotations


def normalize_tdoc_id(tdoc_id: str) -> str:
    """Normalize a TDoc ID to uppercase.

    Args:
        tdoc_id: TDoc identifier to normalize.

    Returns:
        Uppercase normalized TDoc ID.
    """
    return str(tdoc_id).strip().upper()


def normalize_tdoc_ids(tdoc_ids: list[str] | None) -> list[str] | None:
    """Normalize a list of TDoc IDs to uppercase.

    Args:
        tdoc_ids: List of TDoc identifiers to normalize.

    Returns:
        List of uppercase normalized TDoc IDs, or None if input is None.
    """
    if tdoc_ids is None:
        return None
    return [normalize_tdoc_id(tdoc_id) for tdoc_id in tdoc_ids]
