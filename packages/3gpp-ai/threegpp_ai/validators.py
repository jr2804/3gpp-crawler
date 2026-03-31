"""Validators for AI provider and model configuration."""

from __future__ import annotations

import litellm


def validate_llm_provider(model: str) -> str:
    """Validate LLM provider at operation time (not config time).

    Called before making requests to ensure the provider is supported by litellm.
    Keeps litellm dependency out of base config models.

    Args:
        model: Model identifier in <provider>/<model_name> format

    Returns:
        Normalized <provider>/<model_name> string

    Raises:
        ValueError: If provider is not supported or format is invalid
    """
    if "/" not in model:
        msg = f"model '{model}' must be in '<provider>/<model_name>' format"
        raise ValueError(msg)

    provider, model_name = model.split("/", 1)
    provider_normalized = provider.strip().lower()
    model_name_normalized = model_name.strip()

    if not provider_normalized:
        msg = "model provider segment cannot be empty"
        raise ValueError(msg)
    if not model_name_normalized:
        msg = "model_name segment cannot be empty"
        raise ValueError(msg)

    supported_providers = set(litellm.LITELLM_CHAT_PROVIDERS + litellm.openai_compatible_providers)

    if provider_normalized not in supported_providers:
        msg = (
            f"provider '{provider}' is not supported by litellm. "
            f"See https://docs.litellm.ai/docs/providers for the full list of {len(supported_providers)} supported providers."
        )
        raise ValueError(msg)

    return f"{provider_normalized}/{model_name_normalized}"
