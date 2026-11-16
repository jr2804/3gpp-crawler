"""Tests for main-file selection: precedence, decision model, overrides."""

from __future__ import annotations

import asyncio
import zipfile
from pathlib import Path
from unittest.mock import patch

import niquests
import pytest
from typer.testing import CliRunner

from tdoc_crawler.cli.main_file_app import main_file_app
from tdoc_crawler.config.settings import CheckoutConfig
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.main_files import (
    clear_main_file_override,
    get_main_file_override,
    list_main_file_overrides,
    set_main_file_override,
)
from tdoc_crawler.models.main_files import MainFileSelector, MainFileSource
from tdoc_crawler.tdocs.operations.main_file import (
    member_candidates,
    resolve_main_file,
    select_heuristic_main_file,
)


class TestResolvePrecedence:
    """Manual override > decision model > heuristic."""

    def test_override_wins_over_heuristic(self, archive_dir: Path) -> None:
        selection = resolve_main_file(archive_dir, "S4-261599", override_member="Cover sheet.pdf")

        assert selection.relative_path == "Cover sheet.pdf"
        assert selection.source is MainFileSource.MANUAL_OVERRIDE
        assert selection.path.is_file()

    def test_override_missing_from_archive_raises(self, archive_dir: Path) -> None:
        with pytest.raises(FileNotFoundError, match="override-missing-from-archive"):
            resolve_main_file(archive_dir, "S4-261599", override_member="gone.pdf")

    def test_override_cannot_escape_archive(self, archive_dir: Path) -> None:
        with pytest.raises(FileNotFoundError, match="override-escapes-archive"):
            resolve_main_file(archive_dir, "S4-261599", override_member="../outside.pdf")

    def test_heuristic_is_default(self, archive_dir: Path) -> None:
        selection = resolve_main_file(archive_dir, "S4-261599")

        assert selection.source is MainFileSource.HEURISTIC
        assert selection.relative_path == "S4-261599 On binaural capture.docx"

    def test_manual_selector_without_override_raises(self, archive_dir: Path) -> None:
        config = CheckoutConfig(selector=MainFileSelector.MANUAL)

        with pytest.raises(FileNotFoundError, match="selector 'manual' disables"):
            resolve_main_file(archive_dir, "S4-261599", config=config)

    def test_manual_selector_uses_override(self, archive_dir: Path) -> None:
        config = CheckoutConfig(selector=MainFileSelector.MANUAL)

        selection = resolve_main_file(
            archive_dir,
            "S4-261599",
            override_member="Cover sheet.pdf",
            config=config,
        )

        assert selection.source is MainFileSource.MANUAL_OVERRIDE

    def test_decision_model_without_api_key_falls_back(self, archive_dir: Path) -> None:
        config = CheckoutConfig(selector=MainFileSelector.DECISION_MODEL, systemone_api_key=None)

        selection = resolve_main_file(archive_dir, "S4-261599", config=config)

        assert selection.source is MainFileSource.HEURISTIC

    def test_decision_model_choice_wins(self, archive_dir: Path) -> None:
        config = CheckoutConfig(selector=MainFileSelector.DECISION_MODEL, systemone_api_key="key")
        answer = {
            "answers": {
                "has_main_document": {"type": "noul", "noul": 0.95},
                "main_file": {"type": "choice", "choice": "Cover sheet.pdf", "confidence": 0.91},
            }
        }

        with patch("tdoc_crawler.tdocs.operations.main_file._post_systemone", return_value=answer):
            selection = resolve_main_file(archive_dir, "S4-261599", config=config)

        assert selection.relative_path == "Cover sheet.pdf"
        assert selection.source is MainFileSource.DECISION_MODEL
        assert selection.confidence == pytest.approx(0.91)

    def test_decision_model_below_threshold_falls_back(self, archive_dir: Path) -> None:
        config = CheckoutConfig(selector=MainFileSelector.DECISION_MODEL, systemone_api_key="key")
        answer = {
            "answers": {
                "has_main_document": {"type": "noul", "noul": 0.9},
                "main_file": {"type": "choice", "choice": "Cover sheet.pdf", "confidence": 0.4},
            }
        }

        with patch("tdoc_crawler.tdocs.operations.main_file._post_systemone", return_value=answer):
            selection = resolve_main_file(archive_dir, "S4-261599", config=config)

        assert selection.source is MainFileSource.HEURISTIC

    def test_decision_model_no_main_document_falls_back(self, archive_dir: Path) -> None:
        config = CheckoutConfig(selector=MainFileSelector.DECISION_MODEL, systemone_api_key="key")
        answer = {
            "answers": {
                "has_main_document": {"type": "noul", "noul": 0.1},
                "main_file": {"type": "choice", "choice": "Cover sheet.pdf", "confidence": 0.99},
            }
        }

        with patch("tdoc_crawler.tdocs.operations.main_file._post_systemone", return_value=answer):
            selection = resolve_main_file(archive_dir, "S4-261599", config=config)

        assert selection.source is MainFileSource.HEURISTIC

    def test_decision_model_http_failure_falls_back(self, archive_dir: Path) -> None:
        config = CheckoutConfig(selector=MainFileSelector.DECISION_MODEL, systemone_api_key="key")

        with patch(
            "tdoc_crawler.tdocs.operations.main_file._post_systemone",
            side_effect=niquests.RequestException("boom"),
        ):
            selection = resolve_main_file(archive_dir, "S4-261599", config=config)

        assert selection.source is MainFileSource.HEURISTIC

    def test_member_candidates_exclude_clutter(self, archive_dir: Path) -> None:
        (archive_dir / "__MACOSX").mkdir()
        (archive_dir / "__MACOSX" / "._junk.docx").write_bytes(b"junk")

        names = [p.name for p in member_candidates(archive_dir)]

        assert names == ["Agenda item 9.1.pptx", "Cover sheet.pdf", "S4-261599 On binaural capture.docx"]

    def test_heuristic_prefers_tracked_changes_version(self, tmp_path: Path) -> None:
        extract_dir = tmp_path / "S4-242060"
        _docx(extract_dir / "S4-242060 clean.docx")
        _docx(extract_dir / "S4-242060 revised.docx", tracked=True)

        assert select_heuristic_main_file(extract_dir, "S4-242060").name == "S4-242060 revised.docx"


class TestOverrideStorage:
    """Round-trip of the manual main-file override table."""

    def test_set_get_clear(self, test_db_path: Path) -> None:
        async def run() -> None:
            async with TDocDatabase(test_db_path):
                created = await set_main_file_override("S4-261599", "main.docx", note="because")
                assert created.tdoc_id == "S4-261599"

                stored = await get_main_file_override("S4-261599")
                assert stored is not None
                assert stored.member_path == "main.docx"
                assert stored.note == "because"

                replaced = await set_main_file_override("S4-261599", "other.docx")
                assert replaced.member_path == "other.docx"
                assert (await list_main_file_overrides())[0].member_path == "other.docx"

                assert await clear_main_file_override("S4-261599") is True
                assert await get_main_file_override("S4-261599") is None
                assert await clear_main_file_override("S4-261599") is False

        asyncio.run(run())

    @pytest.mark.parametrize("bad_path", ["", "/etc/passwd", "../escape.docx"])
    def test_rejects_invalid_member_paths(self, test_db_path: Path, bad_path: str) -> None:
        async def run() -> None:
            async with TDocDatabase(test_db_path):
                await set_main_file_override("S4-261599", bad_path)

        with pytest.raises(ValueError, match="invalid-member-path"):
            asyncio.run(run())


class TestMainFileCli:
    """`tdoc main-file` commands against a temporary database."""

    def test_set_show_list_clear(self, test_db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("tdoc_crawler.cli.main_file_app._db_file", lambda: test_db_path)
        runner = CliRunner()

        result = runner.invoke(main_file_app, ["set", "S4-261599", "Cover sheet.pdf", "--note", "manual"])
        assert result.exit_code == 0, result.output
        assert "Cover sheet.pdf" in result.output

        result = runner.invoke(main_file_app, ["show", "S4-261599"])
        assert result.exit_code == 0, result.output
        assert "Cover sheet.pdf" in result.output

        result = runner.invoke(main_file_app, ["list"])
        assert result.exit_code == 0, result.output
        assert "S4-261599" in result.output

        result = runner.invoke(main_file_app, ["clear", "S4-261599"])
        assert result.exit_code == 0, result.output

        result = runner.invoke(main_file_app, ["show", "S4-261599"])
        assert result.exit_code == 0, result.output
        assert "Cover sheet.pdf" not in result.output


@pytest.fixture
def archive_dir(tmp_path: Path) -> Path:
    """Extract dir with a main document plus two attachments."""
    extract_dir = tmp_path / "S4-261599"
    _docx(extract_dir / "S4-261599 On binaural capture.docx")
    (extract_dir / "Cover sheet.pdf").write_bytes(b"%PDF-1.4")
    (extract_dir / "Agenda item 9.1.pptx").write_bytes(b"ppt")
    return extract_dir


def _docx(path: Path, *, tracked: bool = False) -> Path:
    """Write a minimal OOXML zip; ``tracked`` adds revision-mark XML."""
    body = b"<w:document><w:body><w:p><w:r><w:t>x</w:t></w:r></w:p></w:body></w:document>"
    if tracked:
        body = b"<w:document><w:body><w:ins><w:r><w:t>x</w:t></w:r></w:ins></w:body></w:document>"
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", body)
    return path
