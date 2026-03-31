"""CLI configuration utilities for shared config loading."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from tdoc_crawler.config import ThreeGPPConfig

console = Console()


def load_cli_config(
    ctx: typer.Context,
    config_file: Path | None = None,
) -> ThreeGPPConfig:
    """Load and validate ThreeGPPConfig for CLI use.

    Loads config from (in precedence order):
    1. Explicit --config file (if provided)
    2. Discovered config files (mise-style hierarchy)
    3. Environment variables (via pydantic-settings)
    4. Hard-coded defaults

    Validates config at load time. On validation error, prints
    formatted error message and exits with code 1.

    Args:
        ctx: Typer context object for storing config
        config_file: Optional explicit config file path from --config

    Returns:
        Validated ThreeGPPConfig instance

    Raises:
        typer.Exit: If config validation fails
    """
    try:
        config = ThreeGPPConfig.from_settings(
            config_file=config_file,
            cwd=Path.cwd(),
        )

        ctx.obj = config

        return config

    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(code=1) from e
