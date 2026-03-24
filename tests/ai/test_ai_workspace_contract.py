"""Legacy contract tests for removed pipeline behaviors."""

import pytest


@pytest.mark.skip(reason="Legacy pipeline removed; contract no longer applies.")
def test_workspace_contract_removed() -> None:
    assert True
