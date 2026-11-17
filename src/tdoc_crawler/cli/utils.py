"""CLI utilities."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import typer

from tdoc_crawler.logging import get_logger

logger = get_logger(__name__)


def launch_file(filename: Path) -> None:
    """Launch file in system's default application."""
    if not filename.exists():
        logger.error("File not found: %s", filename)
        raise typer.Exit(code=1)

    try:
        if sys.platform.startswith("win"):
            os.startfile(filename)  # noqa: S606 -- OS file launcher, not a shell command
        elif sys.platform == "darwin":
            open_cmd_file = Path("/usr/bin/open")
            if open_cmd_file.exists():
                subprocess.run([str(open_cmd_file), str(filename)], check=False)  # noqa: S603 -- fixed binary + one file arg, shell=False
            else:
                logger.warning("/usr/bin/open not available")
        else:
            # Linux and other Unix-like systems
            xdg_cmd_file = Path("/usr/bin/xdg-open")
            if xdg_cmd_file.exists():
                subprocess.run([str(xdg_cmd_file), str(filename)], check=False)  # noqa: S603 -- fixed binary + one file arg, shell=False
            else:
                logger.warning("xdg-open command not available")
    except OSError as exc:
        logger.exception("Failed to open file: %s", exc)
        raise typer.Exit(code=1) from exc
