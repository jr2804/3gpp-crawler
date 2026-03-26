"""Unit tests for document chunking strategies."""

from __future__ import annotations

from threegpp_ai.operations.chunking import (
    ChunkingConfig,
    ChunkingStrategy,
    chunk_document,
    chunk_semantic,
    chunk_structural,
    chunk_with_overlap,
)


def _longest_token_overlap(a: list[int], b: list[int], max_overlap: int) -> int:
    """Return the longest suffix/prefix token overlap length."""
    upper = min(len(a), len(b), max_overlap)
    for size in range(upper, 0, -1):
        if a[-size:] == b[:size]:
            return size
    return 0


def test_chunk_semantic_large_section_no_unit_mixing() -> None:
    """A large section split should not depend on token->char index conversion."""
    content = "# Title\n\n## Section\n\n" + ("alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu\n" * 250)
    config = ChunkingConfig(
        strategy=ChunkingStrategy.SEMANTIC,
        max_tokens=120,
        respect_sections=False,
    )

    chunks = chunk_semantic(content, config)

    assert len(chunks) > 1
    assert all(config.count_tokens(chunk) <= config.max_tokens for chunk in chunks)
    assert any("Section" in chunk for chunk in chunks)


def test_chunk_document_semantic_strategy_splits_on_sections() -> None:
    """Semantic strategy should keep section boundaries while splitting."""
    content = "# Intro\n\n" + ("intro text " * 120) + "\n\n## Body\n\n" + ("body text " * 120) + "\n\n## End\n\n" + ("end text " * 120)
    config = ChunkingConfig(
        strategy=ChunkingStrategy.SEMANTIC,
        max_tokens=100,
        respect_sections=True,
    )

    chunks = chunk_document(content, config)

    assert len(chunks) >= 2
    assert chunks[0].startswith("# Intro")
    assert any("## Body" in chunk for chunk in chunks)


def test_chunk_with_overlap_preserves_context_between_chunks() -> None:
    """Consecutive overlap chunks should share a token overlap region."""
    content = " ".join(f"token{i:04d}" for i in range(500))
    config = ChunkingConfig(
        strategy=ChunkingStrategy.OVERLAP,
        max_tokens=80,
        overlap_tokens=20,
    )

    chunks = chunk_with_overlap(content, config)

    assert len(chunks) > 1

    encoder = config.get_encoder()
    overlaps = []
    for first, second in zip(chunks, chunks[1:], strict=False):
        a_tokens = encoder.encode(first)
        b_tokens = encoder.encode(second)
        overlaps.append(_longest_token_overlap(a_tokens, b_tokens, config.overlap_tokens))

    assert all(overlap >= 5 for overlap in overlaps)


def test_chunk_structural_preserves_equation_block() -> None:
    """Structural chunking should keep equation blocks intact as standalone chunks."""
    equation = "$$ E = mc^2 $$"
    content = "# Intro\n\n" + ("text " * 200) + "\n\n" + equation + "\n\n" + ("more text " * 200)
    config = ChunkingConfig(
        strategy=ChunkingStrategy.STRUCTURAL,
        max_tokens=80,
        respect_sections=True,
    )

    chunks = chunk_structural(content, config)

    assert any(equation in chunk for chunk in chunks)


def test_chunk_document_structural_strategy() -> None:
    """chunk_document should dispatch to structural strategy when configured."""
    marker = "<!-- table:id=table_1,page=1,rows=1,cols=2 -->"
    content = f"{('alpha ' * 120)}\n\n{marker}\n\n{('beta ' * 120)}"
    config = ChunkingConfig(
        strategy=ChunkingStrategy.STRUCTURAL,
        max_tokens=60,
    )

    chunks = chunk_document(content, config)
    assert any(marker in chunk for chunk in chunks)
