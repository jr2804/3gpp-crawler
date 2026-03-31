"""Spec commands for checkout and open operations."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from tdoc_crawler.cli._shared import console
from tdoc_crawler.cli.args import (
    CacheDirOption,
    CheckoutDirOption,
    DocOnlyOption,
    ReleaseOption,
    SpecArgument,
    SpecFileOption,
    VerbosityOption,
)
from tdoc_crawler.cli.printing import print_checkout_results
from tdoc_crawler.cli.utils import launch_file
from tdoc_crawler.config import PathConfig
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity
from tdoc_crawler.specs.downloads import SpecDownloads
from tdoc_crawler.specs.operations.checkout import build_default_spec_sources
from tdoc_crawler.utils.parse import collect_spec_numbers

HELP_PANEL = "Main Commands"


def checkout_spec(
    spec_numbers: SpecArgument = None,
    release: ReleaseOption = "latest",
    doc_only: DocOnlyOption = False,
    spec_file: SpecFileOption = None,
    cache_dir: CacheDirOption = None,
    checkout_dir: CheckoutDirOption = None,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Download and extract spec documents."""
    set_verbosity(verbosity)
    path = PathConfig(cache_dir=cache_dir) if cache_dir else PathConfig()
    if spec_numbers is None:
        spec_numbers = []
    specs = collect_spec_numbers(spec_numbers, spec_file)
    if not specs:
        console.print("[red]No specs provided[/red]")
        raise typer.Exit(code=1)

    effective_checkout_dir = checkout_dir or path.checkout_dir
    sources = build_default_spec_sources()

    db_file = path.db_file

    async def _run_checkout() -> list[Path]:
        async with SpecDatabase(db_file) as database:
            downloader = SpecDownloads(database)
            return downloader.checkout_specs(specs, doc_only, effective_checkout_dir, release, sources=sources)

    results = asyncio.run(_run_checkout())

    print_checkout_results(results)


def open_spec(
    spec: Annotated[str, typer.Argument(help="Spec number")],
    release: ReleaseOption = "latest",
    doc_only: DocOnlyOption = False,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Download and open a spec document."""
    set_verbosity(verbosity)
    normalized = spec.strip()
    path = PathConfig(cache_dir=cache_dir) if cache_dir else PathConfig()
    checkout_dir = path.checkout_dir

    sources = build_default_spec_sources()

    db_file = path.db_file

    async def _run_open() -> Path:
        async with SpecDatabase(db_file) as database:
            downloader = SpecDownloads(database)
            return downloader.open_spec(normalized, doc_only, checkout_dir, release, sources=sources)

    try:
        spec_file = asyncio.run(_run_open())
        console.print(f"[green]Opening {spec_file}[/green]")
        launch_file(spec_file)
    except Exception as exc:
        console.print(f"[red]Failed to open spec: {exc}[/red]")
        raise typer.Exit(code=1)


__all__ = [
    "HELP_PANEL",
    "checkout_spec",
    "open_spec",
]
