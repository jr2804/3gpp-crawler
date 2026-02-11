"""Credential helpers for ETSI Online (EOL) access."""

from __future__ import annotations

import os
import sys

import typer

from tdoc_crawler.models.base import PortalCredentials


def set_credentials(username: str | None, password: str | None, prompt: bool | None) -> None:
    """Set credential environment variables from CLI inputs.

    Args:
        username: EOL username (optional)
        password: EOL password (optional)
        prompt: Whether to prompt for credentials when missing (optional)
    """
    if username is not None:
        os.environ["TDC_EOL_USERNAME"] = username
    if password is not None:
        os.environ["TDC_EOL_PASSWORD"] = password
    if prompt is not None:
        os.environ["TDC_EOL_PROMPT"] = "true" if prompt else "false"


def resolve_credentials(
    username: str | None,
    password: str | None,
    prompt: bool | None = None,
) -> PortalCredentials | None:
    """Resolve portal credentials from parameters, environment, or prompt.

    Resolution order:
    1. CLI parameters (username, password)
    2. Environment variables (TDC_EOL_USERNAME, TDC_EOL_PASSWORD)
    3. Interactive prompt (if TDC_EOL_PROMPT=true or prompt=True, and stdin is a TTY)

    Args:
        username: CLI-provided username
        password: CLI-provided password
        prompt: Whether to prompt interactively. If None, reads from EOL_PROMPT env var.

    Returns:
        PortalCredentials instance if resolved, None otherwise
    """
    resolved_username = username or os.getenv("TDC_EOL_USERNAME")
    resolved_password = password or os.getenv("TDC_EOL_PASSWORD")

    if resolved_username and resolved_password:
        return PortalCredentials(username=resolved_username, password=resolved_password)

    should_prompt = prompt if prompt is not None else os.getenv("TDC_EOL_PROMPT", "").lower() in ("true", "1", "yes")
    if should_prompt and not sys.stdin.isatty():
        should_prompt = False

    if should_prompt:
        if not resolved_username:
            resolved_username = typer.prompt("EOL username")
        if not resolved_password:
            resolved_password = typer.prompt("EOL password", hide_input=True)
        if resolved_username and resolved_password:
            return PortalCredentials(username=resolved_username, password=resolved_password)

    return None


__all__ = ["resolve_credentials", "set_credentials"]
