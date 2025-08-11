from __future__ import annotations

from flask import current_app

from .providers.anthropic_provider import AnthropicProvider
from .providers.openai_provider import OpenAIProvider
from .providers import Provider


def get_provider() -> Provider:
    name = current_app.config.get("LLM_PROVIDER", "anthropic").lower()
    if name == "openai":
        return OpenAIProvider()
    return AnthropicProvider()

