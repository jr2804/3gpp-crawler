"""Unit tests for 3GPP metadata enrichment."""

from tdoc_ai.lightrag.metadata import RAGMetadata, create_metadata_from_dict, enrich_text


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
