"""Tests for stored main-file classifications and re-classification."""

from __future__ import annotations

import asyncio
import zipfile
from collections.abc import AsyncGenerator, Coroutine
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from tdoc_crawler.cli.main_file_app import main_file_app
from tdoc_crawler.config.settings import CheckoutConfig
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.main_files import (
    get_main_file_override,
    get_main_file_record,
    save_main_file_record,
    set_main_file_override,
)
from tdoc_crawler.database.oxyde_models import MainFileOverride, MainFileRecord, TDocMetadata
from tdoc_crawler.models.main_files import MainFileSelector, ReclassifyStatus
from tdoc_crawler.tdocs.operations.checkout import get_checkout_path
from tdoc_crawler.tdocs.operations.reclassify import ReclassifyOutcome, reclassify_tdocs


class TestReclassify:
    """Re-classification preserves computed memory but protects user choices."""

    def test_updates_heuristic_classification(self, reclassify_env: ReclassifyEnv) -> None:
        outcomes = asyncio.run(reclassify_env.run())

        assert [outcome.status for outcome in outcomes] == [ReclassifyStatus.UPDATED]
        assert outcomes[0].selection is not None
        assert outcomes[0].selection.relative_path == "S4-261599 On binaural capture.docx"

        record = asyncio.run(reclassify_env.record())
        assert record is not None
        assert record.member_path == "S4-261599 On binaural capture.docx"
        assert record.selector == "heuristic"

    def test_protects_manual_override_by_default(self, reclassify_env: ReclassifyEnv) -> None:
        asyncio.run(reclassify_env.set_override("Cover sheet.pdf"))

        outcomes = asyncio.run(reclassify_env.run())

        assert outcomes[0].status is ReclassifyStatus.SKIPPED
        assert "manual choice protected" in outcomes[0].message
        assert asyncio.run(reclassify_env.override()) is not None

    def test_include_manual_deletes_override(self, reclassify_env: ReclassifyEnv) -> None:
        asyncio.run(reclassify_env.set_override("Cover sheet.pdf"))

        outcomes = asyncio.run(reclassify_env.run(include_manual=True))

        assert outcomes[0].status is ReclassifyStatus.UPDATED
        assert asyncio.run(reclassify_env.override()) is None

    def test_manual_selector_skips_without_override(self, reclassify_env: ReclassifyEnv) -> None:
        asyncio.run(reclassify_env.save_record(selector="manual"))

        outcomes = asyncio.run(reclassify_env.run())

        assert outcomes[0].status is ReclassifyStatus.SKIPPED

    def test_missing_when_not_checked_out(self, reclassify_env: ReclassifyEnv) -> None:
        reclassify_env.remove_checkout()

        outcomes = asyncio.run(reclassify_env.run())

        assert outcomes[0].status is ReclassifyStatus.MISSING
        assert "not checked out" in outcomes[0].message


class TestReclassifyCli:
    """The CLI requires an explicit target set."""

    def test_requires_ids_or_all(self, reclassify_env: ReclassifyEnv) -> None:
        runner = CliRunner()
        result = runner.invoke(main_file_app, ["reclassify"])

        assert result.exit_code == 2
        assert "Pass at least one TDoc ID, or --all" in result.output

    def test_include_manual_requires_confirmation(self, reclassify_env: ReclassifyEnv) -> None:
        runner = CliRunner()
        result = runner.invoke(main_file_app, ["reclassify", "S4-261599", "--include-manual"])

        assert result.exit_code == 2
        assert "--confirm-overwrite" in result.output


class ReclassifyEnv:
    """A checked-out TDoc with stored metadata and classification."""

    def __init__(self, db_file: Path, checkout_dir: Path, metadata: TDocMetadata, extract_dir: Path) -> None:
        self.db_file = db_file
        self.checkout_dir = checkout_dir
        self.metadata = metadata
        self.extract_dir = extract_dir

    def run(
        self,
        *,
        include_manual: bool = False,
        selector: MainFileSelector = MainFileSelector.HEURISTIC,
    ) -> Coroutine[Any, Any, list[ReclassifyOutcome]]:
        return reclassify_tdocs(
            db_file=self.db_file,
            checkout_dir=self.checkout_dir,
            checkout_config=CheckoutConfig(selector=selector),
            include_manual=include_manual,
        )

    async def record(self) -> MainFileRecord | None:
        async with self._db():
            return await get_main_file_record(self.metadata.tdoc_id)

    async def override(self) -> MainFileOverride | None:
        async with self._db():
            return await get_main_file_override(self.metadata.tdoc_id)

    async def set_override(self, member_path: str) -> None:
        async with self._db():
            await set_main_file_override(self.metadata.tdoc_id, member_path)

    async def save_record(self, *, selector: str) -> None:
        async with self._db():
            await save_main_file_record(
                self.metadata.tdoc_id,
                member_path="old.docx",
                source="heuristic",
                selector=selector,
            )

    def remove_checkout(self) -> None:
        for path in sorted(self.extract_dir.rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        self.extract_dir.rmdir()

    @asynccontextmanager
    async def _db(self) -> AsyncGenerator[TDocDatabase]:
        async with TDocDatabase(self.db_file) as database:
            yield database


@pytest.fixture
def reclassify_env(tmp_path: Path) -> ReclassifyEnv:
    """Create metadata, a stored classification, and an extracted archive."""
    db_file = tmp_path / "db.sqlite3"
    checkout_dir = tmp_path / "checkout"
    metadata = TDocMetadata(
        tdoc_id="S4-261599",
        meeting_id=123,
        title="On binaural capture",
        url="https://www.3gpp.org/ftp/tsg_sa/TSG_SA/TSGS_100/S4-261599.zip",
        source="S4 Chair",
        contact="Test Contact",
        tdoc_type="discussion",
        agenda_item_nbr="9.1",
        agenda_item_text="Binaural capture",
        status="available",
    )

    extract_dir = get_checkout_path(metadata, checkout_dir)
    extract_dir.mkdir(parents=True)
    _docx(extract_dir / "S4-261599 On binaural capture.docx")
    (extract_dir / "Cover sheet.pdf").write_bytes(b"%PDF-1.4")

    async def _seed() -> None:
        async with TDocDatabase(db_file) as database:
            await database.upsert_tdoc(metadata)
            await save_main_file_record(
                metadata.tdoc_id,
                member_path="old.docx",
                source="heuristic",
                selector="heuristic",
            )

    asyncio.run(_seed())
    return ReclassifyEnv(db_file, checkout_dir, metadata, extract_dir)


def _docx(path: Path) -> Path:
    """Write a minimal OOXML zip."""
    body = b"<w:document><w:body><w:p><w:r><w:t>x</w:t></w:r></w:p></w:body></w:document>"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", body)
    return path
