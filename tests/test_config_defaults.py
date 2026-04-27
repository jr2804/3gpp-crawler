"""Tests to verify configuration defaults alignment.

These tests ensure that .env.example documentation is consistent
and matches what the code actually uses.
"""

from __future__ import annotations

import re
from pathlib import Path


def test_embedding_model_env_comment_matches_value() -> None:
    """Verify .env.example TDC_AI_EMBEDDING_MODEL comment and value are consistent.

    The comment recommends a model, but if the actual value differs,
    users get confusing instructions about which model to use.
    """
    env_example = Path(".env.example").read_text()

    # Find the embedding model line and its preceding comment
    embed_section = re.search(
        r"# Embedding model[^\n]*\n"
        r"(?:# [^\n]*\n)?"  # Optional recommended line
        r"TDC_AI_EMBEDDING_MODEL=(\S+)",
        env_example,
        re.MULTILINE,
    )
    assert embed_section, "TDC_AI_EMBEDDING_MODEL not found in .env.example"

    value = embed_section.group(1)

    # If there's a recommended line, extract it and check consistency
    recommended_match = re.search(r"# Recommended: ([^\n]+)", embed_section.group(0))
    if recommended_match:
        recommended = recommended_match.group(1)
        # Extract model name from "provider/model:tag" format
        recommended_model = re.search(r"(\S+/\S+:?\S*)", recommended)
        if recommended_model:
            assert value == recommended_model.group(1), (
                f".env.example embedding model comment ({recommended_model.group(1)}) differs from value ({value}). Update comment to match value."
            )
