"""Unit tests for 3GPP metadata enrichment."""

from __future__ import annotations

import pytest
from threegpp_ai.lightrag.config import LightRAGConfig
from threegpp_ai.lightrag.metadata import RAGMetadata, create_metadata_from_dict, enrich_text
from threegpp_ai.lightrag.rag import TDocRAG


class TestRAGMetadata:
    """Test RAGMetadata model."""

    def test_minimal_metadata(self) -> None:
        """Test metadata with only required field."""
        metadata = RAGMetadata(tdoc_id="S4-250001")
        assert metadata.tdoc_id == "S4-250001"
        assert metadata.title is None
        assert metadata.spec_refs == []

    def test_tdoc_id_normalization(self) -> None:
        """Test tdoc_id is uppercased and stripped."""
        metadata = RAGMetadata(tdoc_id="  s4-250001  ")
        assert metadata.tdoc_id == "S4-250001"

    def test_spec_refs_normalization(self) -> None:
        """Test spec_refs are stripped."""
        metadata = RAGMetadata(
            tdoc_id="S4-250001",
            spec_refs=["  TS 26.444  ", "TR 26.999"],
        )
        assert metadata.spec_refs == ["TS 26.444", "TR 26.999"]

    def test_full_metadata(self) -> None:
        """Test metadata with all fields."""
        metadata = RAGMetadata(
            tdoc_id="S4-250001",
            title="Test sequences for speech quality",
            source="portal",
            spec_refs=["TS 26.444", "TR 26.999"],
            meeting="SA4#131-bis",
            release="Rel-18",
            wg="SA4",
        )
        assert metadata.title == "Test sequences for speech quality"
        assert metadata.source == "portal"
        assert len(metadata.spec_refs) == 2
        assert metadata.meeting == "SA4#131-bis"
        assert metadata.release == "Rel-18"
        assert metadata.wg == "SA4"


class TestEnrichText:
    """Test enrich_text function."""

    def test_enrich_minimal(self) -> None:
        """Test enrichment with minimal metadata."""
        metadata = RAGMetadata(tdoc_id="S4-250001")
        enriched = enrich_text(metadata, "Document content")

        lines = enriched.split("\n")
        assert lines[0] == "Document: S4-250001"
        assert lines[1] == ""
        assert lines[2] == "Document content"

    def test_enrich_full(self) -> None:
        """Test enrichment with full metadata."""
        metadata = RAGMetadata(
            tdoc_id="S4-250001",
            title="Test document",
            source="portal",
            spec_refs=["TS 26.444", "TR 26.999"],
            meeting="SA4#131-bis",
            release="Rel-18",
            wg="SA4",
        )
        enriched = enrich_text(metadata, "Content")

        assert "Document: S4-250001" in enriched
        assert "Title: Test document" in enriched
        assert "Source: portal" in enriched
        assert "Related Specifications: TS 26.444, TR 26.999" in enriched
        assert "Meeting: SA4#131-bis" in enriched
        assert "Release: Rel-18" in enriched
        assert "Working Group: SA4" in enriched

    def test_enrich_deterministic(self) -> None:
        """Test enrichment is deterministic."""
        metadata = RAGMetadata(
            tdoc_id="S4-250001",
            title="Test",
            spec_refs=["TS 26.444"],
        )

        enriched1 = enrich_text(metadata, "Content")
        enriched2 = enrich_text(metadata, "Content")

        assert enriched1 == enriched2

    def test_enrich_empty_spec_refs(self) -> None:
        """Test that empty spec_refs are not included."""
        metadata = RAGMetadata(
            tdoc_id="S4-250001",
            spec_refs=[],
        )
        enriched = enrich_text(metadata, "Content")

        assert "Related Specifications" not in enriched


class TestCreateMetadataFromDict:
    """Test create_metadata_from_dict function."""

    def test_create_from_dict(self) -> None:
        """Test creating metadata from dictionary."""
        data = {
            "tdoc_id": "s4-250001",
            "title": "Test document",
            "spec_refs": ["TS 26.444"],
            "meeting": "SA4#131-bis",
        }
        metadata = create_metadata_from_dict(data)

        assert metadata.tdoc_id == "S4-250001"
        assert metadata.title == "Test document"
        assert metadata.spec_refs == ["TS 26.444"]
        assert metadata.meeting == "SA4#131-bis"

    def test_create_from_dict_empty(self) -> None:
        """Test creating metadata from empty dict."""
        metadata = create_metadata_from_dict({})

        assert metadata.tdoc_id == ""
        assert metadata.spec_refs == []

    def test_create_from_dict_with_none_values(self) -> None:
        """Test creating metadata with None values."""
        data = {
            "tdoc_id": "S4-250001",
            "title": None,
            "source": None,
        }
        metadata = create_metadata_from_dict(data)

        assert metadata.tdoc_id == "S4-250001"
        assert metadata.title is None
        assert metadata.source is None


@pytest.mark.asyncio
async def test_rag_insert_passes_metadata_kwargs() -> None:
    """TDocRAG.insert should pass metadata kwargs through to LightRAG ainsert."""

    class _FakeRag:
        def __init__(self) -> None:
            self.called_with: tuple[str, dict] | None = None

        async def ainsert(self, text: str, **kwargs: dict) -> None:
            self.called_with = (text, kwargs)

    rag = TDocRAG(LightRAGConfig())
    fake = _FakeRag()
    rag._rag = fake  # type: ignore[assignment]

    await rag.insert("sample", metadata={"element_type": "table", "page": 2})

    assert fake.called_with is not None
    assert fake.called_with[0] == "sample"
    assert fake.called_with[1]["metadata"]["element_type"] == "table"


@pytest.mark.asyncio
async def test_rag_query_adds_citation_hint_by_default() -> None:
    """TDocRAG.query should augment query text with citation guidance by default."""

    class _FakeRag:
        def __init__(self) -> None:
            self.last_query: str | None = None

        async def aquery(self, query: str, **kwargs: dict) -> str:
            self.last_query = query
            return "ok"

    rag = TDocRAG(LightRAGConfig())
    fake = _FakeRag()
    rag._rag = fake  # type: ignore[assignment]

    result = await rag.query("What is table 3?", mode="naive")

    assert result == "ok"
    assert fake.last_query is not None
    assert "element type" in fake.last_query


@pytest.mark.asyncio
async def test_rag_query_empty_workspace_returns_empty_result() -> None:
    """TDocRAG.query should gracefully handle empty workspace storage state."""

    class _FakeRag:
        async def aquery(self, query: str, **kwargs: dict) -> str:
            raise KeyError("hashing_kv")

    rag = TDocRAG(LightRAGConfig())
    rag._rag = _FakeRag()  # type: ignore[assignment]

    result = await rag.query("any", mode="naive")

    assert result == ""


@pytest.mark.asyncio
async def test_rag_insert_retries_without_kwargs_for_older_lightrag() -> None:
    """TDocRAG.insert retries without kwargs when LightRAG rejects metadata args."""

    class _LegacyRag:
        def __init__(self) -> None:
            self.calls = 0

        async def ainsert(self, text: str, **kwargs: dict) -> None:
            self.calls += 1
            if kwargs:
                raise TypeError("LightRAG.ainsert() got an unexpected keyword argument 'metadata'")

    rag = TDocRAG(LightRAGConfig())
    legacy = _LegacyRag()
    rag._rag = legacy  # type: ignore[assignment]

    await rag.insert("sample", metadata={"element_type": "table"})

    assert legacy.calls == 2
