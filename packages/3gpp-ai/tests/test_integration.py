"""Integration tests for LightRAG pipeline."""

import shutil
from collections.abc import Generator
from pathlib import Path

import pytest
from threegpp_ai.lightrag import (
    QueryMode,
    RAGMetadata,
    TDocRAG,
    enrich_text,
)


@pytest.fixture
def test_workspace() -> Generator[Path]:
    """Create a test workspace directory."""
    workspace_dir = Path("./test_lightrag_workspace")
    if workspace_dir.exists():
        shutil.rmtree(workspace_dir)
    workspace_dir.mkdir(parents=True)
    yield workspace_dir
    # Cleanup
    if workspace_dir.exists():
        shutil.rmtree(workspace_dir)


class TestTDocRAG:
    """Test TDocRAG integration."""

    @pytest.mark.asyncio
    async def test_rag_insert_and_query(self, test_workspace: Path) -> None:
        """Test inserting and querying documents."""
        async with TDocRAG() as rag:
            # Insert test document
            test_text = """
            TDoc S4-250001 discusses TS 26.444 "Test sequences for speech quality".
            This document was presented at TSG-SA WG4 meeting #131-bis.
            The document proposes new test sequences for evaluating speech codecs.
            """
            await rag.insert(test_text)

            # Query (naive mode for simplicity)
            result = await rag.query(
                "What TDocs and specifications are mentioned?",
                mode="naive",
            )

            assert result.startswith("mocked:")

    @pytest.mark.asyncio
    async def test_rag_with_metadata_enrichment(self, test_workspace: Path) -> None:
        """Test inserting with metadata enrichment."""
        metadata = RAGMetadata(
            tdoc_id="S4-250001",
            title="Test sequences",
            spec_refs=["TS 26.444"],
            meeting="SA4#131-bis",
            wg="SA4",
        )

        async with TDocRAG() as rag:
            # Insert with enriched text
            text = "This document proposes new test sequences."
            enriched_text = enrich_text(metadata, text)
            await rag.insert(enriched_text)

            # Verify insertion succeeded
            assert "Document: S4-250001" in enriched_text

    @pytest.mark.asyncio
    async def test_rag_workspace_isolation(self, test_workspace: Path) -> None:
        """Test that workspaces are isolated."""
        # Insert into workspace1
        async with TDocRAG() as rag1:
            await rag1.start("workspace1")
            await rag1.insert("Document for workspace 1")
            await rag1.stop()
            ws1 = getattr(rag1, "_started_workspace", None)

        # Insert into workspace2
        async with TDocRAG() as rag2:
            await rag2.start("workspace2")
            await rag2.insert("Document for workspace 2")
            await rag2.stop()
            ws2 = getattr(rag2, "_started_workspace", None)

        assert ws1 == "workspace1"
        assert ws2 == "workspace2"
        assert ws1 != ws2

    @pytest.fixture(autouse=True)
    def _mock_runtime(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Mock heavy LightRAG runtime calls so tests stay deterministic."""

        async def _start(self: TDocRAG, workspace: str | None = None) -> None:
            self._started_workspace = workspace or "default"

        async def _stop(self: TDocRAG) -> None:
            return None

        async def _insert(self: TDocRAG, text: str, **kwargs: dict) -> None:
            self._last_insert = {"text": text, "kwargs": kwargs}

        async def _query(
            self: TDocRAG,
            query: str,
            mode: QueryMode | str | None = None,
            **kwargs: dict,
        ) -> str:
            return f"mocked:{query}"

        monkeypatch.setattr(TDocRAG, "start", _start)
        monkeypatch.setattr(TDocRAG, "stop", _stop)
        monkeypatch.setattr(TDocRAG, "insert", _insert)
        monkeypatch.setattr(TDocRAG, "query", _query)


class TestMetadataEnrichmentIntegration:
    """Test metadata enrichment in real pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_metadata(self, test_workspace: Path) -> None:
        """Test full pipeline: metadata -> enrich -> insert -> query."""
        # Create metadata
        metadata = RAGMetadata(
            tdoc_id="R1-2500001",
            title="NR RF requirements",
            spec_refs=["TS 38.101-1", "TS 38.101-2"],
            meeting="RAN1#112",
            release="Rel-17",
            wg="RAN1",
        )

        # Create document text
        doc_text = """
        This TDoc discusses new RF requirements for NR devices.
        The proposed changes affect TS 38.101-1 section 5.2.
        """

        # Enrich and insert
        enriched = enrich_text(metadata, doc_text)

        async with TDocRAG() as rag:
            await rag.insert(enriched)

            # Query for the TDoc ID
            result = await rag.query("What is R1-2500001?", mode="naive")

            assert result.startswith("mocked:")

    @pytest.fixture(autouse=True)
    def _mock_runtime(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Mock LightRAG runtime calls to avoid external dependencies."""

        async def _start(self: TDocRAG, workspace: str | None = None) -> None:
            self._started_workspace = workspace or "default"

        async def _stop(self: TDocRAG) -> None:
            return None

        async def _insert(self: TDocRAG, text: str, **kwargs: dict) -> None:
            self._last_insert = {"text": text, "kwargs": kwargs}

        async def _query(
            self: TDocRAG,
            query: str,
            mode: QueryMode | str | None = None,
            **kwargs: dict,
        ) -> str:
            return f"mocked:{query}"

        monkeypatch.setattr(TDocRAG, "start", _start)
        monkeypatch.setattr(TDocRAG, "stop", _stop)
        monkeypatch.setattr(TDocRAG, "insert", _insert)
        monkeypatch.setattr(TDocRAG, "query", _query)
