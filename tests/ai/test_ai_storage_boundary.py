"""Tests for FR-018 storage boundary behavior."""

from __future__ import annotations

from pathlib import Path

from tdoc_ai.storage import AiStorage

from tdoc_crawler.config import CacheManager


def test_ai_storage_writes_inside_ai_store_only(tmp_path: Path) -> None:
    """AI storage writes only within configured AI store path."""
    manager = CacheManager(root_path=tmp_path, name="ai-storage-boundary").register(force=True)
    ai_store = manager.root / ".ai" / "lancedb"

    # Default embedding dimension for sentence-transformers/all-MiniLM-L6-v2
    storage = AiStorage(ai_store, embedding_dimension=384)

    assert storage is not None
    assert ai_store.exists()
    assert str(ai_store).startswith(str(manager.root))


def test_ai_storage_does_not_create_or_mutate_core_sqlite(tmp_path: Path) -> None:
    """Initializing AI storage must not create the core SQLite DB file."""
    manager = CacheManager(root_path=tmp_path, name="ai-storage-boundary-db").register(force=True)
    core_db = manager.db_file

    assert not core_db.exists()

    # Default embedding dimension for sentence-transformers/all-MiniLM-L6-v2
    _ = AiStorage(manager.root / ".ai" / "lancedb", embedding_dimension=384)

    assert not core_db.exists()
