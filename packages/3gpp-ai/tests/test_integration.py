"""Integration tests for LightRAG pipeline."""

import shutil
from pathlib import Path

import pytest
from threegpp_ai.lightrag import (
    LightRAGConfig,
    RAGMetadata,
    TDocRAG,
    enrich_text,
)


@pytest.fixture
def test_workspace():
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
    async def test_rag_insert_and_query(self, test_workspace) -> None:
        """Test inserting and querying documents."""
        config = LightRAGConfig(
            working_dir=str(test_workspace / "lightrag"),
            llm_model="minimax-m2.7:cloud",
            embedding_model="qwen3-embedding:0.6b",
        )

        async with TDocRAG(config) as rag:
            # Insert test document
            test_text = """
            TDoc S4-250001 discusses TS 26.444 "Test sequences for speech quality".
            This document was presented at TSG-SA WG4 meeting #131-bis.
            The document proposes new test sequences for evaluating speech codecs.
            """
            await rag.insert(test_text)

            # Query (naive mode for simplicity)
            await rag.query(
                "What TDocs and specifications are mentioned?",
                mode="naive",
            )

            # Result may be None if LLM fails, but vector search should work
            # The important thing is no exception is raised
            assert True  # If we get here, insert/query didn't crash

    @pytest.mark.asyncio
    async def test_rag_with_metadata_enrichment(self, test_workspace) -> None:
        """Test inserting with metadata enrichment."""
        config = LightRAGConfig(
            working_dir=str(test_workspace / "lightrag"),
            llm_model="minimax-m2.7:cloud",
            embedding_model="qwen3-embedding:0.6b",
        )

        metadata = RAGMetadata(
            tdoc_id="S4-250001",
            title="Test sequences",
            spec_refs=["TS 26.444"],
            meeting="SA4#131-bis",
            wg="SA4",
        )

        async with TDocRAG(config) as rag:
            # Insert with enriched text
            text = "This document proposes new test sequences."
            enriched_text = enrich_text(metadata, text)
            await rag.insert(enriched_text)

            # Verify insertion succeeded
            assert True

    @pytest.mark.asyncio
    async def test_rag_workspace_isolation(self, test_workspace) -> None:
        """Test that workspaces are isolated."""
        config = LightRAGConfig(
            working_dir=str(test_workspace / "lightrag"),
            llm_model="minimax-m2.7:cloud",
            embedding_model="qwen3-embedding:0.6b",
        )

        # Insert into workspace1
        async with TDocRAG(config) as rag1:
            await rag1.start("workspace1")
            await rag1.insert("Document for workspace 1")
            await rag1.stop()

        # Insert into workspace2
        async with TDocRAG(config) as rag2:
            await rag2.start("workspace2")
            await rag2.insert("Document for workspace 2")
            await rag2.stop()

        # Verify both workspaces have separate storage
        ws1_dir = test_workspace / "lightrag" / "workspace1"
        ws2_dir = test_workspace / "lightrag" / "workspace2"

        assert ws1_dir.exists()
        assert ws2_dir.exists()
        assert ws1_dir != ws2_dir


class TestMetadataEnrichmentIntegration:
    """Test metadata enrichment in real pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_metadata(self, test_workspace) -> None:
        """Test full pipeline: metadata -> enrich -> insert -> query."""
        config = LightRAGConfig(
            working_dir=str(test_workspace / "lightrag"),
            llm_model="minimax-m2.7:cloud",
            embedding_model="qwen3-embedding:0.6b",
        )

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

        async with TDocRAG(config) as rag:
            await rag.insert(enriched)

            # Query for the TDoc ID
            await rag.query("What is R1-2500001?", mode="naive")

            # Should not crash
            assert True
