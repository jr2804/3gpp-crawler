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
from dataclasses import dataclass
from typing import Literal

import pandas as pd
import yaml
from ison_parser import dumps as ison_dumps
from ison_parser import from_dict as ison_from_dict
from rich.console import Console
from rich.table import Table
from toon_format import encode as toon_encode

from tdoc_crawler.logging import get_console
from tdoc_crawler.models.base import OutputFormat
from tdoc_crawler.utils.json_types import JSONValue

# Type alias for structured data input
type StructuredData = JSONValue


@dataclass(frozen=True)
class TableColumnSpec:
    """Describes one table column for DataFrame-backed rendering."""

    key: str
    header: str
    style: str = "white"
    justify: Literal["default", "left", "center", "right", "full"] = "left"


# Columns for tag listings shared by `tag list` and `database export-tags`
TAG_COLUMNS = [
    TableColumnSpec(key="kind", header="Kind", style="cyan"),
    TableColumnSpec(key="item_id", header="Item", style="white"),
    TableColumnSpec(key="tag", header="Tag", style="green"),
]


def print_structured_output(
    data: StructuredData,
    output_format: OutputFormat,
    *,
    table_title: str = "Results",
    table_columns: list[TableColumnSpec] | None = None,
    console: Console | None = None,
) -> None:
    """Print structured output through a DataFrame-first common pipeline."""
    output_console = console or get_console()
    df, _ = _normalize_to_dataframe(data)

    if output_format is OutputFormat.TABLE:
        table = _build_table(df, title=table_title, table_columns=table_columns)
        output_console.print(table)
        return

    output_console.print(format_output(df, output_format))


def _build_table(
    df: pd.DataFrame,
    *,
    title: str,
    table_columns: list[TableColumnSpec] | None,
) -> Table:
    """Build a Rich table from a DataFrame and optional column specs."""
    table = Table(title=title)

    if table_columns:
        for column in table_columns:
            table.add_column(column.header, style=column.style, justify=column.justify)

        for _, row in df.iterrows():
            table.add_row(*[_format_cell(row.get(column.key)) for column in table_columns])

        return table

    for column_name in df.columns:
        table.add_column(str(column_name), style="white")

    for _, row in df.iterrows():
        table.add_row(*[_format_cell(row[column_name]) for column_name in df.columns])

    return table


def _format_cell(value: str | float | bool | None) -> str:
    """Format one table cell from DataFrame value with empty handling."""
    if value is None:
        return "-"

    if isinstance(value, float) and pd.isna(value):
        return "-"

    return str(value)


def format_output(data: StructuredData, output_format: OutputFormat) -> str:
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
    df, input_kind = _normalize_to_dataframe(data)
    payload = _dataframe_to_payload(df, input_kind)

    match output_format:
        case OutputFormat.JSON:
            result = json.dumps(payload, indent=2, default=str)
            return result or "{}"
        case OutputFormat.ISON:
            records = payload if isinstance(payload, list) else [payload]
            return ison_dumps(ison_from_dict({"items": records}))
        case OutputFormat.TOON:
            return toon_encode(payload)
        case OutputFormat.YAML:
            return yaml.dump(payload, sort_keys=False, default_flow_style=False)
        case OutputFormat.TABLE:
            return df.to_string(index=False)
        case _:
            msg = f"Unsupported output format: {output_format}. Use one of: {', '.join(f.value for f in OutputFormat)}"
            raise ValueError(msg)


def _normalize_to_dataframe(data: StructuredData) -> tuple[pd.DataFrame, str]:
    """Normalize arbitrary structured data to a DataFrame.

    Returns:
        Tuple of (dataframe, input_kind) where input_kind is one of:
        "records", "dict", "scalar", "dataframe".
    """
    if isinstance(data, pd.DataFrame):
        return data.copy(), "dataframe"

    if isinstance(data, list):
        return pd.DataFrame(data), "records"

    if isinstance(data, dict):
        return pd.DataFrame([data]), "dict"

    return pd.DataFrame([{"value": data}]), "scalar"


def _dataframe_to_payload(df: pd.DataFrame, input_kind: str) -> JSONValue:
    """Convert normalized DataFrame to a payload shape for serializers."""
    records = df.to_dict(orient="records")

    if input_kind == "dict":
        return records[0] if records else {}

    if input_kind == "scalar":
        if not records:
            return None
        return records[0].get("value")

    return records


__all__ = ["TAG_COLUMNS", "TableColumnSpec", "format_output", "print_structured_output"]
