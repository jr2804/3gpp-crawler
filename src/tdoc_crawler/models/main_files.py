"""Main-file selection models for TDoc archives.

One TDoc zip usually holds a single "main" document plus attachments
(cover sheets, background documents, meeting notices, ...). These models
describe how that main file was resolved: the configured automatic
strategy, and the source of the winning decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class MainFileSelector(StrEnum):
    """Automatic strategy allowed to pick the main file.

    A stored manual override always wins over the configured strategy —
    the selector only controls the automatic fallback chain:

    - ``heuristic``: offline filename/content ranking (default).
    - ``decision_model``: ask the external System One model first, fall
      back to the heuristic when it is unconfigured, errors, or answers
      below the confidence threshold.
    - ``manual``: never consult the model; only the heuristic and stored
      overrides are used.
    """

    HEURISTIC = "heuristic"
    DECISION_MODEL = "decision_model"
    MANUAL = "manual"


class MainFileSource(StrEnum):
    """Where the winning main-file decision came from."""

    MANUAL_OVERRIDE = "manual_override"
    DECISION_MODEL = "decision_model"
    HEURISTIC = "heuristic"


@dataclass(frozen=True)
class MainFileSelection:
    """Resolved main file of an extracted TDoc archive."""

    path: Path
    relative_path: str
    source: MainFileSource
    confidence: float | None = None


__all__ = ["MainFileSelection", "MainFileSelector", "MainFileSource"]
