"""Query command functions — re-exported from submodules."""

from tdoc_crawler.cli.query.meetings import query_meetings
from tdoc_crawler.cli.query.specs import query_specs
from tdoc_crawler.cli.query.tdocs import query_tdocs

HELP_PANEL = "Query Commands"

__all__ = [
    "HELP_PANEL",
    "query_meetings",
    "query_specs",
    "query_tdocs",
]
