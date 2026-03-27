"""3GPP metadata enrichment for LightRAG document insertion.

This module provides schema-driven metadata enrichment that prepends
structured 3GPP metadata to document text before LightRAG insertion.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from tdoc_crawler.tdocs.utils import normalize_tdoc_id
from tdoc_crawler.utils.normalization import normalize_release


def normalize_release_label(release: str | None) -> str | None:
    """Normalize release strings to a stable label format for metadata display."""
    normalized_label: str | None = None
    if release is not None:
        cleaned = release.strip()
        if cleaned:
            normalized_label = cleaned
            try:
                release_type, normalized_value, _ = normalize_release(cleaned)
                if release_type == "latest":
                    normalized_label = "latest"
                elif release_type == "all":
                    normalized_label = "all"
                elif normalized_value is not None:
                    normalized_label = f"Rel-{normalized_value.lstrip('-')}"
            except ValueError:
                pass
    return normalized_label


class RAGMetadata(BaseModel):
    """Structured metadata for 3GPP TDoc documents.

    This model defines the metadata contract for enriching documents
    before insertion into LightRAG. The metadata is prepended as a
    deterministic header to ensure consistent entity extraction.

    Attributes:
        tdoc_id: The TDoc identifier (required, e.g., "S4-250001")
        title: Document title (optional)
        source: Metadata source ("whatthespec", "portal", "doclist") (optional)
        spec_refs: List of referenced specifications (e.g., ["TS 26.444", "TR 26.999"])
        meeting: Meeting code (e.g., "SA4#131-bis") (optional)
        release: 3GPP release number (e.g., "Rel-18") (optional)
        wg: Working group (e.g., "SA4", "RAN1") (optional)

    Example:
        >>> metadata = RAGMetadata(
        ...     tdoc_id="S4-250001",
        ...     title="Test sequences for speech quality",
        ...     spec_refs=["TS 26.444"],
        ...     meeting="SA4#131-bis",
        ... )
        >>> print(metadata.tdoc_id)
        S4-250001
    """

    tdoc_id: str
    title: str | None = None
    source: str | None = None
    spec_refs: list[str] = Field(default_factory=list)
    meeting: str | None = None
    release: str | None = None
    wg: str | None = None

    def model_post_init(self, _context: object) -> None:
        """Normalize metadata after initialization."""
        # Normalize tdoc_id: uppercase and strip whitespace
        if self.tdoc_id:
            self.tdoc_id = normalize_tdoc_id(self.tdoc_id)

        # Normalize spec_refs: strip whitespace from each reference
        if self.spec_refs:
            self.spec_refs = [ref.strip() for ref in self.spec_refs if ref.strip()]

        # Normalize release to a consistent label for downstream headers.
        self.release = normalize_release_label(self.release)


def enrich_text(metadata: RAGMetadata, text: str) -> str:
    r"""Prepend normalized metadata to document text for deterministic extraction.

    This function creates a structured header from the metadata and prepends
    it to the document text. The header format is deterministic to ensure
    consistent entity extraction by LightRAG's LLM.

    Args:
        metadata: The document metadata to prepend.
        text: The document text content.

    Returns:
        The enriched text with metadata header.

    Example:
        >>> metadata = RAGMetadata(
        ...     tdoc_id="S4-250001",
        ...     title="Test document",
        ...     spec_refs=["TS 26.444"],
        ... )
        >>> enriched = enrich_text(metadata, "Document content here...")
        >>> print(enriched.split("\\n\\n")[0])
        Document: S4-250001
        Title: Test document
        Related Specifications: TS 26.444
    """
    header_lines = [f"Document: {metadata.tdoc_id}"]

    if metadata.title:
        header_lines.append(f"Title: {metadata.title}")

    if metadata.source:
        header_lines.append(f"Source: {metadata.source}")

    if metadata.spec_refs:
        header_lines.append(f"Related Specifications: {', '.join(metadata.spec_refs)}")

    if metadata.meeting:
        header_lines.append(f"Meeting: {metadata.meeting}")

    if metadata.release:
        header_lines.append(f"Release: {metadata.release}")

    if metadata.wg:
        header_lines.append(f"Working Group: {metadata.wg}")

    header = "\n".join(header_lines)
    return f"{header}\n\n{text}"


def create_metadata_from_dict(data: dict) -> RAGMetadata:
    """Create RAGMetadata from a dictionary (e.g., from SQLite).

    This is a convenience function for creating metadata from database
    query results or other dictionary sources.

    Args:
        data: Dictionary with metadata fields.

    Returns:
        RAGMetadata instance with normalized values.

    Raises:
        ValueError: If required fields are missing.

    Example:
        >>> data = {
        ...     "tdoc_id": "s4-250001",
        ...     "title": "Test document",
        ...     "spec_refs": ["TS 26.444", "TR 26.999"],
        ... }
        >>> metadata = create_metadata_from_dict(data)
        >>> print(metadata.tdoc_id)
        S4-250001
    """
    return RAGMetadata(
        tdoc_id=data.get("tdoc_id", ""),
        title=data.get("title"),
        source=data.get("source"),
        spec_refs=data.get("spec_refs", []),
        meeting=data.get("meeting"),
        release=data.get("release"),
        wg=data.get("wg"),
    )
