"""Tests for OTHER source checkout functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tdoc_crawler.extraction.checkout import (
    _checkout_other,
    _guess_extension,
    _is_url,
    _sniff_content_type,
    checkout_single_item,
)
from tdoc_crawler.models.workspaces import SourceKind


class TestIsUrl:
    """Tests for _is_url helper."""

    def test_http_url(self) -> None:
        assert _is_url("http://example.com/file.pdf") is True

    def test_https_url(self) -> None:
        assert _is_url("https://example.com/file.pdf") is True

    def test_ftp_url_not_recognized(self) -> None:
        # No scheme or non-http(s) scheme returns False
        assert _is_url("ftp://ftp.example.com/file.zip") is False

    def test_local_path(self) -> None:
        assert _is_url("/home/user/docs/report.pdf") is False
        assert _is_url("C:\\Users\\test\\file.pdf") is False

    def test_file_uri(self) -> None:
        assert _is_url("file:///home/user/docs/report.pdf") is False

    def test_no_scheme(self) -> None:
        assert _is_url("example.com/file.pdf") is False

    def test_empty_string(self) -> None:
        assert _is_url("") is False


class TestGuessExtension:
    """Tests for _guess_extension helper."""

    @pytest.mark.parametrize(
        ("content_type", "expected"),
        [
            ("text/html", ".html"),
            ("text/plain", ".txt"),
            ("text/markdown", ".md"),
            ("application/pdf", ".pdf"),
            ("application/msword", ".doc"),
            ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
            ("application/vnd.ms-powerpoint", ".ppt"),
            ("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
            ("application/vnd.ms-excel", ".xls"),
            ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
        ],
    )
    def test_known_types(self, content_type: str, expected: str) -> None:
        assert _guess_extension(content_type) == expected

    def test_unknown_type_returns_empty_string(self) -> None:
        assert _guess_extension("application/octet-stream") == ""
        assert _guess_extension("image/png") == ""

    def test_case_insensitive(self) -> None:
        assert _guess_extension("Text/HTML") == ".html"
        assert _guess_extension("APPLICATION/PDF") == ".pdf"


class TestSniffContentType:
    """Tests for _sniff_content_type async function."""

    @pytest.mark.asyncio
    async def test_returns_content_type(self) -> None:
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}

        mock_session = MagicMock()
        mock_session.head = MagicMock(return_value=mock_response)
        mock_response.raise_for_status = MagicMock()

        with patch("tdoc_crawler.extraction.checkout.create_cached_session") as mock_factory:
            mock_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_factory.return_value.__exit__ = MagicMock(return_value=None)

            result = await _sniff_content_type("https://example.com/page.html")

        assert result == "text/html"

    @pytest.mark.asyncio
    async def test_strips_charset(self) -> None:
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "application/pdf; charset=binary"}

        mock_session = MagicMock()
        mock_session.head = MagicMock(return_value=mock_response)
        mock_response.raise_for_status = MagicMock()

        with patch("tdoc_crawler.extraction.checkout.create_cached_session") as mock_factory:
            mock_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_factory.return_value.__exit__ = MagicMock(return_value=None)

            result = await _sniff_content_type("https://example.com/doc.pdf")

        assert result == "application/pdf"

    @pytest.mark.asyncio
    async def test_fallback_on_error(self) -> None:
        with patch("tdoc_crawler.extraction.checkout.create_cached_session") as mock_factory:
            mock_session = MagicMock()
            mock_session.head.side_effect = Exception("Network error")
            mock_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_factory.return_value.__exit__ = MagicMock(return_value=None)

            result = await _sniff_content_type("https://example.com/page.html")

        assert result == "application/octet-stream"


class TestCheckoutOtherLocal:
    """Tests for _checkout_other with local file paths."""

    @pytest.mark.asyncio
    async def test_local_file_copied(self, tmp_path: Path) -> None:
        # Create a source file
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        source_file = source_dir / "report.html"
        source_file.write_text("<html><body>Test</body></html>", encoding="utf-8")

        # Checkout directory
        checkout_dir = tmp_path / "checkout"
        checkout_dir.mkdir()

        result = await _checkout_other(str(source_file), checkout_dir)

        assert result is not None
        assert result.exists()
        assert result.name == "report.html"
        assert result.read_text(encoding="utf-8") == "<html><body>Test</body></html>"

    @pytest.mark.asyncio
    async def test_local_file_with_custom_prefix(self, tmp_path: Path) -> None:
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        source_file = source_dir / "data.csv"
        source_file.write_text("col1,col2\n1,2", encoding="utf-8")

        checkout_dir = tmp_path / "checkout"

        result = await _checkout_other(str(source_file), checkout_dir, checkout_prefix="CUSTOM_")

        assert result is not None
        # The safe stem should start with CUSTOM_
        assert result.parent.name.startswith("CUSTOM_")

    @pytest.mark.asyncio
    async def test_local_file_not_found_returns_none(self, tmp_path: Path) -> None:
        checkout_dir = tmp_path / "checkout"
        checkout_dir.mkdir()

        result = await _checkout_other("/nonexistent/path/file.pdf", checkout_dir)

        assert result is None


class TestCheckoutOtherUrl:
    """Tests for _checkout_other with URLs."""

    @pytest.mark.asyncio
    async def test_url_downloaded(self, tmp_path: Path) -> None:
        mock_response = MagicMock()
        mock_response.content = b"<html>Test content</html>"
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        mock_head_response = MagicMock()
        mock_head_response.headers = {"content-type": "text/html"}
        mock_head_response.raise_for_status = MagicMock()
        mock_session.head = MagicMock(return_value=mock_head_response)

        with patch("tdoc_crawler.extraction.checkout.create_cached_session") as mock_factory:
            mock_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_factory.return_value.__exit__ = MagicMock(return_value=None)

            checkout_dir = tmp_path / "checkout"
            result = await _checkout_other("https://example.com/page.html", checkout_dir)

        assert result is not None
        assert result.exists()
        assert result.suffix == ".html"
        assert result.read_bytes() == b"<html>Test content</html>"

    @pytest.mark.asyncio
    async def test_url_with_no_extension_gets_bin(self, tmp_path: Path) -> None:
        mock_response = MagicMock()
        mock_response.content = b"binary data"
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        mock_head_response = MagicMock()
        mock_head_response.headers = {"content-type": "application/octet-stream"}
        mock_head_response.raise_for_status = MagicMock()
        mock_session.head = MagicMock(return_value=mock_head_response)

        with patch("tdoc_crawler.extraction.checkout.create_cached_session") as mock_factory:
            mock_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_factory.return_value.__exit__ = MagicMock(return_value=None)

            checkout_dir = tmp_path / "checkout"
            result = await _checkout_other("https://example.com/resource", checkout_dir)

        assert result is not None
        assert result.suffix == ".bin"


class TestCheckoutSingleItem:
    """Tests for checkout_single_item with OTHER source kind."""

    @pytest.mark.asyncio
    async def test_checkout_other_local_file(self, tmp_path: Path) -> None:
        # Create a local file
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        source_file = source_dir / "notes.md"
        source_file.write_text("# Notes\nSome content", encoding="utf-8")

        # Mock path config
        mock_path_config = MagicMock()
        mock_path_config.checkout_dir = tmp_path / "checkout"

        member, skip_reason = await checkout_single_item(
            item=str(source_file),
            workspace="test-workspace",
            source_kind=SourceKind.OTHER,
            checkout=True,
            release=None,
            path_config=mock_path_config,
        )

        assert member is not None
        assert skip_reason is None
        assert member.source_kind == SourceKind.OTHER
        assert member.content_type == ""  # Local file, no content type
        assert member.original_url == ""  # Local file

    @pytest.mark.asyncio
    async def test_checkout_other_url(self, tmp_path: Path) -> None:
        mock_response = MagicMock()
        mock_response.content = b"<html>Test</html>"
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        mock_head_response = MagicMock()
        mock_head_response.headers = {"content-type": "text/html"}
        mock_head_response.raise_for_status = MagicMock()
        mock_session.head = MagicMock(return_value=mock_head_response)

        with patch("tdoc_crawler.extraction.checkout.create_cached_session") as mock_factory:
            mock_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_factory.return_value.__exit__ = MagicMock(return_value=None)

            mock_path_config = MagicMock()
            mock_path_config.checkout_dir = tmp_path / "checkout"

            member, skip_reason = await checkout_single_item(
                item="https://example.com/page.html",
                workspace="test-workspace",
                source_kind=SourceKind.OTHER,
                checkout=True,
                release=None,
                path_config=mock_path_config,
            )

        assert member is not None
        assert skip_reason is None
        assert member.source_kind == SourceKind.OTHER
        assert member.content_type == "text/html"
        assert member.original_url == "https://example.com/page.html"

    @pytest.mark.asyncio
    async def test_checkout_other_url_fetch_failure(self, tmp_path: Path) -> None:
        # Both head (for content-type sniff) AND get must fail for checkout to return None
        with patch("tdoc_crawler.extraction.checkout.create_cached_session") as mock_factory:
            mock_session = MagicMock()
            mock_session.head.side_effect = Exception("Network failure")
            mock_session.get.side_effect = Exception("Download failure")
            mock_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_factory.return_value.__exit__ = MagicMock(return_value=None)

            mock_path_config = MagicMock()
            mock_path_config.checkout_dir = tmp_path / "checkout"

            member, skip_reason = await checkout_single_item(
                item="https://example.com/page.html",
                workspace="test-workspace",
                source_kind=SourceKind.OTHER,
                checkout=True,
                release=None,
                path_config=mock_path_config,
            )

        assert member is None
        assert skip_reason == "OTHER source checkout failed"
