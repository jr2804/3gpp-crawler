"""Tests for spec source fetchers."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from tdoc_crawler.specs.sources.threegpp import (
    SpecNotFoundError,
    _decode_version_from_filename,
    fetch_threegpp_metadata,
)
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


class _FakePortalResponse:
    """Fake HTTP response with HTML text from the portal spec details page."""

    _PORTAL_URL = "https://portal.3gpp.org/desktopmodules/Specifications/SpecificationDetails.aspx?specificationId=3314"

    def __init__(self, html_body: str, url: str = _PORTAL_URL) -> None:
        self.text = html_body
        self.url = url
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None


# ---------------------------------------------------------------------------
# 3GPP filename-to-version decoder tests (utility)
# ---------------------------------------------------------------------------


def test_decode_version_rel10_plus() -> None:
    assert _decode_version_from_filename("26260", "26260-j10.zip") == "19.1.0"
    assert _decode_version_from_filename("26260", "26260-j00.zip") == "19.0.0"
    assert _decode_version_from_filename("26260", "26260-i10.zip") == "18.1.0"
    assert _decode_version_from_filename("26260", "26260-a00.zip") == "10.0.0"


def test_decode_version_pre_rel10() -> None:
    assert _decode_version_from_filename("26260", "26260-100.zip") == "1.0.0"
    assert _decode_version_from_filename("26260", "26260-001.zip") == "0.0.1"


def test_decode_version_wrong_compact_returns_none() -> None:
    assert _decode_version_from_filename("99999", "26260-j10.zip") is None


def test_decode_version_invalid_vercode_returns_none() -> None:
    assert _decode_version_from_filename("26260", "26260-z00.zip") is None


# ---------------------------------------------------------------------------
# Portal-based 3GPP source tests
# ---------------------------------------------------------------------------

_PORTAL_HTML_26260 = """\
<html><body>
<div id="RadPageGeneral">
    <span id="referenceVal">26.260</span>
    <span id="titleVal">Objective test methodologies for the evaluation of immersive audio systems</span>
    <span id="statusVal">Under change control</span>
    <span id="typeVal">Technical specification (TS)</span>
</div>
<div id="RadPageResponsibility">
    <span id="PrimaryResponsibleGroupLbl">Primary responsible group:</span>
    <span>SA 4</span>
</div>
<div id="RadPageReleases">
    <table>
        <tr><td>
            <a id="SpecificationReleaseControl1_rpbReleases_i0_ctl00_specificationsVersionGrid_ctl00_ctl04_lnkFtpDownload"
               title="Click to download this version"
               href="https://www.3gpp.org/ftp/Specs/archive/26_series/26.260/26260-j10.zip">19.1.0</a>
        </td></tr>
        <tr><td>
            <a id="SpecificationReleaseControl1_rpbReleases_i0_ctl00_specificationsVersionGrid_ctl00_ctl06_lnkFtpDownload"
               title="Click to download this version"
               href="https://www.3gpp.org/ftp/Specs/archive/26_series/26.260/26260-j00.zip">19.0.0</a>
        </td></tr>
        <tr><td>
            <a id="SpecificationReleaseControl1_rpbReleases_i1_ctl00_specificationsVersionGrid_ctl00_ctl04_lnkFtpDownload"
               title="Click to download this version"
               href="https://www.3gpp.org/ftp/Specs/archive/26_series/26.260/26260-i10.zip">18.1.0</a>
        </td></tr>
        <tr><td>
            <a id="SpecificationReleaseControl1_rpbReleases_i1_ctl00_specificationsVersionGrid_ctl00_ctl06_lnkFtpDownload"
               title="Click to download this version"
               href="https://www.3gpp.org/ftp/Specs/archive/26_series/26.260/26260-i00.zip">18.0.0</a>
        </td></tr>
        <tr><td>
            <a id="SpecificationReleaseControl1_rpbReleases_i2_ctl00_specificationsVersionGrid_ctl00_ctl04_lnkFtpDownload"
               title="Click to download this version"
               href="https://www.3gpp.org/ftp/Specs/archive/26_series/26.260/26260-h00.zip">17.0.0</a>
        </td></tr>
    </table>
</div>
</body></html>
"""


def test_fetch_threegpp_metadata_parses_portal_page(monkeypatch: object) -> None:
    """Test that fetch_threegpp_metadata parses portal HTML correctly."""
    response = _FakePortalResponse(_PORTAL_HTML_26260)

    class _FakeSession:
        def get(self, *_args: object, **_kwargs: object) -> _FakePortalResponse:
            return response

    def _fake_create_cached_session(*_args: object, **_kwargs: object) -> _FakeSession:
        return _FakeSession()

    monkeypatch.setattr("tdoc_crawler.specs.sources.threegpp.create_cached_session", _fake_create_cached_session)

    result = fetch_threegpp_metadata("26.260")
    assert result["spec_number"] == "26.260"
    assert result["source_name"] == "3gpp"
    assert "19.1.0" in result["versions"]
    assert "19.0.0" in result["versions"]
    assert "18.1.0" in result["versions"]
    assert "18.0.0" in result["versions"]
    assert "17.0.0" in result["versions"]
    # Sorted descending: latest first
    assert result["versions"][0] == "19.1.0"
    # Metadata extracted from portal
    payload = result["metadata_payload"]
    assert payload["title"] == "Objective test methodologies for the evaluation of immersive audio systems"
    assert payload["spec_type"] == "TS"
    assert payload["status"] == "Under change control"
    assert payload["working_group"] == "SA4"
    assert payload["series"] == "26_series"
    assert payload["latest_version"] == "19.1.0"
    # Filenames matched to versions
    assert isinstance(payload["specfile"], list)
    assert len(payload["specfile"]) == len(result["versions"])
    assert payload["specfile"][0] == "26260-j10.zip"


def test_fetch_threegpp_metadata_parses_tr_type(monkeypatch: object) -> None:
    """Test that Technical Report type is correctly parsed to TR."""
    html = _PORTAL_HTML_26260.replace("Technical specification (TS)", "Technical Report (TR)")
    response = _FakePortalResponse(html)

    class _FakeSession:
        def get(self, *_args: object, **_kwargs: object) -> _FakePortalResponse:
            return response

    def _fake_create_cached_session(*_args: object, **_kwargs: object) -> _FakeSession:
        return _FakeSession()

    monkeypatch.setattr("tdoc_crawler.specs.sources.threegpp.create_cached_session", _fake_create_cached_session)

    result = fetch_threegpp_metadata("26.260")
    assert result["metadata_payload"]["spec_type"] == "TR"


def test_fetch_threegpp_metadata_raises_when_no_versions(monkeypatch: object) -> None:
    """Test that SpecNotFoundError is raised when portal page has no version links."""
    html = """<html><body>
    <div id="RadPageGeneral">
        <span id="titleVal">Some spec</span>
        <span id="statusVal">Under change control</span>
        <span id="typeVal">Technical specification (TS)</span>
    </div>
    </body></html>"""
    response = _FakePortalResponse(html)

    class _FakeSession:
        def get(self, *_args: object, **_kwargs: object) -> _FakePortalResponse:
            return response

    def _fake_create_cached_session(*_args: object, **_kwargs: object) -> _FakeSession:
        return _FakeSession()

    monkeypatch.setattr("tdoc_crawler.specs.sources.threegpp.create_cached_session", _fake_create_cached_session)

    with pytest.raises(SpecNotFoundError, match="not found on 3GPP portal"):
        fetch_threegpp_metadata("99.999")


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
