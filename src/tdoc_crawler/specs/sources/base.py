"""Shared spec source protocol definitions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from tdoc_crawler.config.settings import HttpConfig
from tdoc_crawler.specs.models import SpecMetadata

type SpecFetcher = Callable[..., SpecMetadata]
"""Callable that fetches metadata for one spec number."""

type FetcherArgument = str | int | float | bool | None | Path | HttpConfig
"""Value that can be passed to a spec fetcher as keyword argument."""


@dataclass(frozen=True)
class FunctionSpecSource:
    """Adapter that exposes a callable as a SpecSource."""

    name: str
    fetcher: SpecFetcher
    fetcher_args: tuple = ()
    fetcher_kwargs: dict[str, FetcherArgument] = field(default_factory=dict)

    def fetch(self, spec_number: str) -> SpecMetadata:
        """Fetch metadata using the wrapped callable.

        Args:
            spec_number: Spec number to fetch.

        Returns:
            Metadata for the spec.
        """
        return self.fetcher(spec_number, *self.fetcher_args, **self.fetcher_kwargs)


class SpecSource(Protocol):
    """Protocol for spec metadata sources."""

    @property
    def name(self) -> str:
        """Name of the spec source."""
        ...

    def fetch(self, spec_number: str) -> SpecMetadata:
        """Fetch metadata for the given spec number."""
        ...
