"""TDoc utility functions.

Note: Normalization functions are now centralized in tdoc_crawler.utils.normalization.
This module re-exports them for backward compatibility.
"""

from __future__ import annotations

from tdoc_crawler.utils.normalization import normalize_tdoc_id, normalize_tdoc_ids

__all__ = ["normalize_tdoc_id", "normalize_tdoc_ids"]
