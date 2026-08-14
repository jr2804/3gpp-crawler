"""Tests for OTHER source conversion functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from tdoc_crawler.extraction.convert import (
    _build_yaml_frontmatter,
    _convert_html_to_markdown,
    _convert_spreadsheet_to_markdown,
    _convert_text_to_markdown,
    _is_spreadsheet_format,
    _is_text_format,
    _resolve_source_files,
    convert_for_wiki,
)
from tdoc_crawler.extraction.errors import ConversionError
from tdoc_crawler.extraction.profiles import ExtractionProfile, SpreadsheetMode
from tdoc_crawler.models.workspaces import SourceKind


class TestIsTextFormat:
    """Tests for _is_text_format helper."""

    @pytest.mark.parametrize(
        ("suffix", "expected"),
        [
            (".txt", True),
            (".md", True),
            (".html", True),
            (".htm", True),
            (".xlsx", False),
            (".pdf", False),
            (".docx", False),
            (".csv", False),
            (".png", False),
        ],
    )
    def test_text_formats(self, suffix: str, expected: bool) -> None:
        path = Path(f"file{suffix}")
        assert _is_text_format(path) is expected

    def test_case_insensitive(self) -> None:
        assert _is_text_format(Path("file.HTML")) is True
        assert _is_text_format(Path("file.MD")) is True


class TestIsSpreadsheetFormat:
    """Tests for _is_spreadsheet_format helper."""

    @pytest.mark.parametrize(
        ("suffix", "expected"),
        [
            (".xls", True),
            (".xlsx", True),
            (".ods", True),
            (".csv", True),
            (".txt", False),
            (".pdf", False),
            (".html", False),
            (".docx", False),
        ],
    )
    def test_spreadsheet_formats(self, suffix: str, expected: bool) -> None:
        path = Path(f"file{suffix}")
        assert _is_spreadsheet_format(path) is expected

    def test_case_insensitive(self) -> None:
        assert _is_spreadsheet_format(Path("file.CSV")) is True
        assert _is_spreadsheet_format(Path("file.XLSX")) is True


class TestConvertHtmlToMarkdown:
    """Tests for _convert_html_to_markdown."""

    def test_simple_html_converted(self, tmp_path: Path) -> None:
        html_file = tmp_path / "page.html"
        html_file.write_text(
            "<html><head><title>Test</title></head><body><h1>Hello</h1><p>World</p></body></html>",
            encoding="utf-8",
        )

        result = _convert_html_to_markdown(html_file)

        assert "# Hello" in result
        assert "World" in result

    def test_html_with_links(self, tmp_path: Path) -> None:
        html_file = tmp_path / "links.html"
        html_file.write_text(
            "<html><body><a href='https://example.com'>Example</a></body></html>",
            encoding="utf-8",
        )

        result = _convert_html_to_markdown(html_file)

        assert "Example" in result

    def test_html_entities_decoded(self, tmp_path: Path) -> None:
        html_file = tmp_path / "entities.html"
        html_file.write_text("<html><body><p>Tom &amp; Jerry</p></body></html>", encoding="utf-8")

        result = _convert_html_to_markdown(html_file)

        assert "Tom & Jerry" in result


class TestConvertTextToMarkdown:
    """Tests for _convert_text_to_markdown."""

    def test_plain_text_wrapped_in_code_block(self, tmp_path: Path) -> None:
        text_file = tmp_path / "notes.txt"
        text_file.write_text("Line one\nLine two", encoding="utf-8")

        result = _convert_text_to_markdown(text_file)

        assert "```text" in result
        assert "Line one" in result
        assert "Line two" in result
        assert "```" in result

    def test_empty_file(self, tmp_path: Path) -> None:
        text_file = tmp_path / "empty.txt"
        text_file.write_text("", encoding="utf-8")

        result = _convert_text_to_markdown(text_file)

        assert "```text\n\n```" in result


class TestConvertSpreadsheetToMarkdown:
    """Tests for _convert_spreadsheet_to_markdown."""

    def test_csv_data_mode(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("col1,col2\n1,2\n3,4", encoding="utf-8")

        result = _convert_spreadsheet_to_markdown(csv_file, mode=SpreadsheetMode.DATA)

        assert "col1" in result
        assert "col2" in result
        assert "1" in result

    def test_xlsx_data_mode(self, tmp_path: Path) -> None:
        openpyxl = pytest.importorskip("openpyxl")
        xlsx_file = tmp_path / "data.xlsx"
        # Create a minimal xlsx via openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws["A1"] = "Name"
        ws["B1"] = "Value"
        ws["A2"] = "Alice"
        ws["B2"] = 100
        wb.save(str(xlsx_file))

        result = _convert_spreadsheet_to_markdown(xlsx_file, mode=SpreadsheetMode.DATA)

        assert "Sheet: Sheet1" in result
        assert "Name" in result
        assert "Alice" in result

    def test_visual_mode_returns_empty_string(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("col1\n1", encoding="utf-8")

        result = _convert_spreadsheet_to_markdown(csv_file, mode=SpreadsheetMode.VISUAL)

        assert result == ""


class TestBuildYamlFrontmatter:
    """Tests for _build_yaml_frontmatter."""

    def test_basic_frontmatter(self) -> None:
        result = _build_yaml_frontmatter(
            document_id="OTHER_test",
            source_kind=SourceKind.OTHER,
            profile=ExtractionProfile.DEFAULT,
        )

        assert "document_id: OTHER_test" in result
        assert "source_kind: other" in result
        assert "profile: default" in result
        assert result.startswith("---\n")

    def test_frontmatter_with_metadata(self) -> None:
        result = _build_yaml_frontmatter(
            document_id="OTHER_test",
            source_kind=SourceKind.OTHER,
            profile=ExtractionProfile.DEFAULT,
            db_metadata={"author": "Test", "version": 1},
        )

        assert "metadata:" in result
        assert "author: Test" in result
        assert "version: 1" in result


class TestResolveSourceFiles:
    """Tests for _resolve_source_files with OTHER source kind."""

    def test_other_source_path_exists(self, tmp_path: Path) -> None:
        source_file = tmp_path / "doc.html"
        source_file.write_text("<html></html>", encoding="utf-8")

        result = _resolve_source_files(
            "OTHER_test",
            source_kind=SourceKind.OTHER,
            source_path=str(source_file),
        )

        assert result == source_file

    def test_other_source_path_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(ConversionError, match="OTHER source OTHER_test not found on disk"):
            _resolve_source_files(
                "OTHER_test",
                source_kind=SourceKind.OTHER,
                source_path=str(tmp_path / "nonexistent.html"),
            )

    def test_other_source_no_path_raises(self) -> None:
        with pytest.raises(ConversionError, match="OTHER source OTHER_test not found on disk"):
            _resolve_source_files(
                "OTHER_test",
                source_kind=SourceKind.OTHER,
                source_path=None,
            )


class TestConvertForWikiOther:
    """Tests for convert_for_wiki with OTHER source kind."""

    def test_other_html_to_markdown(self, tmp_path: Path) -> None:
        source_file = tmp_path / "page.html"
        source_file.write_text("<html><body><h1>Title</h1><p>Content</p></body></html>", encoding="utf-8")

        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()

        result = convert_for_wiki(
            "OTHER_html_test",
            wiki_dir,
            source_kind=SourceKind.OTHER,
            source_path=str(source_file),
            profile=ExtractionProfile.DEFAULT,
            md_yaml_frontmatter=True,
        )

        assert result.suffix == ".md"
        content = result.read_text(encoding="utf-8")
        assert "# Title" in content
        assert "Content" in content
        assert result.name == "page.md"

    def test_other_text_to_markdown(self, tmp_path: Path) -> None:
        source_file = tmp_path / "notes.txt"
        source_file.write_text("Some text content", encoding="utf-8")

        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()

        result = convert_for_wiki(
            "OTHER_text_test",
            wiki_dir,
            source_kind=SourceKind.OTHER,
            source_path=str(source_file),
            profile=ExtractionProfile.DEFAULT,
            md_yaml_frontmatter=False,
        )

        assert result.suffix == ".md"
        content = result.read_text(encoding="utf-8")
        assert "```text" in content
        assert "Some text content" in content

    def test_other_spreadsheet_data_mode(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("Name,Value\nAlice,100\nBob,200", encoding="utf-8")

        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()

        result = convert_for_wiki(
            "OTHER_csv_test",
            wiki_dir,
            source_kind=SourceKind.OTHER,
            source_path=str(csv_file),
            profile=ExtractionProfile.DEFAULT,
            spreadsheet_mode=SpreadsheetMode.DATA,
            md_yaml_frontmatter=False,
        )

        assert result.suffix == ".md"
        content = result.read_text(encoding="utf-8")
        assert "Alice" in content
        assert "100" in content

    def test_other_spreadsheet_visual_mode_pdf_generated(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("col1\n1", encoding="utf-8")

        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()

        # In visual mode, should call ensure_pdf
        result = convert_for_wiki(
            "OTHER_csv_visual",
            wiki_dir,
            source_kind=SourceKind.OTHER,
            source_path=str(csv_file),
            profile=ExtractionProfile.PDF_ONLY,
            spreadsheet_mode=SpreadsheetMode.VISUAL,
        )

        assert result.suffix == ".pdf"

    def test_other_with_yaml_frontmatter(self, tmp_path: Path) -> None:
        source_file = tmp_path / "doc.html"
        source_file.write_text("<html><body><p>Hello</p></body></html>", encoding="utf-8")

        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()

        result = convert_for_wiki(
            "OTHER_yaml_test",
            wiki_dir,
            source_kind=SourceKind.OTHER,
            source_path=str(source_file),
            profile=ExtractionProfile.DEFAULT,
            md_yaml_frontmatter=True,
        )

        content = result.read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert "document_id: OTHER_yaml_test" in content
        assert "source_kind: other" in content

    def test_other_source_not_found_raises(self, tmp_path: Path) -> None:
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()

        with pytest.raises(ConversionError, match="OTHER source OTHER_missing not found on disk"):
            convert_for_wiki(
                "OTHER_missing",
                wiki_dir,
                source_kind=SourceKind.OTHER,
                source_path=str(tmp_path / "nonexistent.html"),
                profile=ExtractionProfile.DEFAULT,
            )

    def test_other_md_already_exists_skipped(self, tmp_path: Path) -> None:
        source_file = tmp_path / "doc.html"
        source_file.write_text("<html><body><p>Hello</p></body></html>", encoding="utf-8")

        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()

        md_file = wiki_dir / "doc.md"
        md_file.write_text("Already exists", encoding="utf-8")

        # With existing file and no force, should return existing file
        with patch("tdoc_crawler.extraction.convert.logger") as mock_logger:
            result = convert_for_wiki(
                "OTHER_existing",
                wiki_dir,
                source_kind=SourceKind.OTHER,
                source_path=str(source_file),
                profile=ExtractionProfile.DEFAULT,
                force=False,
            )

        assert result == md_file
        mock_logger.debug.assert_called()
