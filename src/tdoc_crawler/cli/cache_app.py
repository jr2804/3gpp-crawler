"""HTTP cache maintenance CLI — inspect and reclaim the HTTP cache database.

Mounted on ``3gpp-crawler`` as ``cache``. Hishel expires HTTP cache entries on
reads and reclaims rows lazily, but SQLite never returns freed pages to the
filesystem: the database file can grow far larger than its live payload.
``cache prune`` removes expired rows, optionally evicts to a size bound, and
vacuums the file.
"""

from __future__ import annotations

from typing import Annotated

import typer

from tdoc_crawler.cli._shared import GlobSafeTyper
from tdoc_crawler.cli.args import CacheDirOption, OutputFormatOption
from tdoc_crawler.cli.formatting import print_structured_output
from tdoc_crawler.config.settings import HttpConfig, PathConfig
from tdoc_crawler.http_client import prune_http_cache
from tdoc_crawler.models.base import OutputFormat

HELP_PANEL = "Cache Commands"

app = GlobSafeTyper(help="Inspect and reclaim the HTTP cache database")

MaxBytesOption = Annotated[
    int | None,
    typer.Option(
        "--max-bytes",
        help="Evict least-recently-used entries until the live cache is at or below this size (0 or negative = no eviction)",
    ),
]


@app.command("prune")
def cache_prune(
    max_bytes: MaxBytesOption = None,
    cache_dir: CacheDirOption = None,
    output: OutputFormatOption = OutputFormat.TABLE,
) -> None:
    """Delete expired HTTP cache entries, evict to a size bound, and vacuum.

    With no ``--max-bytes``, the configured ``http.cache_max_bytes`` limit is
    used. Pass ``--max-bytes 0`` (or a negative value) to skip eviction
    entirely and only remove expired entries before vacuuming.
    """
    paths = PathConfig(cache_dir=cache_dir) if cache_dir else PathConfig()
    configured_max = HttpConfig().cache_max_bytes
    if max_bytes is None:
        limit = configured_max if configured_max > 0 else None
    elif max_bytes <= 0:
        limit = None
    else:
        limit = max_bytes

    stats = prune_http_cache(paths.http_cache_file, max_bytes=limit)
    print_structured_output(
        {
            "cache_file": str(paths.http_cache_file),
            "entries_before": stats.entries_before,
            "entries_after": stats.entries_after,
            "expired_removed": stats.expired_removed,
            "evicted": stats.evicted,
            "bytes_before": stats.bytes_before,
            "bytes_after": stats.bytes_after,
            "reclaimed_bytes": stats.reclaimed_bytes,
            "vacuumed": stats.vacuumed,
        },
        output,
        table_title="HTTP cache prune",
    )


__all__ = ["app"]
