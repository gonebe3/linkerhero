from __future__ import annotations

from typing import Protocol


class Provider(Protocol):
    def generate_post_variants(
        self,
        *,
        source_text: str,
        persona: str,
        tone: str,
        n_variants: int = 3,
        max_tokens: int = 400,
        keywords: list[str] | None = None,
    ) -> list[str]:
        ...

