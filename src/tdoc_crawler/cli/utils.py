"""CLI utilities."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import typer

from tdoc_crawler.logging import get_console, get_logger

console = get_console()
logger = get_logger(__name__)


def launch_file(path: Path) -> None:
    """Launch file in system's default application."""
    if not path.exists():
        logger.error(f"File not found: {path}")
        raise typer.Exit(code=1)
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa: S606
        elif sys.platform == "darwin":
            open_cmd = Path("/usr/bin/open")
            if open_cmd.exists():
                subprocess.run([str(open_cmd), str(path)], check=False)  # noqa: S603
            else:
                logger.warning("/usr/bin/open not available")
        else:
            # Linux and other Unix-like systems
            xdg_cmd = Path("/usr/bin/xdg-open")
            if xdg_cmd.exists():
                subprocess.run([str(xdg_cmd), str(path)], check=False)  # noqa: S603
            else:
                logger.warning("xdg-open command not available")
    except OSError as exc:
        logger.error(f"Failed to open file: {exc}")
        raise typer.Exit(code=1) from exc
