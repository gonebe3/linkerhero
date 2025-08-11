from __future__ import annotations

from typing import List

from flask import current_app
from openai import OpenAI


class OpenAIProvider:
    def __init__(self) -> None:
        api_key = current_app.config.get("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else None

    def generate_post_variants(
        self,
        *,
        source_text: str,
        persona: str,
        tone: str,
        n_variants: int = 3,
        max_tokens: int = 400,
        keywords: list[str] | None = None,
    ) -> List[str]:
        if not self.client:
            base = source_text.split("\n")[0][:140]
            return [f"{persona} {tone}: {base} #draft" for _ in range(n_variants)]

        system = (
            "You create concise LinkedIn posts. Start with a hook. 2-4 short paragraphs. "
            f"Persona: {persona}. Tone: {tone}. Include keywords: {', '.join(keywords or [])}. "
            "Keep paragraphs under 60 words."
        )
        user = f"Craft {n_variants} variants from: \n{source_text[:2000]}"
        chat = self.client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
        )
        text = chat.choices[0].message.content or ""
        variants = [v.strip("- \n") for v in text.split("\n\n") if v.strip()]
        return variants[:n_variants] if variants else [text.strip()][:n_variants]

