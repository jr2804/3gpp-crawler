"""Tests for LibreOffice executable discovery."""

from __future__ import annotations

from pathlib import Path

import pytest
from convert_lo.exceptions import SofficeNotFoundError
from convert_lo.locator import find_soffice


def test_find_soffice_uses_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Return the env path when configured and present."""
    expected = Path("C:/custom/soffice.exe")
    monkeypatch.setenv("LIBREOFFICE_PATH", str(expected))
    monkeypatch.setattr(Path, "exists", lambda self: self == expected)

    assert find_soffice() == expected


@pytest.mark.parametrize(
    ("platform", "candidate"),
    [
        ("win32", Path("C:/Program Files/LibreOffice/program/soffice.exe")),
        ("darwin", Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")),
        ("linux", Path("/usr/bin/soffice")),
    ],
)
def test_find_soffice_platform_candidates(
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    candidate: Path,
) -> None:
    """Use platform-specific candidate paths when available."""
    monkeypatch.delenv("LIBREOFFICE_PATH", raising=False)
    monkeypatch.setattr("convert_lo.locator.sys.platform", platform)
    monkeypatch.setattr(Path, "exists", lambda self: self == candidate)
    monkeypatch.setattr("convert_lo.locator.shutil.which", lambda _: None)

    assert find_soffice() == candidate


def test_find_soffice_uses_shutil_which(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fallback to shutil.which when candidates are missing."""
    expected = Path("/usr/local/bin/soffice")
    monkeypatch.delenv("LIBREOFFICE_PATH", raising=False)
    monkeypatch.setattr("convert_lo.locator.sys.platform", "linux")
    monkeypatch.setattr(Path, "exists", lambda self: False)
    monkeypatch.setattr("convert_lo.locator.shutil.which", lambda _: str(expected))

    assert find_soffice() == expected


def test_find_soffice_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Raise SofficeNotFoundError when no path resolves."""
    monkeypatch.delenv("LIBREOFFICE_PATH", raising=False)
    monkeypatch.setattr("convert_lo.locator.sys.platform", "linux")
    monkeypatch.setattr(Path, "exists", lambda self: False)
    monkeypatch.setattr("convert_lo.locator.shutil.which", lambda _: None)

    with pytest.raises(SofficeNotFoundError):
        find_soffice()
