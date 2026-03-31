"""Generic LiteLLM client wrapper."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

import litellm
from tdoc_crawler.logging import get_logger

from threegpp_ai.config import AiConfig

logger = get_logger(__name__)

# Default system prompt for technical document analysis
DEFAULT_SYSTEM_PROMPT = """You are a technical document analyzer specializing in 3GPP TDoc documents.
Generate concise, informative summaries following the specified structure."""


class LiteLLMClient:
    """Client for LiteLLM API."""

    _instance: LiteLLMClient | None = None

    def __new__(cls) -> LiteLLMClient:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the singleton instance."""
        pass

    @staticmethod
    def complete(
        prompt: str,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_tokens: int = 256000,
        model: str | None = None,
        images: list[Path] | None = None,
    ) -> str:
        """Generate completion from prompt.

        Args:
            prompt: User prompt.
            system_prompt: System prompt.
            max_tokens: Maximum tokens in response.
            model: Model identifier (e.g., 'openai/gpt-4o-mini'). Defaults to config.llm_model.
            images: Optional list of image paths for vision-capable models.

        Returns:
            Generated text.
        """
        cfg = AiConfig()
        if cfg.llm_api_base is not None and cfg.llm_api_key is None:
            msg = f"LLM API base URL is set ({cfg.llm_api_base}) but API key is missing. Please set TDC_AI_LLM_API_KEY environment variable."
            logger.warning(msg)

        try:
            user_content: str | list[dict[str, str]]
            if images:
                user_content = [{"type": "text", "text": prompt}]
                for image_path in images:
                    mime_type, _ = mimetypes.guess_type(str(image_path))
                    mime_type = mime_type or "image/png"
                    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
                    user_content.append(
                        {
                            "type": "image_url",
                            "image_url": f"data:{mime_type};base64,{encoded}",
                        }
                    )
            else:
                user_content = prompt

            response = litellm.completion(
                model=model or cfg.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=max_tokens,
                api_key=cfg.llm_api_key,
                base_url=cfg.llm_api_base,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM completion failed: {e}")
            raise
