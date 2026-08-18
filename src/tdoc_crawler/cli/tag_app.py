"""Tag CLI commands — lightweight grouping for TDocs, specs, and other items."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from tdoc_crawler.cli._shared import console
from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.tags import add_tags, list_tags, remove_tags
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity
from tdoc_crawler.models.base import TagKind
from tdoc_crawler.utils.async_helpers import run_async
from tdoc_crawler.utils.normalization import normalize_spec_number, normalize_tdoc_id

app = typer.Typer(help="Manage tags for TDocs, specs, and other items")
HELP_PANEL = "Tag Commands"


class TagKindChoice(StrEnum):
    """Item kind for tag operations."""

    TDOC = "tdoc"
    SPEC = "spec"
    OTHER = "other"

    def to_kind(self) -> TagKind:
        """Map CLI choice to TagKind."""
        return TagKind(self.value)


KindArgument = Annotated[
    TagKindChoice,
    typer.Argument(help="Item kind: tdoc, spec, or other"),
]
ItemsArgument = Annotated[
    list[str],
    typer.Argument(help="Item ids (TDoc ids like S4-250638, spec numbers like 26.444, or freeform ids)"),
]
TagsOption = Annotated[
    list[str],
    typer.Option("--tag", "-t", help="Tags to apply; comma-separate multiple values (repeatable)"),
]
TagFilterKindOption = Annotated[
    TagKindChoice | None,
    typer.Option("--kind", "-k", help="Filter by item kind"),
]
TagFilterItemOption = Annotated[
    str | None,
    typer.Option("--item", "-i", help="Filter by item id"),
]
TagFilterTagOption = Annotated[
    str | None,
    typer.Option("--tag", "-t", help="Filter by tag name"),
]


def _normalize_item(kind: TagKindChoice, item: str) -> str:
    """Normalize an item id per kind (tdoc/spec have canonical forms)."""
    if kind is TagKindChoice.TDOC:
        return normalize_tdoc_id(item)
    if kind is TagKindChoice.SPEC:
        return normalize_spec_number(item)
    return item.strip()


def tag_add(
    kind: KindArgument,
    items: ItemsArgument,
    tags: TagsOption,
    verbosity: Annotated[str, typer.Option("--verbosity", "-v", help="Verbosity level")] = str(DEFAULT_VERBOSITY),
) -> None:
    """Add tags to one or more items."""
    set_verbosity(verbosity)
    if not tags:
        console.print("[red]At least one --tag is required[/red]")
        raise typer.Exit(1)

    async def run() -> list[tuple[str, int]]:
        results: list[tuple[str, int]] = []
        async with TDocDatabase(_db_file()):
            for item in items:
                added = await add_tags(kind.to_kind(), _normalize_item(kind, item), [t for opt in tags for t in opt.split(",")])
                results.append((item, added))
        return results

    for item, added in run_async(run()):
        console.print(f"[green]{item}[/green]: {added} tag(s) added")


def tag_remove(
    kind: KindArgument,
    items: ItemsArgument,
    tags: Annotated[list[str], typer.Option("--tag", "-t", help="Tags to remove; omit to remove all tags")] = None,
    verbosity: Annotated[str, typer.Option("--verbosity", "-v", help="Verbosity level")] = str(DEFAULT_VERBOSITY),
) -> None:
    """Remove tags from one or more items (all tags if --tag is omitted)."""
    set_verbosity(verbosity)
    flat = [t for opt in (tags or []) for t in opt.split(",")] or None

    async def run() -> list[tuple[str, int]]:
        results: list[tuple[str, int]] = []
        async with TDocDatabase(_db_file()):
            for item in items:
                removed = await remove_tags(kind.to_kind(), _normalize_item(kind, item), flat)
                results.append((item, removed))
        return results

    for item, removed in run_async(run()):
        console.print(f"[yellow]{item}[/yellow]: {removed} tag(s) removed")


def tag_list(
    kind: TagFilterKindOption = None,
    item: TagFilterItemOption = None,
    tag: TagFilterTagOption = None,
    verbosity: Annotated[str, typer.Option("--verbosity", "-v", help="Verbosity level")] = str(DEFAULT_VERBOSITY),
) -> None:
    """List tags, optionally filtered by kind, item, or tag name."""
    set_verbosity(verbosity)

    async def run() -> list:
        async with TDocDatabase(_db_file()):
            return await list_tags(
                kind=kind.to_kind() if kind is not None else None,
                item_id=item,
                tag=tag,
            )

    rows = run_async(run())
    if not rows:
        console.print("[dim]No tags found.[/dim]")
        return
    for row in rows:
        console.print(f"[cyan]{row.kind:5s}[/cyan] {row.item_id:24s} [green]{row.tag}[/green]")


def _db_file() -> Path:
    """Resolve the database file from the default PathConfig."""
    return PathConfig().db_file


app.command("add", rich_help_panel=HELP_PANEL)(tag_add)
app.command("remove", rich_help_panel=HELP_PANEL)(tag_remove)
app.command("list", rich_help_panel=HELP_PANEL)(tag_list)

__all__ = ["app"]
