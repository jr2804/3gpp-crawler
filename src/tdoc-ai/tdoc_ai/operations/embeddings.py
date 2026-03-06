"""Embeddings generation and storage using sentence-transformers."""

import hashlib
import logging
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from sentence_transformers import SentenceTransformer

from tdoc_ai.config import AiConfig, Backend
from tdoc_ai.models import DocumentChunk
from tdoc_ai.operations.workspace_names import normalize_workspace_name
from tdoc_ai.storage import AiStorage
from tdoc_crawler.utils.misc import utc_now

logger = logging.getLogger(__name__)

# Chunk size settings
DEFAULT_MAX_CHARS = 500
DEFAULT_OVERLAP = 50
MAX_NBR_CHUNKS = 10000


class EmbeddingsManager:
    """Manages embedding model and storage for document embedding and retrieval.

    This class handles both the embedding model lifecycle and storage initialization.
    """

    def __init__(
        self,
        config: AiConfig
    ) -> None:
        """Initialize embeddings manager.

        Args:
            config: AI configuration.
        """
        self._config = config

        # will be initialized lazily on first access to allow for faster startup and to ensure correct device selection based on backend
        self._storage = None
        self._model = None

    @property
    def embedding_backend(self) -> Backend:
        """Return the embedding backend."""
        return self.config.embedding_backend

    @property
    def config(self) -> AiConfig:
        """Return the AI configuration."""
        return self._config

    @property
    def storage(self) -> AiStorage:
        """Return the storage instance.

        If storage was not provided during initialization and this is called
        before the model is accessed, it will trigger model loading which
        creates the storage.

        Returns:
            AiStorage instance.

        Raises:
            RuntimeError: If neither storage nor model was provided at init.
        """

        if self._storage is None:
            self._storage = AiStorage(self.config.ai_cache_dir, embedding_dimension=self.dimension)
            logger.info(f"Initialized AiStorage at {self.config.ai_cache_dir} with dimension {self.dimension}")

        return self._storage

    @property
    def model(self) -> SentenceTransformer:
        """Return the sentence-transformers model, loading it lazily on first access."""
        if self._model is None:
            self._model = SentenceTransformer(
                self._config.embedding_model,
                trust_remote_code=True,
                device=None, # uses GPU if available, otherwise CPU (note: OpenVINO backend requires device="cpu")
            )
            logger.info(f"Loaded embedding model: {self._config.embedding_model}")

        return self._model

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        dim = self.model.get_sentence_embedding_dimension()
        if dim is None:
            raise RuntimeError(f"Model '{self._config.embedding_model}' did not report an embedding dimension")
        return dim

    @property
    def model_name(self) -> str:
        """Return model name."""
        return self._config.embedding_model

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        """Encode texts to embeddings.

        Args:
            texts: List of text strings to encode.

        Returns:
            List of embedding vectors.
        """
        embeddings = self.model.encode(list(texts), normalize_embeddings=True, convert_to_numpy=True)
        return embeddings.tolist()

    def generate_embeddings(self, document_id: str, markdown: str | Path, workspace: str | None = None) -> list[DocumentChunk]:
        """Generate embeddings for markdown content.

        Args:
            document_id: Document identifier.
            markdown: Markdown content to embed.
            workspace: Optional workspace scope (defaults to "default").

        Returns:
            List of DocumentChunk objects with embeddings.
        """
        normalized_workspace = normalize_workspace_name(workspace)
        markdown_content = markdown.read_text(encoding="utf-8") if isinstance(markdown, Path) else markdown

        # Compute content hash for idempotency
        content_hash = hashlib.sha256(markdown_content.encode("utf-8")).hexdigest()

        storage = self.storage
        existing_hash = storage.get_embedding_hash(document_id)
        if existing_hash == content_hash:
            logger.info(f"Skipping embedding for {document_id} - content unchanged")
            return []

        # Create chunks
        chunks = self._create_chunks(document_id, markdown_content, self.model_name)

        if not chunks:
            return []

        # Extract text for embedding
        texts = [chunk.content for chunk in chunks]

        # Generate embeddings
        try:
            embeddings = self.encode(texts)

            # Attach embeddings to chunks
            for chunk, embedding in zip(chunks, embeddings, strict=False):
                chunk.embedding = [float(value) for value in embedding]
                chunk.embedding_model = self._config.embedding_model

            storage.save_chunks(chunks, workspace=normalized_workspace)

            # Store hash for future idempotency
            storage.save_embedding_hash(document_id, content_hash)

            logger.info(f"Generated {len(chunks)} embeddings for {document_id}")
            return chunks

        except Exception as e:
            logger.error(f"Failed to generate embeddings for {document_id}: {e}")
            raise

    def query_embeddings(self, query: str, workspace: str, top_k: int = 5) -> list[tuple[DocumentChunk, float]]:
        """Query embeddings using semantic search.

        Args:
            query: Search query.
            workspace: Workspace scope (required).
            top_k: Number of results to return.

        Returns:
            List of (DocumentChunk, score) tuples.
        """
        storage = self.storage
        normalized_workspace = normalize_workspace_name(workspace)

        # Encode query
        query_embedding = cast(Any, self.encode([query])[0])
        if isinstance(query_embedding, list):
            query_vector = [float(value) for value in query_embedding]
        else:
            query_vector = [float(value) for value in query_embedding.tolist()]

        # Search in storage
        return storage.search_chunks(query_vector, top_k, workspace=normalized_workspace)

    @classmethod
    def _chunk_by_paragraphs(cls, text: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
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

    @classmethod
    def _create_chunks(cls, document_id: str, markdown: str, model_name: str) -> list[DocumentChunk]:
        """Create document chunks from markdown.

        Args:
            document_id: Document identifier.
            markdown: Markdown content.
            model_name: Embedding model name to tag on each chunk.

        Returns:
            List of DocumentChunk objects.
        """
        # First try heading-based chunking
        sections = cls._chunk_by_headings(markdown)

        chunks: list[DocumentChunk] = []

        for i, section in enumerate(sections):
            content = section["content"]
            section_name = section["section"]

            # If section is too long, chunk by paragraphs
            if len(content) > DEFAULT_MAX_CHARS * 2:
                sub_chunks = cls._chunk_by_paragraphs(content)
                for j, sub_content in enumerate(sub_chunks):
                    chunks.append(
                        DocumentChunk(
                            chunk_id=f"{document_id}:{i * MAX_NBR_CHUNKS + j}",
                            document_id=document_id,
                            section_heading=f"{section_name} ({j + 1})",
                            chunk_index=i * MAX_NBR_CHUNKS + j,
                            text=sub_content,
                            char_offset_start=0,
                            char_offset_end=len(sub_content),
                            vector=[],
                            embedding_model=model_name,
                            created_at=utc_now(),
                        )
                    )
            else:
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{document_id}:{i}",
                        document_id=document_id,
                        section_heading=section_name,
                        chunk_index=i,
                        text=content,
                        char_offset_start=0,
                        char_offset_end=len(content),
                        vector=[],
                        embedding_model=model_name,
                        created_at=utc_now(),
                    )
                )

        logger.info(f"Created {len(chunks)} chunks for {document_id}")
        return chunks

    @staticmethod
    def _get_dimension(model: SentenceTransformer) -> int:
        """Get embedding dimension from model.

        Args:
            model: SentenceTransformer model instance.

        Returns:
            Embedding dimension.

        Raises:
            RuntimeError: If model does not report an embedding dimension.
        """
        dim = model.get_sentence_embedding_dimension()
        if dim is None:
            msg = f"Model '{model}' did not report an embedding dimension"
            raise RuntimeError(msg)
        return dim

    @staticmethod
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


__all__ = [
    "EmbeddingsManager",
]
