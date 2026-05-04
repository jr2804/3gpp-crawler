"""Query specs command."""

from __future__ import annotations

import asyncio

import typer

from tdoc_crawler.cli._shared import console, handle_clear_options
from tdoc_crawler.cli.args import (
    CacheDirOption,
    CheckoutOption,
    ClearSpecsOption,
    ClearTDocsOption,
    OutputFormatOption,
    SpecArgument,
    SpecFileOption,
    StatusOption,
    TitleOption,
    VerbosityOption,
    WorkingGroupOption,
)
from tdoc_crawler.cli.formatting import format_output
from tdoc_crawler.cli.printing import print_spec_table, spec_query_to_dict
from tdoc_crawler.config import PathConfig
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity
from tdoc_crawler.models.base import OutputFormat
from tdoc_crawler.specs.models import SpecQueryFilters
from tdoc_crawler.specs.operations.checkout import checkout_specs
from tdoc_crawler.utils.parse import collect_spec_numbers, parse_working_groups


def query_specs(
    spec_numbers: SpecArgument = None,
    title: TitleOption = None,
    working_group: WorkingGroupOption = None,
    status: StatusOption = None,
    output_format: OutputFormatOption = OutputFormat.TABLE.value,
    checkout: CheckoutOption = False,
    clear_tdocs: ClearTDocsOption = False,
    clear_specs: ClearSpecsOption = False,
    spec_file: SpecFileOption = None,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Query spec metadata from database."""
    set_verbosity(verbosity)
    path_config = PathConfig(cache_dir=cache_dir) if cache_dir else PathConfig()
    specs = collect_spec_numbers(spec_numbers, spec_file)
    working_groups = parse_working_groups(working_group)
    wg_filter = working_groups[0].value if working_groups else None

    filters = SpecQueryFilters(
        spec_numbers=specs,
        title=title,
        working_group=wg_filter,
        status=status,
    )

    try:
        output = OutputFormat(output_format.lower())
    except ValueError as exc:
        console.print("[red]Invalid output format; use table, json, jsonl, toon, or yaml")
        raise typer.Exit(code=2) from exc

    db_file = path_config.db_file
    handle_clear_options(
        db_file,
        path_config.checkout_dir,
        SpecDatabase,
        clear_tdocs=clear_tdocs,
        clear_specs=clear_specs,
    )

    async def run_query() -> list:
        async with SpecDatabase(db_file) as database:
            return await database.query_specs(filters)

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

    if output is OutputFormat.TABLE:
        print_spec_table(results)
    else:
        data = [spec_query_to_dict(result) for result in results]
        console.print(format_output(data, output))
