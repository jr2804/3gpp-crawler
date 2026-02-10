"""Working group registries and code mappings."""

from __future__ import annotations

from typing import Final

MEETING_CODE_REGISTRY: Final[dict[str, list[tuple[str, str | None]]]] = {
    "RAN": [
        ("RP", "RP"),
        ("R1", "R1"),
        ("R2", "R2"),
        ("R3", "R3"),
        ("R4", "R4"),
        ("R5", "R5"),
        ("R6", "R6"),
    ],
    "SA": [
        ("SP", "SP"),
        ("S1", "S1"),
        ("S2", "S2"),
        ("S3", "S3"),
        ("S4", "S4"),
        ("S5", "S5"),
        ("S6", "S6"),
    ],
    "CT": [
        ("CP", "CP"),
        ("C1", "C1"),
        ("C2", "C2"),
        ("C3", "C3"),
        ("C4", "C4"),
        ("C5", "C5"),
        ("C6", "C6"),
    ],
}

__all__ = [
    "MEETING_CODE_REGISTRY",
]
