"""Crawl and enrich the work item catalogue from the DynaReport pages."""

from __future__ import annotations

import asyncio
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn

from tdoc_crawler.cli._shared import console, parse_scope, resolve_scope_args
from tdoc_crawler.cli.args import (
    CacheDirOption,
    LimitOption,
    OutputFormatOption,
    SubgroupOption,
    VerbosityOption,
    WorkingGroupOption,
    WorkItemOption,
)
from tdoc_crawler.cli.formatting import format_output
from tdoc_crawler.config import PathConfig, ThreeGPPConfig
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import LogLevel, set_verbosity
from tdoc_crawler.models.base import OutputFormat
from tdoc_crawler.workitems import WorkItemSourceError, discover_lead_bodies, fetch_work_items
from tdoc_crawler.workitems.operations import enrich_work_items, expand_area_codes, normalize_wg_codes


def crawl_work_items(
    working_group: WorkingGroupOption = None,
    subgroup: SubgroupOption = None,
    output_format: OutputFormatOption = OutputFormat.TABLE,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Crawl the public DynaReport work item lists into the catalogue.

    Sources are the per-lead-body lists (``TSG-WG--<WG>--wis.htm``), so a
    crawl can be limited to one lead body (``-s S4``, also historical codes
    like ``GP`` or ``T1``) or a whole area (``-w SA``, ``-w RAN``, ``-w CT``).
    Without a scope, the lead bodies are discovered from the global work
    item list.
    """
    crawler_config, path_config = _load_config(cache_dir, verbosity)

    working_group, subgroup = resolve_scope_args(
        working_group,
        subgroup,
        config_working_group=crawler_config.crawl.working_group,
        config_subgroup=crawler_config.crawl.sub_group,
    )
    codes = normalize_wg_codes(subgroup) or expand_area_codes(_parse_areas(working_group))
    source_note = "discovered from the global work item list"
    if not codes:
        try:
            codes = discover_lead_bodies(
                timeout=crawler_config.http.timeout,
                http_config=crawler_config.http,
                http_cache_file=path_config.http_cache_file,
            )
        except WorkItemSourceError as exc:
            console.print(f"[red]Failed to discover lead bodies:[/red] {exc}")
            raise SystemExit(1) from exc
    else:
        source_note = ",".join(codes)

    try:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress_bar:
            task = progress_bar.add_task("Crawling work item lists…", total=len(codes))
            results = fetch_work_items(
                codes,
                timeout=crawler_config.http.timeout,
                http_config=crawler_config.http,
                http_cache_file=path_config.http_cache_file,
                progress=lambda _code: progress_bar.advance(task),
            )
    except WorkItemSourceError as exc:
        console.print(f"[red]Failed to fetch the work item lists:[/red] {exc}")
        raise SystemExit(1) from exc

    work_items = [item for items in results.values() for item in items]

    async def _store() -> int:
        async with TDocDatabase(path_config.db_file) as database:
            return await database.store_work_items(work_items)

    stored = asyncio.run(_store())
    summary = {
        "lead_bodies": {code: len(items) for code, items in results.items()},
        "work_items": len(work_items),
        "stored": stored,
        "source": source_note,
    }

    if output_format is OutputFormat.TABLE:
        per_group = ", ".join(f"{code}: {count}" for code, count in summary["lead_bodies"].items())
        console.print(f"Stored [bold]{summary['work_items']}[/bold] work items ({per_group})")
        return

    console.print(format_output([summary], output_format))


def _parse_areas(working_group):  # noqa: ANN001, ANN202
    """Parse the working group option into WorkingGroup values (may stay empty)."""
    working_groups, _ = parse_scope(working_group, None, default_to_all=False)
    return working_groups


def enrich_work_items_command(
    work_item: WorkItemOption = None,
    limit: LimitOption = None,
    include_all: bool = False,
    output_format: OutputFormatOption = OutputFormat.TABLE,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Enrich work items from the portal details, spec and CR pages.

    Default selection: work items referenced by crawled TDocs plus the ones
    never enriched. Pass ``--include-all`` for every catalogue row, or
    explicit IDs via ``--work-item``.
    """
    crawler_config, path_config = _load_config(cache_dir, verbosity)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress_bar:
        task = progress_bar.add_task("Enriching work items…", total=None)
        summary = enrich_work_items(
            path_config.db_file,
            work_item,
            limit=limit,
            include_all=include_all,
            timeout=crawler_config.http.timeout,
            http_config=crawler_config.http,
            http_cache_file=path_config.http_cache_file,
            progress=lambda _wi_id: progress_bar.advance(task),
        )

    payload = {
        "enriched": summary.enriched,
        "specs_found": summary.specs_found,
        "crs_found": summary.crs_found,
        "parents_found": summary.parents_found,
        "skipped": summary.skipped,
        "failed": summary.failed,
        "errors": summary.errors,
    }
    if output_format is OutputFormat.TABLE:
        console.print(
            f"Enriched [bold]{summary.enriched}[/bold] work items ({summary.specs_found} specs, {summary.crs_found} CRs, {summary.parents_found} with parent)"
        )
        if summary.skipped or summary.failed:
            console.print(f"[yellow]{summary.skipped} skipped, {summary.failed} failed[/yellow]")
        for error in summary.errors:
            console.print(f"  [dim]{error}[/dim]")
        return
    console.print(format_output([payload], output_format))


def _load_config(cache_dir: Path | None, verbosity: LogLevel) -> tuple[ThreeGPPConfig, PathConfig]:
    """Load the CLI config and derive the path config."""
    set_verbosity(verbosity)
    crawler_config = ThreeGPPConfig.from_settings()
    if cache_dir is not None:
        crawler_config.path.cache_dir = cache_dir
    crawler_config.ensure_paths()
    return crawler_config, PathConfig(cache_dir=crawler_config.path.cache_dir)


__all__ = ["crawl_work_items", "enrich_work_items_command"]
