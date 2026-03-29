#!/usr/bin/env uv run python
"""Generate configuration reference documentation from Pydantic models.

This script introspects TDocCrawlerConfig and its nested models to generate
a Markdown table with all configuration fields.

Usage:
    uv run python scripts/generate_config_docs.py

Output can be redirected to a file:
    uv run python scripts/generate_config_docs.py > docs/config_reference.md
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Union, get_args, get_origin

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tdoc_crawler.config.settings import (
    CrawlConfig,
    CredentialsConfig,
    HttpConfig,
    PathConfig,
)


def get_field_type(field_info: Any) -> str:
    """Extract a human-readable type name from a pydantic field."""
    annotation = field_info.annotation

    # Handle Optional types (Union with None)
    if get_origin(annotation) is Union:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return get_field_type_name(args[0])

    return get_field_type_name(annotation)


def get_field_type_name(annotation: Any) -> str:
    """Get the type name from an annotation."""
    if hasattr(annotation, "__name__"):
        return annotation.__name__

    # Handle special cases
    name = str(annotation)
    if name.startswith("typing."):
        name = name[7:]

    return name


def format_default(default: Any) -> str:
    """Format a default value for display."""
    if default is None or (isinstance(default, type) and default is type(None)):
        return "(none)"
    if isinstance(default, Path):
        return str(default)
    if isinstance(default, bool):
        return "true" if default else "false"
    if isinstance(default, str):
        return f'"{default}"'
    return str(default)


def format_constraints(field_info: Any) -> str:
    """Extract validation constraints from a field."""
    constraints = []

    # Check ge (greater than or equal)
    if hasattr(field_info, "ge"):
        constraints.append(f"ge={field_info.ge}")

    # Check le (less than or equal)
    if hasattr(field_info, "le"):
        constraints.append(f"le={field_info.le}")

    # Check pattern (regex)
    if hasattr(field_info, "pattern"):
        constraints.append(f"pattern={field_info.pattern}")

    return ", ".join(constraints) if constraints else ""


def generate_section_table(
    section_name: str,
    title: str,
    description: str,
    model_class: type,  # noqa: ARG002
    fields: dict[str, Any],
) -> list[str]:
    """Generate a Markdown table for a config section."""
    lines = []
    lines.append(f"### {title}")
    lines.append("")
    lines.append(f"*{description}*")
    lines.append("")
    lines.append("| Field | Type | Default | Description |")
    lines.append("|-------|------|---------|-------------|")

    for field_name, field_info in fields.items():
        field_type = get_field_type(field_info)
        default = format_default(field_info.default)
        desc = field_info.description or ""

        # Add constraints to description if present
        constraints = format_constraints(field_info)
        if constraints:
            desc = f"{desc} [{constraints}]"

        # Truncate long descriptions
        if len(desc) > 70:
            desc = desc[:67] + "..."

        lines.append(f"| `{field_name}` | {field_type} | {default} | {desc} |")

    return lines


def generate_docs() -> str:
    """Generate complete configuration documentation."""
    lines = []

    # Header
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append("# Configuration Reference")
    lines.append("")
    lines.append(f"*Auto-generated from `TDocCrawlerConfig` at {timestamp}.*")
    lines.append("*This reference is auto-generated. Run `uv run python scripts/generate_config_docs.py` to update.*")
    lines.append("")

    # Build sections
    sections = [
        (
            "path",
            "Path Settings",
            "File system paths for cache, database, checkout, and AI storage",
            PathConfig,
            {
                "cache_dir": PathConfig.model_fields["cache_dir"],
                "db_filename": PathConfig.model_fields["db_filename"],
                "checkout_dirname": PathConfig.model_fields["checkout_dirname"],
                "ai_cache_dirname": PathConfig.model_fields["ai_cache_dirname"],
            },
        ),
        (
            "http",
            "HTTP Settings",
            "HTTP client behavior, caching, timeouts, and retries",
            HttpConfig,
            {
                "cache_ttl": HttpConfig.model_fields["cache_ttl"],
                "cache_enabled": HttpConfig.model_fields["cache_enabled"],
                "cache_refresh_on_access": HttpConfig.model_fields["cache_refresh_on_access"],
                "verify_ssl": HttpConfig.model_fields["verify_ssl"],
                "max_retries": HttpConfig.model_fields["max_retries"],
                "timeout": HttpConfig.model_fields["timeout"],
            },
        ),
        (
            "credentials",
            "Credentials Settings",
            "ETSI Online (EOL) portal authentication credentials",
            CredentialsConfig,
            {
                "username": CredentialsConfig.model_fields["username"],
                "password": CredentialsConfig.model_fields["password"],
                "prompt": CredentialsConfig.model_fields["prompt"],
            },
        ),
        (
            "crawl",
            "Crawl Settings",
            "Crawling filters, limits, and worker configuration",
            CrawlConfig,
            {
                "working_group": CrawlConfig.model_fields["working_group"],
                "sub_group": CrawlConfig.model_fields["sub_group"],
                "date_start": CrawlConfig.model_fields["date_start"],
                "date_end": CrawlConfig.model_fields["date_end"],
                "source_like": CrawlConfig.model_fields["source_like"],
                "agenda_like": CrawlConfig.model_fields["agenda_like"],
                "title_like": CrawlConfig.model_fields["title_like"],
                "limit": CrawlConfig.model_fields["limit"],
                "workers": CrawlConfig.model_fields["workers"],
            },
        ),
    ]

    for section_name, title, description, _, fields in sections:
        section_lines = generate_section_table(section_name, title, description, _, fields)
        lines.extend(section_lines)
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Main entry point."""
    print(generate_docs())


if __name__ == "__main__":
    main()
