"""Figure description helpers for extracted document images."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def describe_figures(
    figure_paths: dict[str, Path],
    *,
    enabled: bool = True,
    captions: dict[str, str] | None = None,
    model: str | None = None,
) -> dict[str, str]:
    """Generate figure descriptions using the existing LiteLLM client path.

    Args:
        figure_paths: Mapping from figure ids to image paths.
        enabled: Whether description generation is enabled.
        captions: Optional caption hints keyed by figure id.
        model: Optional model override.

    Returns:
        Mapping of figure ids to generated descriptions.
    """
    if not enabled or not figure_paths:
        return {}

    descriptions: dict[str, str] = {}
    for figure_id, image_path in figure_paths.items():
        description = _describe_figure(
            image_path,
            caption=(captions or {}).get(figure_id),
            model=model,
        )
        if description:
            descriptions[figure_id] = description

    return descriptions


def _describe_figure(image_path: Path, *, caption: str | None = None, model: str | None = None) -> str | None:
    """Describe a single figure image using the summarize LiteLLM client."""
    try:
        from threegpp_ai.operations.summarize import LiteLLMClient

        prompt = "Describe this technical figure in 2-3 concise sentences."
        if caption:
            prompt = f"{prompt} Caption hint: {caption}"

        result = LiteLLMClient.complete(
            prompt=prompt,
            images=[image_path],
            model=model,
            max_tokens=600,
        )
        cleaned = (result or "").strip()
        return cleaned if cleaned else None
    except Exception as exc:
        logger.info("Skipping figure description for %s: %s", image_path, exc)
        return None


__all__ = ["describe_figures"]
