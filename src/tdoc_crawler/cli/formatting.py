"""Structured output formatting for CLI commands.

This module provides unified formatting of structured data (dicts, lists of dicts)
to various output formats: JSON, ISON, TOON, YAML.

Usage:
    from tdoc_crawler.cli.formatting import format_output
    from tdoc_crawler.models.base import OutputFormat

    result = format_output(data, OutputFormat.JSON)  # returns JSON string
    result = format_output(data, OutputFormat.TOON)  # returns TOON string
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import yaml
from ison_parser import dumps as ison_dumps
from ison_parser import from_dict as ison_from_dict
from toon_format import encode as toon_encode

from tdoc_crawler.models.base import OutputFormat


def format_output(data: Any, output_format: OutputFormat) -> str:
    """Format structured data to the specified output format.

    Uses pandas DataFrame as intermediate representation for consistent handling
    of tabular data (lists of dicts) before formatting.

    Args:
        data: The data to format (dict, list of dicts, or nested structures)
        output_format: The OutputFormat enum value

    Returns:
        Formatted string in the specified format

    Raises:
        ValueError: If the output format is not supported
    """
    # Convert to DataFrame for consistent tabular handling
    if isinstance(data, list):
        df = pd.DataFrame(data)
    elif isinstance(data, dict):
        df = data if any(isinstance(v, (list, dict)) for v in data.values()) else pd.DataFrame([data])
    else:
        df = data

    match output_format:
        case OutputFormat.JSON:
            result = df.to_json(indent=2, orient="records") if isinstance(df, pd.DataFrame) else json.dumps(df, indent=2, default=str)
            return result or "{}"
        case OutputFormat.ISON:
            records = df.to_dict(orient="records") if isinstance(df, pd.DataFrame) else df
            return ison_dumps(ison_from_dict({"items": records}))
        case OutputFormat.TOON:
            return toon_encode(df.to_dict(orient="records") if isinstance(df, pd.DataFrame) else df)
        case OutputFormat.YAML:
            return yaml.dump(df.to_dict(orient="records") if isinstance(df, pd.DataFrame) else df, sort_keys=False, default_flow_style=False)
        case _:
            raise ValueError(f"Unsupported output format: {output_format}. Use one of: {', '.join(f.value for f in OutputFormat)}")


__all__ = ["format_output"]
