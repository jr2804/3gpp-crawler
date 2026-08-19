"""MCP server for 3gpp-crawler — exposes crawler capabilities via stdio MCP tools."""

from __future__ import annotations

import io
import sys
from collections.abc import Callable
from typing import Any

import typer
from fastmcp import FastMCP
from pool_executors import ExecutorType

from tdoc_crawler.cli.config_app import (
    config_show as cli_config_show,
)
from tdoc_crawler.cli.config_app import (
    config_validate as cli_config_validate,
)
from tdoc_crawler.cli.crawl.meetings import crawl_meetings as cli_crawl_meetings
from tdoc_crawler.cli.crawl.specs import crawl_specs as cli_crawl_specs
from tdoc_crawler.cli.crawl.tdocs import crawl_tdocs as cli_crawl_tdocs
from tdoc_crawler.cli.query.meetings import query_meetings as cli_query_meetings
from tdoc_crawler.cli.query.specs import query_specs as cli_query_specs
from tdoc_crawler.cli.query.tdocs import query_tdocs as cli_query_tdocs
from tdoc_crawler.cli.specs import checkout_spec as cli_checkout_spec
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
from tdoc_crawler.cli.tdoc_app import checkout as cli_checkout_tdoc
from tdoc_crawler.config import PathConfig

# Multiprocessing spawn is unsafe under the stdio server (children inherit
# overlapped stdio handles and deadlock). Use in-process parallelism instead.
# Subinterpreter wins on Python 3.14+ because it sidesteps the GIL; threading
# elsewhere. The factory transparently falls back to multiprocessing for
# ExecutorType.SUBINTERPRETER on older Pythons, so we have to pick ourselves
# rather than passing SUBINTERPRETER unconditionally.
_MCP_EXECUTOR: ExecutorType = (
    ExecutorType.SUBINTERPRETER if sys.version_info >= (3, 14) else ExecutorType.THREADING
)

mcp = FastMCP("3gpp-crawler", instructions="3GPP specification & TDoc crawler MCP server")


# --- CHECKOUT / DOWNLOAD GROUP ---


class _DummyContext:
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
        "Scope with start_date/end_date, limit_meetings or limit_tdocs for speed"
    ),
)
def crawl_tdocs(
    working_group: list[str] | None = None,
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


@mcp.tool(name="crawl_meetings", description="Crawl meeting metadata from 3GPP portal")
def crawl_meetings(
    working_group: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    return _run_captured(
        cli_crawl_meetings,
        working_group=working_group,
        start_date=start_date,
        end_date=end_date,
    )


# --- QUERY GROUP ---


@mcp.tool(name="query_tdocs", description="Query stored TDoc metadata with optional filtering by tag, WG, dates, title pattern, etc.")
def query_tdocs(
    tdoc_ids: list[str] | None = None,
    working_group: list[str] | None = None,
    tag: list[str] | None = None,
    title: list[str] | None = None,
    agenda: str | None = None,
    limit: int | None = None,
) -> str:
    return _run_captured(
        cli_query_tdocs,
        tdoc_ids=tdoc_ids,
        working_group=working_group,
        tag=tag,
        title=title,
        agenda=agenda,
        limit=limit,
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
        working_group=working_group,
        tag=tag,
    )


@mcp.tool(name="query_meetings", description="Query stored 3GPP meetings metadata")
def query_meetings(
    working_group: list[str] | None = None,
) -> str:
    return _run_captured(
        cli_query_meetings,
        working_group=working_group,
    )


@mcp.tool(name="checkout_tdocs", description="Download and extract TDocs to checkout directory")
def checkout_tdocs(
    tdoc_ids: list[str],
    force: bool = False,
    pdf: bool = False,
) -> str:
    return _run_captured(
        cli_checkout_tdoc,
        ctx=_DummyContext(),
        tdoc_ids=tdoc_ids,
        force=force,
        pdf=pdf,
    )


@mcp.tool(name="checkout_specs", description="Download and extract 3GPP specifications to checkout directory")
def checkout_specs(
    spec_numbers: list[str],
    release: str = "latest",
    doc_only: bool = False,
    pdf: bool = False,
) -> str:
    return _run_captured(
        cli_checkout_spec,
        spec_numbers=spec_numbers,
        release=release,
        doc_only=doc_only,
        pdf=pdf,
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
        tags=tags,
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


def _run_captured(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
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


# --- CONFIG GROUP ---


@mcp.tool(name="config_show", description="Show active configuration values")
def config_show() -> str:
    return _run_captured(cli_config_show)


@mcp.tool(name="config_validate", description="Validate configuration files and path settings")
def config_validate() -> str:
    return _run_captured(cli_config_validate)


def run_mcp() -> None:
    """Run the FastMCP server via stdio."""
    mcp.run()
