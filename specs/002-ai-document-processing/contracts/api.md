# API Contracts: AI Document Processing Pipeline

**Date**: 2026-02-24
**Source**: [spec.md](../spec.md) FRs + [data-model.md](../data-model.md) entities

## Module: `tdoc_crawler.ai`

### Public API (exposed from `__init__.py`)

```python
from tdoc_crawler.ai.models import (
    AiConfig,
    DocumentChunk,
    DocumentClassification,
    DocumentSummary,
    GraphEdge,
    GraphNode,
    PipelineStage,
    ProcessingStatus,
)


def process_tdoc(
    tdoc_id: str,
    config: AiConfig | None = None,
    stages: list[PipelineStage] | None = None,
) -> ProcessingStatus:
    """Process a single TDoc through the AI pipeline.

    Args:
        tdoc_id: TDoc identifier (e.g., "SP-123456"). Normalized via .upper().
        config: Pipeline configuration. If None, loads from default config file.
        stages: Specific stages to run. If None, runs all applicable stages.

    Returns:
        Updated ProcessingStatus after pipeline execution.

    Raises:
        TDocNotFoundError: If the TDoc is not in the database or has no files.
        AiConfigError: If required configuration (e.g., LLM endpoint) is missing.
    """


def process_all(
    config: AiConfig | None = None,
    new_only: bool = False,
    stages: list[PipelineStage] | None = None,
    progress_callback: Callable[[str, PipelineStage], None] | None = None,
) -> list[ProcessingStatus]:
    """Batch process all (or new-only) TDocs through the AI pipeline.

    Args:
        config: Pipeline configuration. If None, loads from default config file.
        new_only: If True, only process TDocs not yet in processing_status.
        stages: Specific stages to run. If None, runs all applicable stages.
        progress_callback: Called with (tdoc_id, stage) for progress reporting.

    Returns:
        List of ProcessingStatus for all processed TDocs.
    """


def get_status(
    tdoc_id: str | None = None,
) -> ProcessingStatus | list[ProcessingStatus]:
    """Get processing status for one or all TDocs.

    Args:
        tdoc_id: If provided, return status for this TDoc. If None, return all.

    Returns:
        Single ProcessingStatus or list of all statuses.

    Raises:
        TDocNotFoundError: If tdoc_id is provided but not found.
    """


def query_embeddings(
    query: str,
    top_k: int = 5,
    tdoc_filter: list[str] | None = None,
    config: AiConfig | None = None,
) -> list[tuple[DocumentChunk, float]]:
    """Semantic search over embedded document chunks.

    Args:
        query: Natural language query text.
        top_k: Number of top results to return.
        tdoc_filter: Optional list of TDoc IDs to restrict search to.
        config: Pipeline configuration (for embedding model).

    Returns:
        List of (chunk, similarity_score) tuples, sorted by descending score.
    """


def query_graph(
    query: str,
    temporal_range: tuple[datetime, datetime] | None = None,
    node_types: list[str] | None = None,
    config: AiConfig | None = None,
) -> dict[str, Any]:
    """Query the temporal knowledge graph.

    Args:
        query: Natural language query about relationships/evolution.
        temporal_range: Optional (start, end) datetime filter.
        node_types: Optional filter for node types.
        config: Pipeline configuration.

    Returns:
        Dict with keys "nodes" (list[GraphNode]), "edges" (list[GraphEdge]),
        "answer" (str) — the synthesized response.
    """
```

## Module: `tdoc_crawler.ai.operations.extract`

```python
def extract_docx_to_markdown(
    docx_path: Path,
    output_dir: Path,
) -> Path:
    """Convert a DOCX file to Markdown using extraction library.

    Note: Uses Docling in Phases 1-8. Replaced by Kreuzberg in Phase 9 with full refactoring (no backward compatibility).


    Args:
        docx_path: Path to the source DOCX file.
        output_dir: Directory where the Markdown file will be written.

    Returns:
        Path to the generated Markdown file.

    Raises:
        ExtractionError: If DOCX is corrupt, password-protected, or conversion fails.
    """
```

## Module: `tdoc_crawler.ai.operations.classify`

```python
def classify_tdoc_files(
    tdoc_id: str,
    file_paths: list[Path],
) -> list[DocumentClassification]:
    """Classify files in a TDoc folder as main or secondary.

    Args:
        tdoc_id: The TDoc identifier.
        file_paths: List of DOCX files found in the TDoc folder.

    Returns:
        Classification for each file, with exactly one marked as main.
    """
```

## Module: `tdoc_crawler.ai.operations.embed`

```python
def chunk_and_embed(
    tdoc_id: str,
    markdown_path: Path,
    config: AiConfig,
) -> list[DocumentChunk]:
    """Split Markdown into chunks and generate embeddings.

    Args:
        tdoc_id: The TDoc identifier.
        markdown_path: Path to the extracted Markdown file.
        config: Configuration (embedding model, chunk size, overlap).

    Returns:
        List of DocumentChunk objects with vectors populated.
    """
```

## Module: `tdoc_crawler.ai.operations.summarize`

```python
def summarize_tdoc(
    tdoc_id: str,
    markdown_path: Path,
    config: AiConfig,
) -> DocumentSummary:
    """Generate an abstract and structured summary using an LLM.

    Args:
        tdoc_id: The TDoc identifier.
        markdown_path: Path to the extracted Markdown file.
        config: Configuration (LLM model, prompt version, word count bounds).

    Returns:
        DocumentSummary with abstract, key_points, action_items, decisions.

    Raises:
        LlmConfigError: If no LLM endpoint is configured or reachable.
    """
```

## Module: `tdoc_crawler.ai.operations.graph`

```python
def build_graph_for_tdoc(
    tdoc_id: str,
    markdown_path: Path,
    summary: DocumentSummary,
    config: AiConfig,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Extract entities and relationships from a TDoc and add to the graph.

    Args:
        tdoc_id: The TDoc identifier.
        markdown_path: Path to the extracted Markdown file.
        summary: Previously generated summary (for entity hints).
        config: Configuration.

    Returns:
        Tuple of (new nodes, new edges) added to the graph.
    """
```

## Module: `tdoc_crawler.ai.operations.pipeline`

```python
def run_pipeline(
    tdoc_id: str,
    config: AiConfig,
    stages: list[PipelineStage] | None = None,
) -> ProcessingStatus:
    """Run the full pipeline for a single TDoc, respecting resume logic.

    Checks ProcessingStatus to determine where to resume. Executes stages
    in order: classify -> extract -> embed -> summarize -> graph.

    Args:
        tdoc_id: The TDoc identifier.
        config: Pipeline configuration.
        stages: If provided, only run these stages.

    Returns:
        Updated ProcessingStatus.
    """
```

## Module: `tdoc_crawler.ai.storage`

```python
class AiStorage:
    """LanceDB storage layer for all AI-generated data."""

    def __init__(self, store_path: Path) -> None:
        """Initialize LanceDB connection at the given path."""

    def save_status(self, status: ProcessingStatus) -> None: ...
    def get_status(self, tdoc_id: str) -> ProcessingStatus | None: ...
    def list_statuses(self) -> list[ProcessingStatus]: ...

    def save_classifications(self, classifications: list[DocumentClassification]) -> None: ...
    def get_classifications(self, tdoc_id: str) -> list[DocumentClassification]: ...

    def save_chunks(self, chunks: list[DocumentChunk]) -> None: ...
    def search_chunks(self, query_vector: list[float], top_k: int) -> list[tuple[DocumentChunk, float]]: ...

    def save_summary(self, summary: DocumentSummary) -> None: ...
    def get_summary(self, tdoc_id: str) -> DocumentSummary | None: ...

    def save_nodes(self, nodes: list[GraphNode]) -> None: ...
    def save_edges(self, edges: list[GraphEdge]) -> None: ...
    def query_graph(self, filters: dict[str, Any]) -> tuple[list[GraphNode], list[GraphEdge]]: ...
```

## Error Types

```python
class AiError(Exception):
    """Base exception for AI processing errors."""

class TDocNotFoundError(AiError):
    """TDoc not found in database or has no files."""

class ExtractionError(AiError):
    """DOCX extraction failed (corrupt, password-protected, etc.)."""

class LlmConfigError(AiError):
    """LLM endpoint not configured or unreachable."""

class AiConfigError(AiError):
    """Invalid or missing AI configuration."""

class EmbeddingDimensionError(AiError):
    """Embedding model dimension mismatch with stored vectors."""
```
