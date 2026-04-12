"""Utility functions for meeting data normalization.

This module re-exports normalization functions from tdoc_crawler.utils.normalization.
The canonical source for normalization logic is tdoc_crawler.utils.normalization.

Import directly from there when possible:

    from tdoc_crawler.utils.normalization import normalize_portal_meeting_name

"""

from __future__ import annotations

from tdoc_crawler.utils.normalization import (
    normalize_portal_meeting_name,
    normalize_subgroup_alias,
    normalize_working_group_alias,
)

__all__ = [
    "normalize_portal_meeting_name",
    "normalize_subgroup_alias",
    "normalize_working_group_alias",
]
