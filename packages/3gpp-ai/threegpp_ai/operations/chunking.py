"""Document chunking strategies for large documents.

Provides semantic-aware chunking to split large documents into manageable
pieces while preserving context and section boundaries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import tiktoken
from tdoc_crawler.logging import get_logger

logger = get_logger(__name__)

# Default encoding for token counting (cl100k_base is used by GPT-4, GPT-3.5-turbo)
_DEFAULT_ENCODING = "cl100k_base"


class ChunkingStrategy(Enum):
    """Document chunking strategies."""

    TRUNCATE = "truncate"  # Simple truncation at max_tokens
    SEMANTIC = "semantic"  # Split on section boundaries (markdown headers)
    OVERLAP = "overlap"  # Overlapping chunks with context window
    STRUCTURAL = "structural"  # Preserve protected structural blocks


@dataclass
class ChunkingConfig:
    """Configuration for document chunking.

    Attributes:
        strategy: Chunking strategy to use.
        max_tokens: Maximum tokens per chunk.
        overlap_tokens: Number of overlapping tokens between chunks (for overlap strategy).
        respect_sections: Whether to avoid splitting within sections (for semantic strategy).
        encoding: Tiktoken encoding name for token counting.
    """

    strategy: ChunkingStrategy = ChunkingStrategy.TRUNCATE
    max_tokens: int = 100_000
    overlap_tokens: int = 500
    respect_sections: bool = True
    encoding: str = field(default=_DEFAULT_ENCODING, repr=False)

    _encoder: tiktoken.Encoding | None = field(default=None, repr=False, compare=False)

    def get_encoder(self) -> tiktoken.Encoding:
        """Get or create the tiktoken encoder."""
        if self._encoder is None:
            self._encoder = tiktoken.get_encoding(self.encoding)
        return self._encoder

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using the configured encoding."""
        return len(self.get_encoder().encode(text))


def _find_section_boundaries(content: str) -> list[int]:
    """Find positions of markdown section boundaries.

    Identifies positions after:
    - Markdown headers (# , ##, ###, etc.)
    - Horizontal rules (---, ***)
    - Double newlines (paragraph breaks)

    Args:
        content: Markdown content to analyze.

    Returns:
        List of character positions suitable for splitting.
    """
    boundaries: list[int] = []

    # Pattern for markdown headers (## Header, ### Header, etc.)
    header_pattern = re.compile(r"^(#{1,6})\s+.+$", re.MULTILINE)

    # Pattern for horizontal rules
    hr_pattern = re.compile(r"^(?:---|\*\*\*|___)\s*$", re.MULTILINE)

    # Find all header positions (split BEFORE headers)
    for match in header_pattern.finditer(content):
        boundaries.append(match.start())

    # Find horizontal rule positions
    for match in hr_pattern.finditer(content):
        boundaries.append(match.end())

    # Find double newline positions (paragraph breaks)
    # Only add if not too close to existing boundaries
    para_pattern = re.compile(r"\n\n+")
    for match in para_pattern.finditer(content):
        pos = match.start()
        # Only add if not within 100 chars of existing boundary
        if not any(abs(pos - b) < 100 for b in boundaries):
            boundaries.append(pos)

    # Sort and deduplicate
    boundaries = sorted(set(boundaries))
    return boundaries


def chunk_by_tokens(content: str, max_tokens: int, config: ChunkingConfig | None = None) -> list[str]:
    """Split content by token count.

    Simple token-based splitting without semantic awareness.
    Splits at the last space before max_tokens to avoid mid-word splits.

    Args:
        content: Text content to chunk.
        max_tokens: Maximum tokens per chunk.
        config: Optional chunking config (uses defaults if not provided).

    Returns:
        List of text chunks, each under max_tokens.
    """
    if config is None:
        config = ChunkingConfig()

    encoder = config.get_encoder()
    tokens = encoder.encode(content)

    if len(tokens) <= max_tokens:
        return [content]

    chunks: list[str] = []
    start = 0

    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = encoder.decode(chunk_tokens)

        # Try to find a good break point (last space/newline)
        if end < len(tokens):
            # Look for last space or newline in decoded text
            last_space = max(chunk_text.rfind(" "), chunk_text.rfind("\n"))
            if last_space > len(chunk_text) // 2:
                # Re-encode up to the break point
                chunk_text = chunk_text[: last_space + 1]
                # Adjust token count for next iteration
                actual_tokens = encoder.encode(chunk_text)
                end = start + len(actual_tokens)

        chunks.append(chunk_text.strip())
        start = end

    return chunks


def chunk_semantic(content: str, config: ChunkingConfig) -> list[str]:
    """Split content on semantic boundaries (section headers, etc.).

    Respects markdown structure to keep related content together.
    Falls back to token-based splitting for sections exceeding max_tokens.

    Args:
        content: Markdown content to chunk.
        config: Chunking configuration.

    Returns:
        List of semantically coherent chunks.
    """
    encoder = config.get_encoder()
    tokens = encoder.encode(content)

    if len(tokens) <= config.max_tokens:
        return [content]

    # Find section boundaries
    boundaries = _find_section_boundaries(content)
    boundaries = [0] + boundaries + [len(content)]

    chunks: list[str] = []
    current_chunk_start = 0
    current_chunk_end = 0

    for i in range(len(boundaries) - 1):
        section_start = boundaries[i]
        section_end = boundaries[i + 1]
        section_text = content[section_start:section_end]
        section_tokens = len(encoder.encode(section_text))

        # Check if adding this section would exceed max_tokens
        potential_chunk = content[current_chunk_start:section_end]
        potential_tokens = len(encoder.encode(potential_chunk))

        if potential_tokens <= config.max_tokens:
            # Include this section in current chunk
            current_chunk_end = section_end
        else:
            # Current chunk is full, save it
            if current_chunk_start < current_chunk_end:
                chunk_text = content[current_chunk_start:current_chunk_end].strip()
                if chunk_text:
                    chunks.append(chunk_text)

            # Start new chunk with this section
            current_chunk_start = section_start
            current_chunk_end = section_end

            # If single section exceeds max_tokens, use token-based splitting
            if section_tokens > config.max_tokens and not config.respect_sections:
                sub_chunks = chunk_by_tokens(section_text, config.max_tokens, config)
                chunks.extend(sub_chunks)
                # This section is fully consumed by token-based sub-chunks.
                # Continue chunking from the next section boundary.
                current_chunk_start = section_end
                current_chunk_end = section_end

    # Add final chunk
    if current_chunk_start < len(content):
        final_chunk = content[current_chunk_start:].strip()
        if final_chunk:
            chunks.append(final_chunk)

    return chunks if chunks else [content]


def chunk_with_overlap(content: str, config: ChunkingConfig) -> list[str]:
    """Split content with overlapping windows for context preservation.

    Each chunk overlaps with the previous one by overlap_tokens to maintain
    context across chunk boundaries.

    Args:
        content: Text content to chunk.
        config: Chunking configuration (uses overlap_tokens for overlap size).

    Returns:
        List of overlapping text chunks.
    """
    encoder = config.get_encoder()
    tokens = encoder.encode(content)

    if len(tokens) <= config.max_tokens:
        return [content]

    chunks: list[str] = []
    start = 0
    step = config.max_tokens - config.overlap_tokens

    # Ensure step is positive
    if step <= 0:
        step = config.max_tokens // 2

    while start < len(tokens):
        end = min(start + config.max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = encoder.decode(chunk_tokens)

        if chunk_text.strip():
            chunks.append(chunk_text)

        if end >= len(tokens):
            break

        start += step

    return chunks


def chunk_structural(content: str, config: ChunkingConfig) -> list[str]:
    """Split content while preserving protected structural blocks.

    Protected blocks include equation notations and structural comment markers
    for tables/figures/equations generated by extraction.
    """
    protected_pattern = re.compile(
        r"(\$\$.*?\$\$|\\\[.*?\\\]|\\begin\{equation\}.*?\\end\{equation\}|<!--\s*(?:table|figure|equation):.*?-->)",
        re.DOTALL,
    )

    parts = protected_pattern.split(content)
    if len(parts) == 1:
        return chunk_semantic(content, config)

    chunks: list[str] = []
    current = ""

    def _flush_current() -> None:
        nonlocal current
        current = current.strip()
        if current:
            chunks.extend(chunk_semantic(current, config))
        current = ""

    for part in parts:
        if not part or not part.strip():
            continue

        is_protected = protected_pattern.fullmatch(part.strip()) is not None
        if is_protected:
            _flush_current()
            chunks.append(part.strip())
            continue

        candidate = f"{current}\n{part}" if current else part
        if config.count_tokens(candidate) > config.max_tokens and current.strip():
            _flush_current()
            current = part
        else:
            current = candidate

    _flush_current()
    return chunks


def chunk_document(content: str, config: ChunkingConfig | None = None) -> list[str]:
    """Chunk a document using the configured strategy.

    Main entry point for document chunking. Selects the appropriate
    chunking algorithm based on the strategy in config.

    Args:
        content: Document text content (typically markdown).
        config: Chunking configuration. Uses defaults if not provided.

    Returns:
        List of document chunks.

    Raises:
        ValueError: If an unknown chunking strategy is specified.
    """
    if config is None:
        config = ChunkingConfig()

    if not content or not content.strip():
        return []

    strategy = config.strategy

    if strategy == ChunkingStrategy.TRUNCATE:
        result = chunk_by_tokens(content, config.max_tokens, config)
    elif strategy == ChunkingStrategy.SEMANTIC:
        result = chunk_semantic(content, config)
    elif strategy == ChunkingStrategy.OVERLAP:
        result = chunk_with_overlap(content, config)
    elif strategy == ChunkingStrategy.STRUCTURAL:
        result = chunk_structural(content, config)
    else:
        msg = f"Unknown chunking strategy: {strategy}"
        raise ValueError(msg)

    logger.debug(f"Chunked document using {strategy.value} strategy: {len(result)} chunks, avg {sum(len(c) for c in result) // max(len(result), 1)} chars")

    return result


def chunk_hybrid(dl_doc: Any, *, max_tokens: int = 100_000) -> list[str]:
    """Chunk a docling document using HybridChunker for semantic boundaries.

    HybridChunker preserves document structure (headings, paragraphs, tables, figures)
    and creates chunks with proper semantic boundaries. This replaces the older
    regex-based chunking strategies.

    Args:
        dl_doc: A docling DoclingDocument (result.document from ConvertResult).
        max_tokens: Maximum tokens per chunk.

    Returns:
        List of text chunks.
    """
    from docling.chunking import HybridChunker

    chunker = HybridChunker(max_tokens=max_tokens)
    chunks: list[str] = []
    for chunk in chunker.chunk(dl_doc):
        text = getattr(chunk, "text", "") if hasattr(chunk, "text") else str(chunk)
        if text:
            chunks.append(text)
    return chunks
    chunks: list[str] = []
    for chunk in chunker.chunk(dl_doc):
        text = getattr(chunk, "text", "") if hasattr(chunk, "text") else str(chunk)
        if text:
            chunks.append(text)
    return chunks


__all__ = [
    "ChunkingConfig",
    "ChunkingStrategy",
    "chunk_by_tokens",
    "chunk_document",
    "chunk_hybrid",
    "chunk_semantic",
    "chunk_structural",
    "chunk_with_overlap",
]
