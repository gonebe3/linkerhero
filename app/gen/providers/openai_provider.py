from __future__ import annotations

from typing import List
import re

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
        hook_type: str | None = None,
        language: str | None = None,
    ) -> List[str]:
        if not self.client:
            base = source_text.split("\n")[0][:140]
            return [f"{persona} {tone}: {base} #draft" for _ in range(n_variants)]

        hook_clause = f" Hook style: {hook_type}." if hook_type and hook_type != "auto" else ""
        system = (
            "You write concise, topic-grounded LinkedIn posts. Start with a strong hook. 2–4 short paragraphs. "
            f"Persona: {persona}. Tone: {tone}. Include keywords: {', '.join(keywords or [])}. "
            "Keep paragraphs under 60 words."
            + hook_clause
            + " Output only the post text. Do not include prefaces or headings."
            + " Always write in the same language as the Source text (do not translate)."
            + " CRITICAL: Base the post ONLY on the content in 'Source' below. Do NOT give generic LinkedIn tips or advice unless the Source is about LinkedIn itself."
        )
        lang_clause = f" Write the post in {language}." if language else ""
        user = (
            f"Craft {n_variants} LinkedIn-style post(s). "
            "Start with a strong hook, then 2–4 short paragraphs (<=60 words each). "
            "Conclude with a light CTA or reflection if appropriate. "
            "Use concrete details from the Source (names, numbers, facts). If the Source is a list/table, synthesize the key points. "
            "If the Source lacks enough content to write a post about the same topic, respond exactly with 'INSUFFICIENT_SOURCE'.\n\n"
            f"Source:\n{source_text[:3000]}"
            + lang_clause
        )
        chat = self.client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
        )
        text = chat.choices[0].message.content or ""
        def _clean(s: str) -> str:
            s = s.strip()
            s = re.sub(r"^(here\s*(is|are|\'s)).*?:\s*\n?", "", s, flags=re.I)
            return s.strip()
        if n_variants == 1:
            return [_clean(text)] if text.strip() else [""]
        variants = [_clean(v.strip("- \n")) for v in text.split("\n\n") if v.strip()]
        return variants[:n_variants] if variants else [text.strip()][:n_variants]

    # New: extract grounded facts
    def extract_facts(self, *, source_text: str, language: str | None = None, max_facts: int = 12) -> List[str]:
        if not self.client:
            sentences = [s.strip() for s in re.split(r"[\.!?\n]+", source_text) if s.strip()]
            return sentences[:max_facts]
        system = (
            "Extract key facts as short bullet points from the Source. Do NOT invent new information. "
            "Return each fact as a single line. Always write in the same language as the Source."
        )
        user = (
            f"Source:\n{source_text[:3000]}\n\n"
            f"Return up to {max_facts} facts, one per line."
        )
        chat = self.client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=400,
        )
        text = chat.choices[0].message.content or ""
        facts = [ln.strip("- • \t ") for ln in text.split("\n") if ln.strip()]
        return [f for f in facts if len(f) > 3][:max_facts]

    # New: write post from facts
    def write_post_from_facts(
        self,
        *,
        facts: List[str],
        persona: str,
        tone: str,
        hook_type: str | None = None,
        language: str | None = None,
        max_tokens: int = 600,
    ) -> str:
        if not self.client:
            base = " ".join(facts)[:400]
            return f"{base}"
        hook_clause = f" Hook style: {hook_type}." if hook_type and hook_type != "auto" else ""
        system = (
            "You write concise, topic-grounded LinkedIn posts. Start with a strong hook. 2–4 short paragraphs. "
            f"Persona: {persona}. Tone: {tone}. Keep paragraphs under 60 words."
            + hook_clause
            + " Output only the post text. Do not include headings."
            + " Always write in the language of the Facts."
        )
        facts_text = "\n- " + "\n- ".join(facts[:20])
        user = (
            "Using ONLY these facts, write a short LinkedIn-style post that clearly reflects them.\n"
            f"Facts:{facts_text}"
        )
        chat = self.client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
        )
        return (chat.choices[0].message.content or "").strip()

