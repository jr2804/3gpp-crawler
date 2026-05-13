"""Suppress noisy ``std::bad_alloc`` errors from Docling's C++ backend.

Docling-parse (RockHopper) has a known bug where it tries to preprocess
phantom pages beyond the actual PDF page count, resulting in a flood of
``std::bad_alloc`` errors at ERROR level.  These are non-fatal – Docling
returns ``partial_success`` with valid output for the real pages.

This filter downgrades such messages to DEBUG so they only appear when
the user has explicitly enabled debug verbosity.
"""

from __future__ import annotations

import logging
from typing import override

logger = logging.getLogger(__name__)

# Logger used by Docling's threaded pipeline for C++ preprocess errors.
_DOCLING_PIPELINE_LOGGER = "docling.pipeline.standard_pdf_pipeline"


class _DoclingBadAllocFilter(logging.Filter):
    """Suppress noisy ``std::bad_alloc`` errors from Docling's C++ backend."""

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != _DOCLING_PIPELINE_LOGGER:
            return True
        msg = record.getMessage()
        if "bad_alloc" in msg and record.levelno == logging.ERROR:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "Docling C++ backend: %s (suppressed from ERROR)",
                    msg,
                )
            return False
        return True
