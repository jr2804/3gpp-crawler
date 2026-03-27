"""Tests for CLI structured output formatting."""

from __future__ import annotations

from rich.console import Console

from tdoc_crawler.cli.formatting import TableColumnSpec, format_output, print_structured_output
from tdoc_crawler.models.base import OutputFormat


def test_format_output_json_from_records() -> None:
    """JSON output should serialize list-of-dict inputs as records."""
    output = format_output([{"name": "alpha", "count": 2}], OutputFormat.JSON)

    assert '"name": "alpha"' in output
    assert output.strip().startswith("[")


def test_format_output_json_from_dict() -> None:
    """JSON output should keep dict payload shape after DataFrame normalization."""
    output = format_output({"name": "alpha", "count": 2}, OutputFormat.JSON)

    assert '"name": "alpha"' in output
    assert output.strip().startswith("{")


def test_format_output_yaml_from_records() -> None:
    """YAML output should serialize records with stable keys."""
    output = format_output([{"name": "alpha", "count": 2}], OutputFormat.YAML)

    assert "name: alpha" in output
    assert "count: 2" in output


def test_format_output_ison_contains_items_wrapper() -> None:
    """ISON output should include the shared items envelope."""
    output = format_output([{"name": "alpha"}], OutputFormat.ISON)

    assert "items" in output
    assert "alpha" in output


def test_format_output_table_text() -> None:
    """Table output should return DataFrame string representation."""
    output = format_output([{"name": "alpha", "count": 2}], OutputFormat.TABLE)

    assert "name" in output
    assert "count" in output


def test_print_structured_output_table_with_column_specs() -> None:
    """Table printer should render specified columns via the shared pipeline."""
    output_console = Console(record=True, width=120)

    print_structured_output(
        [{"name": "alpha", "count": 2}],
        OutputFormat.TABLE,
        table_title="Example",
        table_columns=[
            TableColumnSpec("name", "Name", style="cyan"),
            TableColumnSpec("count", "Count", style="yellow", justify="right"),
        ],
        console=output_console,
    )

    rendered = output_console.export_text()
    assert "Example" in rendered
    assert "Name" in rendered
    assert "Count" in rendered
    assert "alpha" in rendered
