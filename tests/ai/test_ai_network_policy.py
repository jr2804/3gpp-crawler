"""Tests enforcing FR-012 network policy boundaries for AI modules."""

from __future__ import annotations

from pathlib import Path

AI_MODULES = [
    Path("packages/3gpp-ai/threegpp_ai/__init__.py"),
    Path("packages/3gpp-ai/threegpp_ai/config.py"),
    Path("packages/3gpp-ai/threegpp_ai/storage.py"),
    Path("packages/3gpp-ai/threegpp_ai/operations/classify.py"),
    Path("packages/3gpp-ai/threegpp_ai/operations/extract.py"),
    Path("packages/3gpp-ai/threegpp_ai/operations/embeddings.py"),
    Path("packages/3gpp-ai/threegpp_ai/operations/summarize.py"),
    Path("packages/3gpp-ai/threegpp_ai/operations/graph.py"),
    Path("packages/3gpp-ai/threegpp_ai/operations/pipeline.py"),
]

FORBIDDEN_CORE_SOURCE_REFERENCES = [
    "3gpp.org",
    "whatthespec.net",
    "portal.etsi.org",
]


def test_ai_modules_do_not_directly_target_core_crawler_sources() -> None:
    """AI modules must not include direct hardcoded core-source URLs."""
    for module_path in AI_MODULES:
        content = module_path.read_text(encoding="utf-8")
        lowered = content.lower()
        for reference in FORBIDDEN_CORE_SOURCE_REFERENCES:
            assert reference not in lowered, f"{module_path} contains forbidden source reference '{reference}'"


def test_core_source_policy_task_documents_cached_session_rule() -> None:
    """Task plan explicitly tracks create_cached_session policy enforcement."""
    tasks_path = Path("specs/002-ai-document-processing/tasks.md")
    content = tasks_path.read_text(encoding="utf-8")
    assert "create_cached_session()" in content
    assert "FR-012" in content
