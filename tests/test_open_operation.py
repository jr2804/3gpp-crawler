"""Tests for the shared TDoc open operation."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tdoc_crawler.config import CheckoutConfig
from tdoc_crawler.database.oxyde_models import MainFileOverride, TDocMetadata
from tdoc_crawler.models.main_files import MainFileSelection, MainFileSource
from tdoc_crawler.tdocs.operations.fetch import FetchMissingResult
from tdoc_crawler.tdocs.operations.open import TDocNotFoundError, resolve_tdoc_main_file


class TestResolveTDocMainFile:
    """The CLI and MCP share this orchestration."""

    @patch("tdoc_crawler.tdocs.operations.open.prepare_tdoc_selection")
    @patch("tdoc_crawler.tdocs.operations.open.fetch_missing_tdocs")
    @patch("tdoc_crawler.tdocs.operations.open.TDocDatabase")
    def test_forwards_flags_and_uses_stored_override(
        self,
        mock_db_class: MagicMock,
        mock_fetch: AsyncMock,
        mock_prepare: MagicMock,
        sample_metadata: TDocMetadata,
        tmp_path: Path,
    ) -> None:
        """Flags reach the fetch step and the override reaches the selection step."""
        mock_db = MagicMock()
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.query_tdocs = AsyncMock(return_value=[])
        mock_db.get_main_file_override = AsyncMock(return_value=MainFileOverride(tdoc_id="R1-260001", member_path="docs/main.docx"))
        mock_fetch.return_value = FetchMissingResult(refreshed=[sample_metadata], fetch_result=None)
        mock_prepare.return_value = _selection(tmp_path / "main.docx")

        result = asyncio.run(
            resolve_tdoc_main_file(
                "R1-260001",
                db_file=tmp_path / "db.sqlite3",
                checkout_dir=tmp_path / "checkout",
                checkout_config=CheckoutConfig(),
                full_metadata=True,
                use_whatthespec=True,
            )
        )

        assert result.metadata.tdoc_id == "R1-260001"
        assert result.selection.source is MainFileSource.HEURISTIC
        _, fetch_kwargs = mock_fetch.call_args
        assert fetch_kwargs["full_metadata"] is True
        assert fetch_kwargs["use_whatthespec"] is True
        _, prepare_kwargs = mock_prepare.call_args
        assert prepare_kwargs["override_member"] == "docs/main.docx"

    @patch("tdoc_crawler.tdocs.operations.open.fetch_missing_tdocs")
    @patch("tdoc_crawler.tdocs.operations.open.TDocDatabase")
    def test_missing_tdoc_raises(
        self,
        mock_db_class: MagicMock,
        mock_fetch: AsyncMock,
        tmp_path: Path,
    ) -> None:
        """A TDoc that cannot be fetched raises a dedicated error."""
        mock_db = MagicMock()
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.query_tdocs = AsyncMock(return_value=[])
        mock_fetch.return_value = FetchMissingResult(refreshed=[], fetch_result=None)

        with pytest.raises(TDocNotFoundError, match="TDoc R1-260001 not found"):
            asyncio.run(
                resolve_tdoc_main_file(
                    "R1-260001",
                    db_file=tmp_path / "db.sqlite3",
                    checkout_dir=tmp_path / "checkout",
                    checkout_config=CheckoutConfig(),
                )
            )

    @patch("tdoc_crawler.tdocs.operations.open.prepare_tdoc_selection")
    @patch("tdoc_crawler.tdocs.operations.open.fetch_missing_tdocs")
    @patch("tdoc_crawler.tdocs.operations.open.TDocDatabase")
    def test_collects_fetch_errors(
        self,
        mock_db_class: MagicMock,
        mock_fetch: AsyncMock,
        mock_prepare: MagicMock,
        sample_metadata: TDocMetadata,
        tmp_path: Path,
    ) -> None:
        """Targeted-crawl problems are surfaced to the caller."""
        mock_db = MagicMock()
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.query_tdocs = AsyncMock(return_value=[])
        mock_db.get_main_file_override = AsyncMock(return_value=None)
        crawl_result = MagicMock()
        crawl_result.errors = ["portal timeout"]
        mock_fetch.return_value = FetchMissingResult(refreshed=[sample_metadata], fetch_result=crawl_result)
        mock_prepare.return_value = _selection(tmp_path / "main.docx")

        result = asyncio.run(
            resolve_tdoc_main_file(
                "R1-260001",
                db_file=tmp_path / "db.sqlite3",
                checkout_dir=tmp_path / "checkout",
                checkout_config=CheckoutConfig(),
            )
        )

        assert result.fetch_errors == ("portal timeout",)


def _selection(path: Path) -> MainFileSelection:
    return MainFileSelection(path=path, relative_path=path.name, source=MainFileSource.HEURISTIC)


@pytest.fixture
def sample_metadata() -> TDocMetadata:
    """A minimal stored TDoc record."""
    return TDocMetadata(
        tdoc_id="R1-260001",
        meeting_id=123,
        title="RAN1 discussion document",
        url="https://www.3gpp.org/tsg_ran/RAN1/r1-260001.zip",
        source="RAN1 Chair",
        contact="Test Contact",
        tdoc_type="discussion",
        agenda_item_nbr="3.1",
        agenda_item_text="Test agenda item text",
        status="available",
    )
