"""Test fixtures for convert-lo."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(name="example_doc_path")
def fixture_example_doc_path() -> Path:
    """Return the legacy .doc example fixture path."""
    return Path(__file__).parent / "examples" / "example_legacy.doc"


@pytest.fixture(name="example_small_docx_path")
def fixture_example_small_docx_path() -> Path:
    """Return the small .docx example fixture path for faster tests."""
    return Path(__file__).parent / "examples" / "example_medium_size.docx"


@pytest.fixture(name="example_medium_docx_path")
def fixture_example_medium_docx_path() -> Path:
    """Return the medium .docx example fixture path."""
    return Path(__file__).parent / "examples" / "example_modern.docx"


@pytest.fixture(name="output_dir")
def fixture_output_dir(tmp_path: Path) -> Path:
    """Return a temporary output directory for conversions."""
    output_path = tmp_path / "outputs"
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path
