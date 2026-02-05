"""Spec query filters and results."""

from dataclasses import dataclass, field

from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text


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
