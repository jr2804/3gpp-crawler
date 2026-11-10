"""Tag CLI commands — lightweight grouping for TDocs, specs, and other items."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from tdoc_crawler.cli._shared import GlobSafeTyper, console
from tdoc_crawler.cli.args import OutputFormatOption, TagFilterKindOption, TagKindChoice
from tdoc_crawler.cli.formatting import TAG_COLUMNS, TableColumnSpec, print_structured_output
from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.tag_transfer import normalize_item_id
from tdoc_crawler.database.tags import add_tags, list_tags, remove_tags
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import LogLevel, set_verbosity
from tdoc_crawler.models.base import OutputFormat
from tdoc_crawler.utils.async_helpers import run_async

HELP_PANEL = "Tag Commands"

app = GlobSafeTyper(help="Manage tags for TDocs, specs, and other items")


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
TagFilterItemOption = Annotated[
    str | None,
    typer.Option("--item", "-i", help="Filter by item id"),
]
TagFilterTagOption = Annotated[
    str | None,
    typer.Option("--tag", "-t", help="Filter by tag name"),
]


def tag_add(
    kind: KindArgument,
    items: ItemsArgument,
    tags: TagsOption,
    output_format: OutputFormatOption = OutputFormat.TABLE,
    verbosity: Annotated[LogLevel, typer.Option("--verbosity", "-v", help="Verbosity level")] = DEFAULT_VERBOSITY,
) -> None:
    """Add tags to one or more items."""
    set_verbosity(verbosity)
    if not tags:
        console.print("[red]At least one --tag is required[/red]")
        raise typer.Exit(1)
    flat_tags = [t for opt in tags for t in opt.split(",")]

    async def run() -> list[dict]:
        results: list[dict] = []
        async with TDocDatabase(_db_file()):
            for item in items:
                added = await add_tags(kind.to_kind(), normalize_item_id(kind.to_kind(), item), flat_tags)
                results.append({"item": item, "added": added})
        return results

    print_structured_output(
        run_async(run()),
        output_format,
        table_title="Tags added",
        table_columns=[TableColumnSpec(key="item", header="Item"), TableColumnSpec(key="added", header="Added", justify="right")],
    )


def tag_remove(
    kind: KindArgument,
    items: ItemsArgument,
    tags: Annotated[list[str], typer.Option("--tag", "-t", help="Tags to remove; omit to remove all tags")] = None,
    output_format: OutputFormatOption = OutputFormat.TABLE,
    verbosity: Annotated[LogLevel, typer.Option("--verbosity", "-v", help="Verbosity level")] = DEFAULT_VERBOSITY,
) -> None:
    """Remove tags from one or more items (all tags if --tag is omitted)."""
    set_verbosity(verbosity)
    flat = [t for opt in (tags or []) for t in opt.split(",")] or None

    async def run() -> list[dict]:
        results: list[dict] = []
        async with TDocDatabase(_db_file()):
            for item in items:
                removed = await remove_tags(kind.to_kind(), normalize_item_id(kind.to_kind(), item), flat)
                results.append({"item": item, "removed": removed})
        return results

    print_structured_output(
        run_async(run()),
        output_format,
        table_title="Tags removed",
        table_columns=[TableColumnSpec(key="item", header="Item"), TableColumnSpec(key="removed", header="Removed", justify="right")],
    )


def tag_list(
    kind: TagFilterKindOption = None,
    item: TagFilterItemOption = None,
    tag: TagFilterTagOption = None,
    output_format: OutputFormatOption = OutputFormat.TABLE,
    verbosity: Annotated[LogLevel, typer.Option("--verbosity", "-v", help="Verbosity level")] = DEFAULT_VERBOSITY,
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
    if not rows and output_format is OutputFormat.TABLE:
        console.print("[dim]No tags found.[/dim]")
        return
    print_structured_output(
        [{"kind": row.kind, "item_id": row.item_id, "tag": row.tag} for row in rows],
        output_format,
        table_title="Tags",
        table_columns=TAG_COLUMNS,
    )


def _db_file() -> Path:
    """Resolve the database file from the default PathConfig."""
    return PathConfig().db_file


app.command("add", rich_help_panel=HELP_PANEL)(tag_add)
app.command("remove", rich_help_panel=HELP_PANEL)(tag_remove)
app.command("list", rich_help_panel=HELP_PANEL)(tag_list)

__all__ = ["app"]
