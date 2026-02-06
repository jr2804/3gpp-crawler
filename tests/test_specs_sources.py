"""Tests for spec source fetchers."""

from typing import Any

import pytest

from tdoc_crawler.specs.sources.threegpp import SpecNotFoundError, fetch_threegpp_metadata
from tdoc_crawler.specs.sources.whatthespec import fetch_whatthespec_metadata


class _FakeResponse:
    def __init__(self, url: str, payload: dict[str, Any]) -> None:
        self.url = url
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def test_fetch_threegpp_metadata_uses_redirect(monkeypatch) -> None:
    payload = {"title": "Spec title", "versions": ["19.0.0"]}
    response = _FakeResponse("https://portal.3gpp.org/desktopmodules/Specifications/SpecificationDetails.aspx?specificationId=12345", payload)

    def _fake_get(*_args: object, **_kwargs: object) -> _FakeResponse:
        return response

    monkeypatch.setattr("requests.get", _fake_get)

    result = fetch_threegpp_metadata("26.132")
    assert result["spec_number"] == "26.132"
    assert result["source_name"] == "3gpp"
    assert result["source_identifier"] == "12345"


def test_fetch_threegpp_metadata_raises_when_spec_not_found(monkeypatch) -> None:
    """Test that SpecNotFoundError is raised when spec doesn't exist (no specificationId in redirect)."""
    payload = {"title": "Unknown Specification"}
    # Simulate redirect to unknown spec page without specificationId parameter
    response = _FakeResponse("https://portal.3gpp.org/desktopmodules/Specifications/SpecificationDetails.aspx", payload)

    def _fake_get(*_args: object, **_kwargs: object) -> _FakeResponse:
        return response

    monkeypatch.setattr("requests.get", _fake_get)

    with pytest.raises(SpecNotFoundError, match="not found on 3GPP portal"):
        fetch_threegpp_metadata("99.999")


def test_fetch_threegpp_metadata_raises_when_redirect_to_unknown_page(monkeypatch) -> None:
    """Test that SpecNotFoundError is raised when redirected to an unknown/invalid page."""
    payload = {}
    # Simulate redirect to a generic page without specificationId
    response = _FakeResponse("https://www.3gpp.org/specifications/unknown", payload)

    def _fake_get(*_args: object, **_kwargs: object) -> _FakeResponse:
        return response

    monkeypatch.setattr("requests.get", _fake_get)

    with pytest.raises(SpecNotFoundError, match="not found on 3GPP portal"):
        fetch_threegpp_metadata("26.999")


def test_fetch_whatthespec_metadata_parses_json(monkeypatch) -> None:
    payload = {"title": "Spec title", "versions": ["19.0.0"]}
    response = _FakeResponse("https://whatthespec.net/api/specs/26132", payload)

    def _fake_get(*_args: object, **_kwargs: object) -> _FakeResponse:
        return response

    monkeypatch.setattr("requests.get", _fake_get)

    result = fetch_whatthespec_metadata("26.132")
    assert result["spec_number"] == "26.132"
    assert result["source_name"] == "whatthespec"
