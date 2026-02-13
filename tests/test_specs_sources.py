"""Tests for spec source fetchers."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from tdoc_crawler.specs.sources.threegpp import SpecNotFoundError, fetch_threegpp_metadata
from tdoc_crawler.specs.sources.whatthespec import fetch_whatthespec_metadata


class _FakeResponse:
    def __init__(self, url: str, payload: dict[str, Any]) -> None:
        self.url = url
        self._payload = payload
        self.status_code = 200
        # Add request object so response.request.url works
        self.request = MagicMock()
        self.request.url = url

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def test_fetch_threegpp_metadata_uses_redirect(monkeypatch: object) -> None:
    payload = {"title": "Spec title", "versions": ["19.0.0"]}
    response = _FakeResponse("https://portal.3gpp.org/desktopmodules/Specifications/SpecificationDetails.aspx?specificationId=12345", payload)

    class _FakeSession:
        def get(self, *_args: object, **_kwargs: object) -> _FakeResponse:
            return response

    def _fake_create_cached_session(*_args: object, **_kwargs: object) -> _FakeSession:
        return _FakeSession()

    monkeypatch.setattr("tdoc_crawler.specs.sources.threegpp.create_cached_session", _fake_create_cached_session)

    result = fetch_threegpp_metadata("26.132")
    assert result["spec_number"] == "26.132"
    assert result["source_name"] == "3gpp"
    assert result["source_identifier"] == 12345


def test_fetch_threegpp_metadata_raises_when_spec_not_found(monkeypatch: object) -> None:
    """Test that SpecNotFoundError is raised when spec doesn't exist (no specificationId in redirect)."""
    payload = {"title": "Unknown Specification"}
    # Simulate redirect to unknown spec page without specificationId parameter
    response = _FakeResponse("https://portal.3gpp.org/desktopmodules/Specifications/SpecificationDetails.aspx", payload)

    class _FakeSession:
        def get(self, *_args: object, **_kwargs: object) -> _FakeResponse:
            return response

    def _fake_create_cached_session(*_args: object, **_kwargs: object) -> _FakeSession:
        return _FakeSession()

    monkeypatch.setattr("tdoc_crawler.specs.sources.threegpp.create_cached_session", _fake_create_cached_session)

    with pytest.raises(SpecNotFoundError, match="not found on 3GPP portal"):
        fetch_threegpp_metadata("99.999")


def test_fetch_threegpp_metadata_raises_when_redirect_to_unknown_page(monkeypatch: object) -> None:
    """Test that SpecNotFoundError is raised when redirected to an unknown/invalid page."""
    payload = {}
    # Simulate redirect to a generic page without specificationId
    response = _FakeResponse("https://www.3gpp.org/specifications/unknown", payload)

    class _FakeSession:
        def get(self, *_args: object, **_kwargs: object) -> _FakeResponse:
            return response

    def _fake_create_cached_session(*_args: object, **_kwargs: object) -> _FakeSession:
        return _FakeSession()

    monkeypatch.setattr("tdoc_crawler.specs.sources.threegpp.create_cached_session", _fake_create_cached_session)

    with pytest.raises(SpecNotFoundError, match="not found on 3GPP portal"):
        fetch_threegpp_metadata("26.999")


def test_fetch_whatthespec_metadata_parses_json(monkeypatch: object) -> None:
    payload = {"title": "Spec title", "versions": ["19.0.0"]}
    response = _FakeResponse("https://whatthespec.net/api/specs/26132", payload)

    class _FakeSession:
        def get(self, *_args: object, **_kwargs: object) -> _FakeResponse:
            return response

    def _fake_create_cached_session(*_args: object, **_kwargs: object) -> _FakeSession:
        return _FakeSession()

    monkeypatch.setattr("tdoc_crawler.specs.sources.whatthespec.create_cached_session", _fake_create_cached_session)

    result = fetch_whatthespec_metadata("26.132")
    assert result["spec_number"] == "26.132"
    assert result["source_name"] == "whatthespec"
