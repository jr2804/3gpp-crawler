"""Template validation tests for 3GPP Crawler."""

from __future__ import annotations

import tomllib
from pathlib import Path


def test_pyproject_toml_structure() -> None:
    """Test that generated pyproject.toml has correct structure."""
    pyproject_file = Path("pyproject.toml")
    if not pyproject_file.exists():
        msg = "pyproject.toml should exist"
        raise AssertionError(msg)

    with open(pyproject_file, "rb") as f:
        content = tomllib.load(f)

    # Verify required sections
    if "project" not in content:
        msg = "Missing [project] section"
        raise AssertionError(msg)
    if "build-system" not in content:
        msg = "Missing [build-system] section"
        raise AssertionError(msg)
    if "tool" not in content:
        msg = "Missing [tool] section"
        raise AssertionError(msg)

    # Verify project metadata
    if "name" not in content["project"]:
        msg = "Missing project name"
        raise AssertionError(msg)
    if "dynamic" not in content["project"]:
        msg = "Missing 'dynamic' in [project] section (version should be dynamic)"
        raise AssertionError(msg)
    if "version" not in content["project"]["dynamic"]:
        msg = "Missing 'version' in dynamic list"
        raise AssertionError(msg)
    if "description" not in content["project"]:
        msg = "Missing project description"
        raise AssertionError(msg)
    if "requires-python" not in content["project"]:
        msg = "Missing requires-python"
        raise AssertionError(msg)

    # Verify project name matches project slug (kebab-case)
    project_name = content["project"]["name"]
    expected_name = "3gpp-crawler"
    if project_name != expected_name:
        msg = f"Project name should be '{expected_name}', got: {project_name}"
        raise AssertionError(msg)


def test_pytest_configuration() -> None:
    """Test that pytest is configured with coverage."""
    pyproject_file = Path("pyproject.toml")

    with open(pyproject_file, "rb") as f:
        content = tomllib.load(f)

    # Verify pytest-cov configuration
    tool_section = content.get("tool", {})
    if "pytest-cov" not in tool_section:
        msg = "Missing [tool.pytest-cov] section"
        raise AssertionError(msg)
    pytest_cov = tool_section["pytest-cov"]
    if "fail_under" not in pytest_cov:
        msg = "Missing fail_under"
        raise AssertionError(msg)
    if pytest_cov["fail_under"] != 70:
        msg = "Coverage should be at least 70%"
        raise AssertionError(msg)
    # Verify coverage source matches package slug (snake_case)
    if "addopts" in pytest_cov:
        addopts = pytest_cov["addopts"]
        expected_slug = "tdoc_crawler"
        if expected_slug not in addopts:
            msg = f"Coverage should be configured for '{expected_slug}', got: {addopts}"
            raise AssertionError(msg)
