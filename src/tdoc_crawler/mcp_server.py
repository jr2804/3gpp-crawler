"""MCP server for 3gpp-crawler — exposes crawler capabilities via stdio MCP tools."""

from __future__ import annotations

import io
import sys
from collections.abc import Callable
from pathlib import Path
from typing import ParamSpec, TypeVar

import typer
from fastmcp import FastMCP

from tdoc_crawler.cli.checkout import checkout_tdocs as cli_checkout_tdoc
from tdoc_crawler.cli.checkout import list_tdoc_files as cli_list_tdoc_files
from tdoc_crawler.cli.config_app import (
    config_show as cli_config_show,
)
from tdoc_crawler.cli.config_app import (
    config_validate as cli_config_validate,
)
from tdoc_crawler.cli.crawl.meetings import crawl_meetings as cli_crawl_meetings
from tdoc_crawler.cli.crawl.specs import crawl_specs as cli_crawl_specs
from tdoc_crawler.cli.crawl.tdocs import crawl_tdocs as cli_crawl_tdocs
from tdoc_crawler.cli.crawl.work_items import crawl_work_items as cli_crawl_work_items
from tdoc_crawler.cli.crawl.work_items import enrich_work_items_command as cli_enrich_work_items
from tdoc_crawler.cli.database_app import (
    clear_all as cli_database_clear_all,
)
from tdoc_crawler.cli.database_app import (
    clear_meetings as cli_database_clear_meetings,
)
from tdoc_crawler.cli.database_app import (
    clear_specs as cli_database_clear_specs,
)
from tdoc_crawler.cli.database_app import (
    clear_tdocs as cli_database_clear_tdocs,
)
from tdoc_crawler.cli.database_app import (
    tag_export as cli_database_export_tags,
)
from tdoc_crawler.cli.database_app import (
    tag_import as cli_database_import_tags,
)
from tdoc_crawler.cli.query.meetings import query_meetings as cli_query_meetings
from tdoc_crawler.cli.query.specs import query_specs as cli_query_specs
from tdoc_crawler.cli.query.tdocs import query_tdocs as cli_query_tdocs
from tdoc_crawler.cli.query.work_items import query_work_items as cli_query_work_items
from tdoc_crawler.cli.specs import checkout_spec as cli_checkout_spec
from tdoc_crawler.cli.specs import list_spec_files as cli_list_spec_files
from tdoc_crawler.cli.tag_app import (
    TagKindChoice,
)
from tdoc_crawler.cli.tag_app import (
    tag_add as cli_tag_add,
)
from tdoc_crawler.cli.tag_app import (
    tag_list as cli_tag_list,
)
from tdoc_crawler.cli.tag_app import (
    tag_remove as cli_tag_remove,
)
from tdoc_crawler.config import PathConfig
from tdoc_crawler.executors import ExecutorType, best_executor_type
from tdoc_crawler.models.base import SortKey, SortOrder

# Multiprocessing spawn is unsafe under the stdio server (children inherit
# overlapped stdio handles and deadlock), so processes are excluded here.
_MCP_EXECUTOR: ExecutorType = best_executor_type(allow_processes=False)


# --- DATABASE GROUP ---

# MCP callers are agents, not humans: typer.confirm() has nobody to answer it.
# Destructive tools therefore refuse to run unless the caller explicitly sets
# confirm=true — a deliberate speed bump that costs one extra tool round-trip.
_DATABASE_REFUSAL = "Refused: destructive database operation. Re-invoke with confirm=true to proceed."

P = ParamSpec("P")
T = TypeVar("T")

mcp = FastMCP("3gpp-crawler", instructions="3GPP specification & TDoc crawler MCP server")


# --- CHECKOUT / DOWNLOAD GROUP ---


class _DummyContext(typer.Context):
    """Context stand-in for CLI calls that only read ``ctx.obj``."""

    class _Obj:
        def __init__(self) -> None:
            self.path = PathConfig()

    def __init__(self) -> None:
        self.obj = self._Obj()


# --- CRAWL GROUP ---


@mcp.tool(
    name="crawl_tdocs",
    description=(
        "Crawl TDoc metadata from 3GPP meeting document lists (Excel). "
        "Scope with subgroup (e.g. ['SA4'] for SA WG4, ['R1'], ['CT1']) and/or working_group "
        "(RAN/SA/CT only), plus start_date/end_date, limit_meetings or limit_tdocs for speed"
    ),
)
def crawl_tdocs(
    working_group: list[str] | None = None,
    subgroup: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    title: list[str] | None = None,
    source: list[str] | None = None,
    agenda: list[str] | None = None,
    limit_meetings: int | None = None,
    limit_tdocs: int | None = None,
    workers: int = 4,
) -> str:
    return _run_captured(
        cli_crawl_tdocs,
        working_group=working_group,
        subgroup=subgroup,
        start_date=start_date,
        end_date=end_date,
        title=title,
        source=source,
        agenda=agenda,
        limit_meetings=limit_meetings,
        limit_tdocs=limit_tdocs,
        workers=workers,
        executor=_MCP_EXECUTOR,
        show_progress=False,
    )


@mcp.tool(name="crawl_specs", description="Crawl 3GPP specification metadata")
def crawl_specs(
    spec_numbers: list[str] | None = None,
    release: str = "latest",
) -> str:
    return _run_captured(
        cli_crawl_specs,
        spec_numbers=spec_numbers,
        release=release,
    )


@mcp.tool(
    name="crawl_meetings",
    description=(
        "Crawl meeting metadata from 3GPP portal. "
        "Use subgroup for sub-working groups (e.g. ['SA4'], ['S4'], ['R1'], ['CT1']); "
        "working_group accepts only RAN/SA/CT and would otherwise crawl the plenary"
    ),
)
def crawl_meetings(
    working_group: list[str] | None = None,
    subgroup: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    return _run_captured(
        cli_crawl_meetings,
        working_group=working_group,
        subgroup=subgroup,
        start_date=start_date,
        end_date=end_date,
    )


# --- QUERY GROUP ---


@mcp.tool(
    name="query_tdocs",
    description=(
        "Query stored TDoc metadata with optional filtering by tag, WG, subgroup, work item, dates, title pattern, etc. "
        "working_group accepts only RAN/SA/CT; filter sub-working groups with subgroup (e.g. ['SA4'], ['S4']); "
        "filter by 3GPP work item with work_item (e.g. ['ULBC-MED']), taken from the document list 'Related WIs' column; "
        "filter by agenda item text with agenda (e.g. ['ULBC']), which also matches the text of parent agenda items"
    ),
)
def query_tdocs(
    tdoc_ids: list[str] | None = None,
    working_group: list[str] | None = None,
    subgroup: list[str] | None = None,
    work_item: list[str] | None = None,
    spec_number: list[str] | None = None,
    tag: list[str] | None = None,
    title: list[str] | None = None,
    agenda: list[str] | None = None,
    limit: int | None = None,
    sort_by: str | None = None,
    order: str | None = None,
) -> str:
    return _run_captured(
        cli_query_tdocs,
        tdoc_ids=tdoc_ids,
        working_group=working_group,
        subgroup=subgroup,
        work_item=work_item,
        spec_number=spec_number,
        tag=tag,
        title=title,
        agenda=agenda,
        limit=limit,
        sort_by=_sort_key(sort_by),
        order=_sort_order(order),
    )


@mcp.tool(
    name="query_work_items",
    description=(
        "List 3GPP work items from the catalogue (titles, release, status, lead body, parent work item, "
        "impacted specifications) together with the number of crawled TDocs that reference each work item. "
        "Pass work_item_ids to look up specific work items (e.g. ['ULBC-MED']); crawl_error means the "
        "catalogue has not been crawled yet. Run crawl_work_items once to populate it"
    ),
)
def query_work_items(
    work_item_ids: list[str] | None = None,
    working_group: list[str] | None = None,
    release: str | None = None,
    status: str | None = None,
    show_specs: bool = False,
    limit: int | None = None,
) -> str:
    return _run_captured(
        cli_query_work_items,
        work_item_ids=work_item_ids,
        working_group=working_group,
        release=release,
        status=status,
        show_specs=show_specs,
        limit=limit,
    )


@mcp.tool(
    name="crawl_work_items",
    description=(
        "Crawl the public DynaReport work item lists and store the work item catalogue "
        "(work item IDs, UIDs, titles, releases, lead bodies). "
        "Scope with subgroup=['S4'] (one lead body, historical codes like 'GP' work too) or "
        "working_group=['SA']/['RAN']/['CT'] (a whole area); without a scope all lead bodies "
        "are discovered from the global work item list. Run it before query_work_items"
    ),
)
def crawl_work_items(
    working_group: list[str] | None = None,
    subgroup: list[str] | None = None,
) -> str:
    return _run_captured(
        cli_crawl_work_items,
        working_group=working_group,
        subgroup=subgroup,
    )


@mcp.tool(
    name="enrich_work_items",
    description=(
        "Enrich work items with portal detail pages: status, parent/child work items, "
        "rapporteur, impacted specifications and related change requests. "
        "Default selection: work items referenced by crawled TDocs plus never-enriched ones; "
        "pass work_item=['ULBC-MED'] for specific IDs or include_all=true for the whole catalogue"
    ),
)
def enrich_work_items(
    work_item: list[str] | None = None,
    limit: int | None = None,
    include_all: bool = False,
) -> str:
    return _run_captured(
        cli_enrich_work_items,
        work_item=work_item,
        limit=limit,
        include_all=include_all,
    )


@mcp.tool(name="query_specs", description="Query stored 3GPP specifications metadata")
def query_specs(
    spec_numbers: list[str] | None = None,
    title: str | None = None,
    working_group: str | None = None,
    tag: list[str] | None = None,
) -> str:
    return _run_captured(
        cli_query_specs,
        spec_numbers=spec_numbers,
        title=title,
        working_group=[working_group] if working_group else None,
        tag=tag,
    )


@mcp.tool(
    name="query_meetings",
    description=("Query stored 3GPP meetings metadata. Filter sub-working groups with subgroup (e.g. ['SA4']); working_group accepts only RAN/SA/CT"),
)
def query_meetings(
    working_group: list[str] | None = None,
    subgroup: list[str] | None = None,
) -> str:
    return _run_captured(
        cli_query_meetings,
        working_group=working_group,
        subgroup=subgroup,
    )


@mcp.tool(name="checkout_tdocs", description="Download and extract TDocs to checkout directory")
def checkout_tdocs(
    tdoc_ids: list[str],
    force: bool = False,
    keep_zip: bool = False,
) -> str:
    return _run_captured(
        cli_checkout_tdoc,
        ctx=_DummyContext(),
        tdoc_ids=tdoc_ids,
        force=force,
        keep_zip=keep_zip,
    )


@mcp.tool(name="list_tdoc_files", description="List the files inside a TDoc's zip archive (stored listing, remote listing on first use)")
def list_tdoc_files(
    tdoc_id: str,
    refresh: bool = False,
) -> str:
    return _run_captured(
        cli_list_tdoc_files,
        ctx=_DummyContext(),
        tdoc_id=tdoc_id,
        refresh=refresh,
    )


@mcp.tool(name="checkout_specs", description="Download and extract 3GPP specifications to checkout directory")
def checkout_specs(
    spec_numbers: list[str],
    release: str = "latest",
    doc_only: bool = False,
) -> str:
    return _run_captured(
        cli_checkout_spec,
        spec_numbers=spec_numbers,
        release=release,
        doc_only=doc_only,
    )


@mcp.tool(name="list_spec_files", description="List the files inside a 3GPP specification's zip archive (stored listing, remote listing on first use)")
def list_spec_files(
    spec_number: str,
    release: str = "latest",
    refresh: bool = False,
) -> str:
    return _run_captured(
        cli_list_spec_files,
        spec_number=spec_number,
        release=release,
        refresh=refresh,
    )


# --- TAG GROUP ---


@mcp.tool(name="tag_add", description="Add tags to items (tdoc, spec, or other)")
def tag_add(
    kind: str,
    items: list[str],
    tags: list[str],
) -> str:
    return _run_captured(
        cli_tag_add,
        kind=TagKindChoice(kind.lower()),
        items=items,
        tags=tags,
    )


@mcp.tool(name="tag_remove", description="Remove tags from items")
def tag_remove(
    kind: str,
    items: list[str],
    tags: list[str] | None = None,
) -> str:
    return _run_captured(
        cli_tag_remove,
        kind=TagKindChoice(kind.lower()),
        items=items,
        tags=tags or [],
    )


@mcp.tool(name="tag_list", description="List tags for items")
def tag_list(
    kind: str | None = None,
    item: str | None = None,
    tag: str | None = None,
) -> str:
    return _run_captured(
        cli_tag_list,
        kind=TagKindChoice(kind.lower()) if kind else None,
        item=item,
        tag=tag,
    )


@mcp.tool(
    name="database_clear_tdocs",
    description="Delete all TDoc records and their checkout entries from the database (destructive)",
)
def database_clear_tdocs(confirm: bool = False) -> str:
    if not confirm:
        return _DATABASE_REFUSAL
    return _run_captured(cli_database_clear_tdocs)


@mcp.tool(
    name="database_clear_specs",
    description="Delete all specification records and their checkout entries from the database (destructive)",
)
def database_clear_specs(confirm: bool = False) -> str:
    if not confirm:
        return _DATABASE_REFUSAL
    return _run_captured(cli_database_clear_specs)


@mcp.tool(
    name="database_clear_meetings",
    description="Delete all meeting records from the database, keeping TDoc records (destructive)",
)
def database_clear_meetings(confirm: bool = False) -> str:
    if not confirm:
        return _DATABASE_REFUSAL
    return _run_captured(cli_database_clear_meetings)


@mcp.tool(
    name="database_clear_all",
    description=(
        "Delete the whole database file and recreate it on next use, preserving tags (destructive; this is the rebuild path named by schema-mismatch errors)"
    ),
)
def database_clear_all(confirm: bool = False) -> str:
    if not confirm:
        return _DATABASE_REFUSAL
    return _run_captured(cli_database_clear_all, yes=True)


@mcp.tool(
    name="database_export_tags",
    description="Export tags as natural-key records (kind, item_id, tag); pass file to write a backup dump, otherwise returns the dump text (JSON)",
)
def database_export_tags(
    kind: str | None = None,
    file: str | None = None,
) -> str:
    return _run_captured(
        cli_database_export_tags,
        kind=TagKindChoice(kind.lower()) if kind else None,
        file=Path(file) if file else None,
    )


@mcp.tool(
    name="database_import_tags",
    description="Import tags from a JSON or YAML dump written by database_export_tags (existing tag rows are skipped)",
)
def database_import_tags(file: str) -> str:
    return _run_captured(cli_database_import_tags, Path(file))


# --- CONFIG GROUP ---


@mcp.tool(name="config_show", description="Show active configuration values")
def config_show() -> str:
    return _run_captured(cli_config_show)


@mcp.tool(name="config_validate", description="Validate configuration files and path settings")
def config_validate() -> str:
    return _run_captured(cli_config_validate)


def _sort_key(value: str | None) -> SortKey:
    """Convert an MCP sort key into the CLI enum.

    Args:
        value: Sort key name (e.g. ``meeting_date``) or ``None``.

    Returns:
        The matching :class:`SortKey`, defaulting to ``MEETING_DATE``.

    Raises:
        ValueError: If the name is not a known sort key.
    """
    if value is None:
        return SortKey.MEETING_DATE
    try:
        return SortKey(value)
    except ValueError as exc:
        msg = f"Unknown sort_by {value!r}; expected one of {', '.join(key.value for key in SortKey)}"
        raise ValueError(msg) from exc


def _sort_order(value: str | None) -> SortOrder:
    """Convert an MCP sort order into the CLI enum.

    Args:
        value: Sort order name (``asc``/``desc``) or ``None``.

    Returns:
        The matching :class:`SortOrder`, defaulting to ``ASC``.

    Raises:
        ValueError: If the name is not a known sort order.
    """
    if value is None:
        return SortOrder.ASC
    try:
        return SortOrder(value)
    except ValueError as exc:
        msg = f"Unknown order {value!r}; expected one of {', '.join(order.value for order in SortOrder)}"
        raise ValueError(msg) from exc


def _run_captured[**P, T](fn: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> str:
    """Run a CLI function with stdout/stderr captured into a string."""
    buffer = io.StringIO()
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = buffer
    sys.stderr = buffer
    try:
        fn(*args, **kwargs)
    except (SystemExit, typer.Exit):
        pass
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
    return buffer.getvalue()


def run_mcp() -> None:
    """Run the FastMCP server via stdio."""
    mcp.run()
