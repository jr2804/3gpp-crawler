"""Query specs command."""

from __future__ import annotations

import asyncio

import typer

from tdoc_crawler.cli._shared import console
from tdoc_crawler.cli.args import (
    CacheDirOption,
    CheckoutOption,
    OutputFormatOption,
    SpecArgument,
    SpecFileOption,
    StatusOption,
    TagFilterOption,
    TitleOption,
    VerbosityOption,
    WorkingGroupOption,
)
from tdoc_crawler.cli.formatting import format_output
from tdoc_crawler.cli.printing import print_spec_table, spec_query_to_dict
from tdoc_crawler.config import PathConfig, ThreeGPPConfig
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.database.tags import item_ids_for_tag_groups, parse_tag_groups
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity
from tdoc_crawler.models.base import OutputFormat, TagKind
from tdoc_crawler.specs.models import SpecQueryFilters
from tdoc_crawler.specs.operations.checkout import checkout_specs
from tdoc_crawler.utils.parse import collect_spec_numbers, parse_spec_working_group


def query_specs(
    spec_numbers: SpecArgument = None,
    title: TitleOption = None,
    working_group: WorkingGroupOption = None,
    status: StatusOption = None,
    output_format: OutputFormatOption = OutputFormat.TABLE,
    checkout: CheckoutOption = False,
    spec_file: SpecFileOption = None,
    cache_dir: CacheDirOption = None,
    tag: TagFilterOption = None,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Query spec metadata from database."""
    set_verbosity(verbosity)
    path_config = PathConfig(cache_dir=cache_dir) if cache_dir else PathConfig()
    specs = collect_spec_numbers(spec_numbers, spec_file)
    crawler_config = ThreeGPPConfig.from_settings()
    working_group_arg = working_group or ([crawler_config.crawl.working_group] if crawler_config.crawl.working_group else None)
    try:
        wg_filter = parse_spec_working_group(working_group_arg)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="'--working-group'") from exc

    filters = SpecQueryFilters(
        spec_numbers=specs,
        title=title,
        working_group=wg_filter,
        status=status,
    )

    db_file = path_config.db_file

    async def run_query() -> list:
        async with SpecDatabase(db_file) as database:
            results = await database.query_specs(filters)
            groups = parse_tag_groups(tag or [])
            if groups:
                matching = await item_ids_for_tag_groups(groups, TagKind.SPEC)
                results = [r for r in results if r.spec_number in matching]
            return results

    results = asyncio.run(run_query())

    if not results:
        console.print("[yellow]No specs found[/yellow]")
        return

    if checkout:
        spec_list = [result.spec_number for result in results]

        async def load_specs_for_checkout() -> None:
            async with SpecDatabase(db_file) as database:
                checkout_specs(spec_list, path_config.checkout_dir, database, release="latest")

        asyncio.run(load_specs_for_checkout())

    if output_format is OutputFormat.TABLE:
        print_spec_table(results)
    else:
        data = [spec_query_to_dict(result) for result in results]
        console.print(format_output(data, output_format))
