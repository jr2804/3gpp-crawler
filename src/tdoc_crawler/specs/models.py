"""Specification query and filter models.

All persistent spec models live in tdoc_crawler.database.oxyde_models.
This module only contains pure-dataclass query models with no DB mapping.
"""

from dataclasses import dataclass, field

from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

from tdoc_crawler.utils.json_types import JSONValue


@dataclass(frozen=True, slots=True)
class SpecMetadata:
    """Metadata for one specification, as returned by a spec source.

    Attributes:
        spec_number: Normalized spec number (e.g. "26.131").
        source_name: Name of the source that produced the metadata.
        source_identifier: Identifier of the spec at the source (portal id or
            spec number); ``None`` when the source does not provide one.
        metadata_payload: Raw payload as returned by the source.
        versions: Version entries as returned by the source.
    """

    spec_number: str
    source_name: str
    source_identifier: int | str | None = None
    metadata_payload: dict[str, JSONValue] = field(default_factory=dict)
    versions: list[JSONValue] = field(default_factory=list)


@dataclass
class SpecQueryFilters:
    """Filter inputs for spec queries."""

    spec_numbers: list[str] | None = None
    title: str | None = None
    working_group: str | None = None
    status: str | None = None

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        _ = (console, options)
        yield Text(f"SpecQueryFilters(spec_numbers={self.spec_numbers})")


@dataclass
class SpecQueryResult:
    """Query result row for a spec."""

    spec_number: str
    title: str | None = None
    status: str | None = None
    working_group: str | None = None
    source_differences: dict[str, dict[str, str | None]] = field(default_factory=dict)

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        _ = (console, options)
        yield Text(f"{self.spec_number} - {self.title or 'Unknown'}")


__all__ = [
    "SpecMetadata",
    "SpecQueryFilters",
    "SpecQueryResult",
]
