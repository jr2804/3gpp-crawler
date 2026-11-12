"""Query meetings command."""

from __future__ import annotations

import asyncio

from tdoc_crawler.cli._shared import console, parse_scope
from tdoc_crawler.cli.args import (
    CacheDirOption,
    CheckoutOption,
    IncludeWithoutFilesOption,
    LimitOption,
    OrderOption,
    OutputFormatOption,
    SubgroupOption,
    VerbosityOption,
    WorkingGroupOption,
)
from tdoc_crawler.cli.formatting import format_output
from tdoc_crawler.cli.printing import meeting_to_dict, print_meeting_table
from tdoc_crawler.config import PathConfig, ThreeGPPConfig
from tdoc_crawler.database import MeetingDatabase
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity
from tdoc_crawler.meetings.models import MeetingQueryConfig
from tdoc_crawler.models.base import OutputFormat, SortOrder
from tdoc_crawler.tdocs.operations.checkout import checkout_meeting_tdocs


def query_meetings(
    working_group: WorkingGroupOption = None,
    subgroup: SubgroupOption = None,
    limit: LimitOption = None,
    order: OrderOption = SortOrder.DESC,
    output_format: OutputFormatOption = OutputFormat.TABLE,
    checkout: CheckoutOption = False,
    include_without_files: IncludeWithoutFilesOption = False,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Query meeting metadata from database."""
    set_verbosity(verbosity)
    path_config = PathConfig(cache_dir=cache_dir) if cache_dir else PathConfig()
    # Query semantics: no working_group filter unless the user asked for one.
    crawler_config = ThreeGPPConfig.from_settings()
    working_groups, subgroups = parse_scope(
        working_group,
        subgroup,
        default_to_all=False,
        config_working_group=crawler_config.crawl.working_group,
        config_subgroup=crawler_config.crawl.sub_group,
    )
    config = MeetingQueryConfig(
        working_groups=working_groups,
        subgroups=subgroups,
        limit=limit,
        order=order,
        include_without_files=include_without_files,
    )

    db_file = path_config.db_file

    async def run_query() -> list:
        async with MeetingDatabase(db_file) as database:
            return await database.query_meetings(config)

    meetings = asyncio.run(run_query())

    if not meetings:
        console.print("[yellow]No meetings found[/yellow]")
        return

    if checkout:
        with create_cached_session() as session:
            checkout_meeting_tdocs(meetings, path_config.checkout_dir, path_config.http_cache_file, session=session)

    if output_format is OutputFormat.TABLE:
        print_meeting_table(meetings)
    else:
        data = [meeting_to_dict(meeting) for meeting in meetings]
        console.print(format_output(data, output_format))
