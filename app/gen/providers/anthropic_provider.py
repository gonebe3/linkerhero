from __future__ import annotations

from typing import List

from flask import current_app
from anthropic import Anthropic


class AnthropicProvider:
    def __init__(self) -> None:
        api_key = current_app.config.get("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=api_key) if api_key else None

    def generate_post_variants(
        self,
        *,
        source_text: str,
        persona: str,
        tone: str,
        n_variants: int = 3,
        max_tokens: int = 400,
        keywords: list[str] | None = None,
        hook_type: str | None = None,
    ) -> List[str]:
        if not self.client:
            base = source_text.split("\n")[0][:140]
            return [f"{persona} {tone}: {base} #draft" for _ in range(n_variants)]

        hook_clause = f" Hook style: {hook_type}." if hook_type and hook_type != "auto" else ""
        system = (
            "You create concise LinkedIn posts. Start with a strong hook. 2-4 short paragraphs. "
            f"Persona: {persona}. Tone: {tone}. Include keywords: {', '.join(keywords or [])}. "
            "Keep paragraphs under 60 words." + hook_clause
        )
        prompt = f"Summarize and craft {n_variants} LinkedIn-style post variants from: \n{source_text[:2000]}"
        resp = self.client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join([c.text for c in resp.content if getattr(c, "text", None)])
        variants = [v.strip("- \n") for v in text.split("\n\n") if v.strip()]
        return variants[:n_variants] if variants else [text.strip()][:n_variants]

