"""Shared spec source protocol definitions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


class SpecSource(Protocol):
    """Protocol for spec metadata sources."""

    name: str

    def fetch(self, spec_number: str) -> dict[str, object]:
        """Fetch metadata for the given spec number."""
        raise NotImplementedError


@dataclass(frozen=True)
class FunctionSpecSource:
    """Adapter that exposes a callable as a SpecSource."""

    name: str
    fetcher: Callable[[str], dict[str, object]]

    def fetch(self, spec_number: str) -> dict[str, object]:
        """Fetch metadata using the wrapped callable.

        Args:
            spec_number: Spec number to fetch.

        Returns:
            Raw metadata payload for the spec.
        """
        return self.fetcher(spec_number)
