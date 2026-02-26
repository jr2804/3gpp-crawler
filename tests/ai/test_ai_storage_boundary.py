"""Tests for FR-018 storage boundary behavior."""

from __future__ import annotations

from pathlib import Path

from tdoc_crawler.ai.storage import AiStorage
from tdoc_crawler.config import CacheManager


def test_ai_storage_writes_inside_ai_store_only(tmp_path: Path) -> None:
    """AI storage writes only within configured AI store path."""
    manager = CacheManager(root_path=tmp_path, name="ai-storage-boundary").register(force=True)
    ai_store = manager.root / ".ai" / "lancedb"

    storage = AiStorage(ai_store)

    assert storage is not None
    assert ai_store.exists()
    assert str(ai_store).startswith(str(manager.root))


def test_ai_storage_does_not_create_or_mutate_core_sqlite(tmp_path: Path) -> None:
    """Initializing AI storage must not create the core SQLite DB file."""
    manager = CacheManager(root_path=tmp_path, name="ai-storage-boundary-db").register(force=True)
    core_db = manager.db_file

    assert not core_db.exists()

    _ = AiStorage(manager.root / ".ai" / "lancedb")

    assert not core_db.exists()
