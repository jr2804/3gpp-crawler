"""Embeddings generation and storage using sentence-transformers."""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from sentence_transformers import SentenceTransformer

from tdoc_crawler.ai.config import AiConfig
from tdoc_crawler.ai.models import DocumentChunk
from tdoc_crawler.ai.operations.workspaces import normalize_workspace_name
from tdoc_crawler.ai.storage import AiStorage
from tdoc_crawler.utils.misc import utc_now

logger = logging.getLogger(__name__)

# Default embedding model
DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_DIMENSION = 384

# Chunk size settings
DEFAULT_MAX_CHARS = 500
DEFAULT_OVERLAP = 50


def get_embedding_model() -> EmbeddingModelWrapper:
    """Get the embedding model, initializing if needed.

    Returns:
        EmbeddingModelWrapper instance.
    """
    return EmbeddingModelWrapper()


class EmbeddingModelWrapper:
    """Wrapper for sentence-transformers model."""

    _instance: EmbeddingModelWrapper | None = None
    _model: Any = None
    _model_name = DEFAULT_MODEL

    def __new__(cls) -> EmbeddingModelWrapper:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._model is None:
            self._load_model()

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        """Encode texts to embeddings.

        Args:
            texts: List of text strings to encode.

        Returns:
            List of embedding vectors.
        """
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        # Get dimension from the actual model
        try:
            return self._model.get_sentence_embedding_dimension()
        except Exception:
            return DEFAULT_DIMENSION

    @property
    def model_name(self) -> str:
        """Return model name."""
        return self._model_name

    def _load_model(self) -> None:
        """Load the sentence-transformers model."""
        self._model = SentenceTransformer(DEFAULT_MODEL)
        logger.info(f"Loaded embedding model: {DEFAULT_MODEL}")


def _chunk_by_headings(markdown: str) -> list[dict[str, str]]:
    """Split markdown content by heading sections.

    Args:
        markdown: Markdown content.

    Returns:
        List of dicts with 'section' and 'content' keys.
    """
    # Split by markdown headings (# ## ### etc)
    heading_pattern = r"(?m)^(#{1,6})\s+(.+)$"

    parts = re.split(heading_pattern, markdown)
    chunks: list[dict[str, str]] = []

    current_section = "Introduction"
    current_content: list[str] = []

    for i, part in enumerate(parts):
        if i % 3 == 0:
            # Content between headings
            if part.strip():
                current_content.append(part.strip())
        elif i % 3 == 2:
            # Heading text
            # Save previous chunk if exists
            if current_content:
                chunks.append(
                    {
                        "section": current_section,
                        "content": "\n\n".join(current_content),
                    }
                )
                current_content = []

            current_section = part.strip()

    # Add final chunk
    if current_content:
        chunks.append(
            {
                "section": current_section,
                "content": "\n\n".join(current_content),
            }
        )

    # If no headings found, treat as single chunk
    if not chunks:
        chunks.append(
            {
                "section": "Document",
                "content": markdown,
            }
        )

    return chunks


def _chunk_by_paragraphs(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    """Split text into chunks by paragraphs.

    Args:
        text: Text to chunk.
        max_chars: Maximum characters per chunk.

    Returns:
        List of text chunks.
    """
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for paragraph in paragraphs:
        stripped_paragraph = paragraph.strip()
        if not stripped_paragraph:
            continue

        if len(stripped_paragraph) > max_chars:
            words = stripped_paragraph.split()
            partial: list[str] = []
            partial_len = 0
            for word in words:
                candidate_len = partial_len + len(word) + (1 if partial else 0)
                if candidate_len > max_chars and partial:
                    chunks.append(" ".join(partial))
                    partial = [word]
                    partial_len = len(word)
                else:
                    partial.append(word)
                    partial_len = candidate_len
            if partial:
                chunks.append(" ".join(partial))
            continue

        para_len = len(stripped_paragraph)

        if current_len + para_len > max_chars and current:
            chunks.append("\n\n".join(current))
            current = [stripped_paragraph]
            current_len = para_len
        else:
            current.append(stripped_paragraph)
            current_len += para_len

    if current:
        chunks.append("\n\n".join(current))

    if len(chunks) <= 1:
        return chunks

    overlapped_chunks: list[str] = [chunks[0]]
    for index in range(1, len(chunks)):
        previous_words = chunks[index - 1].split()
        overlap_words = previous_words[-10:] if len(previous_words) > 10 else previous_words
        overlapped_chunks.append(f"{' '.join(overlap_words)} {chunks[index]}".strip())

    return overlapped_chunks


def _create_chunks(tdoc_id: str, markdown: str) -> list[DocumentChunk]:
    """Create document chunks from markdown.

    Args:
        tdoc_id: TDoc identifier.
        markdown: Markdown content.

    Returns:
        List of DocumentChunk objects.
    """
    # First try heading-based chunking
    sections = _chunk_by_headings(markdown)

    chunks: list[DocumentChunk] = []

    for i, section in enumerate(sections):
        content = section["content"]
        section_name = section["section"]

        # If section is too long, chunk by paragraphs
        if len(content) > DEFAULT_MAX_CHARS * 2:
            sub_chunks = _chunk_by_paragraphs(content)
            for j, sub_content in enumerate(sub_chunks):
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{tdoc_id}:{i * 100 + j}",
                        tdoc_id=tdoc_id,
                        section_heading=f"{section_name} ({j + 1})",
                        chunk_index=i * 100 + j,
                        text=sub_content,
                        char_offset_start=0,
                        char_offset_end=len(sub_content),
                        vector=[],
                        embedding_model=DEFAULT_MODEL,
                        created_at=utc_now(),
                    )
                )
        else:
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{tdoc_id}:{i}",
                    tdoc_id=tdoc_id,
                    section_heading=section_name,
                    chunk_index=i,
                    text=content,
                    char_offset_start=0,
                    char_offset_end=len(content),
                    vector=[],
                    embedding_model=DEFAULT_MODEL,
                    created_at=utc_now(),
                )
            )

    logger.info(f"Created {len(chunks)} chunks for {tdoc_id}")
    return chunks


def _should_skip_embedding(tdoc_id: str, content_hash: str) -> bool:
    """Check if embedding should be skipped based on content hash.

    Args:
        tdoc_id: TDoc identifier.
        content_hash: Hash of the content.

    Returns:
        True if embedding exists and is current.
    """
    try:
        config = AiConfig.from_env(cache_manager_name="default")
        model = get_embedding_model()
        storage_client = AiStorage(config.ai_store_path, embedding_dimension=model.dimension)
        existing_hash = storage_client.get_embedding_hash(tdoc_id)
        return existing_hash == content_hash
    except Exception:
        return False


def generate_embeddings(
    tdoc_id: str,
    markdown: str | Path,
    storage: AiStorage | None = None,
    workspace: str | None = None,
) -> list[DocumentChunk]:
    """Generate embeddings for markdown content.

    Args:
        tdoc_id: TDoc identifier.
        markdown: Markdown content to embed.
        storage: Optional storage instance.
        workspace: Optional workspace scope (defaults to "default").

    Returns:
        List of DocumentChunk objects with embeddings.
    """
    if storage is None:
        config = AiConfig.from_env(cache_manager_name="default")
        model = get_embedding_model()
        storage = AiStorage(config.ai_store_path, embedding_dimension=model.dimension)

    normalized_workspace = normalize_workspace_name(workspace)
    markdown_content = markdown.read_text(encoding="utf-8") if isinstance(markdown, Path) else markdown

    # Compute content hash for idempotency
    content_hash = hashlib.sha256(markdown_content.encode("utf-8")).hexdigest()

    if _should_skip_embedding(tdoc_id, content_hash):
        logger.info(f"Skipping embedding for {tdoc_id} - content unchanged")
        return []

    # Create chunks
    chunks = _create_chunks(tdoc_id, markdown_content)

    if not chunks:
        return []

    # Get embedding model
    model = get_embedding_model()

    # Extract text for embedding
    texts = [chunk.content for chunk in chunks]

    # Generate embeddings
    try:
        embeddings = model.encode(texts)

        # Attach embeddings to chunks
        for chunk, embedding in zip(chunks, embeddings, strict=False):
            if hasattr(embedding, "tolist"):
                chunk.embedding = [float(value) for value in embedding.tolist()]
            else:
                chunk.embedding = [float(value) for value in embedding]
            chunk.embedding_model = model.model_name

        storage.save_chunks(chunks, workspace=normalized_workspace)

        # Store hash for future idempotency
        storage.save_embedding_hash(tdoc_id, content_hash)

        logger.info(f"Generated {len(chunks)} embeddings for {tdoc_id}")
        return chunks

    except Exception as e:
        logger.error(f"Failed to generate embeddings for {tdoc_id}: {e}")
        raise


def query_embeddings(
    query: str,
    workspace: str,
    top_k: int = 5,
) -> list[tuple[DocumentChunk, float]]:
    """Query embeddings using semantic search.

    Args:
        query: Search query.
        workspace: Workspace scope (required).
        top_k: Number of results to return.

    Returns:
        List of (DocumentChunk, score) tuples.
    """
    config = AiConfig.from_env(cache_manager_name="default")
    storage = AiStorage(config.ai_store_path)  # type: ignore[arg-type]
    normalized_workspace = normalize_workspace_name(workspace)

    # Get embedding model
    model = get_embedding_model()

    # Encode query
    query_embedding = cast(Any, model.encode([query])[0])
    query_vector = [float(value) for value in query_embedding.tolist()] if hasattr(query_embedding, "tolist") else [float(value) for value in query_embedding]

    # Search in storage
    return storage.search_chunks(query_vector, top_k, workspace=normalized_workspace)


__all__ = [
    "generate_embeddings",
    "get_embedding_model",
    "query_embeddings",
]
