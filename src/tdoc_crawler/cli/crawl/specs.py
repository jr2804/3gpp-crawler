"""Crawl specs command."""

from __future__ import annotations

import asyncio

from tdoc_crawler.cli._shared import console, handle_clear_options
from tdoc_crawler.cli.args import (
    CacheDirOption,
    CheckoutOption,
    ClearSpecsOption,
    ClearTDocsOption,
    OutputFormatOption,
    ReleaseOption,
    SpecArgument,
    SpecFileOption,
    VerbosityOption,
)
from tdoc_crawler.cli.formatting import format_output
from tdoc_crawler.cli.printing import print_spec_crawl_table, spec_crawl_to_dict
from tdoc_crawler.config import ThreeGPPConfig
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity
from tdoc_crawler.models.base import OutputFormat
from tdoc_crawler.specs.operations.checkout import build_default_spec_sources, checkout_specs
from tdoc_crawler.utils.parse import collect_spec_numbers


def crawl_specs(
    spec_numbers: SpecArgument = None,
    release: ReleaseOption = "latest",
    checkout: CheckoutOption = False,
    output_format: OutputFormatOption = OutputFormat.TABLE,
    clear_tdocs: ClearTDocsOption = False,
    clear_specs: ClearSpecsOption = False,
    spec_file: SpecFileOption = None,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Crawl spec metadata from configured sources."""
    set_verbosity(verbosity)
    crawler_config = ThreeGPPConfig.from_settings()
    if cache_dir is not None:
        crawler_config.path.cache_dir = cache_dir
    crawler_config.ensure_paths()
    spec_numbers = spec_numbers or []

    specs = collect_spec_numbers(spec_numbers, spec_file)

    sources = build_default_spec_sources()

    asyncio.run(
        handle_clear_options(
            crawler_config.path.db_file,
            crawler_config.path.checkout_dir,
            SpecDatabase,
            clear_tdocs=clear_tdocs,
            clear_specs=clear_specs,
        ),
    )

    async def crawl_specs_db() -> list:
        async with SpecDatabase(crawler_config.path.db_file) as database:
            return await database.crawl_specs(specs, release, sources)

    results = asyncio.run(crawl_specs_db())

    if not results:
        console.print("[yellow]No specs crawled[/yellow]")
        return

    if checkout:

        async def checkout_specs_db() -> None:
            async with SpecDatabase(crawler_config.path.db_file) as database:
                checkout_specs(
                    [result.spec_number for result in results],
                    crawler_config.path.checkout_dir,
                    database,
                    release=release,
                )

        asyncio.run(checkout_specs_db())

    if output_format is OutputFormat.TABLE:
        print_spec_crawl_table(results)
    else:
        data = [spec_crawl_to_dict(result) for result in results]
        console.print(format_output(data, output_format))
