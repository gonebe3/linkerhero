from __future__ import annotations

from flask import current_app

from .providers.anthropic_provider import AnthropicProvider
from .providers.openai_provider import OpenAIProvider
from .providers import Provider


def get_provider(name: str | None = None) -> Provider:
    provider_name = (name or current_app.config.get("LLM_PROVIDER", "anthropic")).lower()
    if provider_name in {"openai", "gpt", "gpt5", "chatgpt"}:
        return OpenAIProvider()
    # default to anthropic/claude
    return AnthropicProvider()

