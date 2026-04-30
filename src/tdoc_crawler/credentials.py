"""Credential helpers for ETSI Online (EOL) access."""

from __future__ import annotations

import os
import sys

import typer

from tdoc_crawler.config.settings import CredentialsConfig
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


def _resolve_prompt_decision(prompt: bool | None, credentials_config: CredentialsConfig | None) -> bool:
    """Determine whether to prompt the user for credentials.

    Resolution order: explicit prompt flag > config file > TDC_EOL_PROMPT env var.

    Args:
        prompt: CLI-provided prompt flag (highest precedence).
        credentials_config: Optional credentials config from settings.

    Returns:
        Whether to prompt for credentials interactively.
    """
    config_prompt = credentials_config.prompt if credentials_config else None
    should_prompt = prompt if prompt is not None else (config_prompt.lower() in ("true", "1", "yes") if config_prompt else None)
    if should_prompt is None:
        should_prompt = os.getenv("TDC_EOL_PROMPT", "").lower() in ("true", "1", "yes")
    if should_prompt and not sys.stdin.isatty():
        should_prompt = False
    return should_prompt


def resolve_credentials(
    username: str | None = None,
    password: str | None = None,
    prompt: bool | None = None,
    credentials_config: CredentialsConfig | None = None,
) -> PortalCredentials | None:
    """Resolve portal credentials with TDocCrawlerConfig integration.

    Resolution order (per D-03):
    1. CLI parameters (username, password)
    2. credentials_config values (from config file)
    3. Environment variables (TDC_EOL_USERNAME, TDC_EOL_PASSWORD)
    4. Interactive prompt (if enabled)

    Args:
        username: CLI-provided username (highest precedence)
        password: CLI-provided password (highest precedence)
        prompt: Whether to prompt interactively
        credentials_config: Optional CredentialsConfig from TDocCrawlerConfig

    Returns:
        PortalCredentials instance if resolved, None otherwise
    """
    # Resolution order: CLI > Config > Env > Prompt
    resolved_username = username or (credentials_config.username if credentials_config else None) or os.getenv("TDC_EOL_USERNAME")
    resolved_password = password or (credentials_config.password if credentials_config else None) or os.getenv("TDC_EOL_PASSWORD")

    if resolved_username and resolved_password:
        return PortalCredentials(username=resolved_username, password=resolved_password)

    # Determine if we should prompt
    should_prompt = _resolve_prompt_decision(prompt, credentials_config)

    if should_prompt:
        if not resolved_username:
            resolved_username = typer.prompt("EOL username")
        if not resolved_password:
            resolved_password = typer.prompt("EOL password", hide_input=True)
        if resolved_username and resolved_password:
            return PortalCredentials(username=resolved_username, password=resolved_password)

    return None


__all__ = ["resolve_credentials", "set_credentials"]
