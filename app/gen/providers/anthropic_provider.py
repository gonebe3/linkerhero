from __future__ import annotations

from typing import List
import re

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
        goal: str | None = None,
        length: str | None = None,
        ending: str | None = None,
        emoji: str | None = None,
        user_prompt: str | None = None,
        language: str | None = None,
    ) -> List[str]:
        if not self.client:
            base = source_text.split("\n")[0][:140]
            return [f"{persona} {tone}: {base} #draft" for _ in range(n_variants)]

        def humanize(v: str | None) -> str:
            if not v:
                return ""
            return v.replace("_", " ").replace("-", " ").strip()

        hook_clause = f" Hook type: {humanize(hook_type)}." if hook_type and hook_type != "auto" else " Hook type: Auto (infer best)."
        persona_clause = f" Persona: {humanize(persona)}." if persona and persona != "auto" else " Persona: Auto (infer best)."
        tone_clause = f" Tone: {humanize(tone)}." if tone and tone != "auto" else " Tone: Auto (infer best)."
        goal_clause = f" Goal: {humanize(goal)}." if goal and goal != "auto" else " Goal: Auto (infer best)."

        if (emoji or "").lower() == "yes":
            emoji_clause = " Emoji: Allowed but sparse (0–3 max). No emoji spam."
        else:
            emoji_clause = " Emoji: Do not use emojis."

        length_clause = ""
        if length == "short":
            length_clause = " Length: Short (1–2 short paragraphs, ~80–140 words)."
        elif length == "medium":
            length_clause = " Length: Medium (2–4 short paragraphs, ~150–260 words)."
        elif length == "long":
            length_clause = " Length: Long (4–6 short paragraphs, ~280–420 words)."
        else:
            length_clause = " Length: Auto (pick the best length)."

        ending_clause = ""
        if ending == "mic-drop":
            ending_clause = " Ending: Mic Drop (end with a strong statement; no question)."
        elif ending == "discussion":
            ending_clause = " Ending: Discussion (end with a thought-provoking open question)."
        elif ending == "the-hand-raiser":
            ending_clause = " Ending: The Hand-Raiser (ask readers to comment 'GUIDE' to get a resource)."
        elif ending == "the-pitch":
            ending_clause = " Ending: The Pitch (invite qualified leads to DM you or book a call)."
        elif ending == "profile-funnel":
            ending_clause = " Ending: Profile Funnel (ask readers to visit your profile and follow for more)."
        else:
            ending_clause = " Ending: Auto (choose the best ending style for the goal)."

        language_clause = f" Write the post in {language}." if language else " Write in the same language as the Source."
        user_prompt_clause = (
            f" Additional user instructions: {user_prompt.strip()}."
            if user_prompt and user_prompt.strip()
            else ""
        )
        system = (
            "You write concise, topic-grounded LinkedIn posts. Start with a strong hook. 2–4 short paragraphs. "
            + persona_clause
            + tone_clause
            + goal_clause
            + length_clause
            + ending_clause
            + emoji_clause
            + user_prompt_clause
            + f" Include keywords: {', '.join(keywords or [])}. "
            + " Keep paragraphs under 60 words."
            + hook_clause
            + " Output only the post text. Do not include any prefaces like 'Here is' or headings."
            + language_clause
            + " CRITICAL: Base the post ONLY on the content in 'Source' below. Do NOT give generic LinkedIn tips or advice unless the Source is about LinkedIn itself."
        )
        lang_clause = ""  # already in system
        prompt = (
            f"Craft {n_variants} LinkedIn-style post(s) from the source below. "
            "Start with a strong hook, then 2–4 short paragraphs (<=60 words each). "
            "Conclude with a light CTA or reflection if appropriate. "
            "Use concrete details from the Source (names, numbers, facts). If the Source is a list/table, synthesize the key points. "
            "If the Source lacks enough content to write a post about the same topic, respond exactly with 'INSUFFICIENT_SOURCE'.\n\n"
            f"Source:\n{source_text[:3000]}"
            + lang_clause
        )
        resp = self.client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join([c.text for c in resp.content if getattr(c, "text", None)])
        # Sanitize away generic prefaces
        def _clean(s: str) -> str:
            s = s.strip()
            s = re.sub(r"^(here\s*(is|are|\'s)).*?:\s*\n?", "", s, flags=re.I)
            return s.strip()

        if n_variants == 1:
            return [_clean(text)] if text.strip() else [""]

        chunks = [v for v in text.split("\n\n") if v.strip()]
        variants = [_clean(v.strip("- \n")) for v in chunks]
        return variants[:n_variants] if variants else [text.strip()][:n_variants]

    # New: extract grounded facts as JSON list
    def extract_facts(self, *, source_text: str, language: str | None = None, max_facts: int = 12) -> List[str]:
        if not self.client:
            # Fallback: naive sentence split
            sentences = [s.strip() for s in re.split(r"[\.!?\n]+", source_text) if s.strip()]
            return sentences[:max_facts]
        system = (
            "Extract key facts as short bullet points from the Source. "
            "Do NOT invent new information. Return each fact as a single line. "
            "Write in the same language as the Source."
        )
        prompt = f"Source:\n{source_text[:3000]}\n\nReturn up to {max_facts} facts, one per line."
        resp = self.client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=600,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join([c.text for c in resp.content if getattr(c, "text", None)])
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
        goal: str | None = None,
        length: str | None = None,
        ending: str | None = None,
        emoji: str | None = None,
        user_prompt: str | None = None,
        language: str | None = None,
        max_tokens: int = 600,
    ) -> str:
        if not self.client:
            base = " ".join(facts)[:400]
            return f"{base}"
        def humanize(v: str | None) -> str:
            if not v:
                return ""
            return v.replace("_", " ").replace("-", " ").strip()

        hook_clause = f" Hook type: {humanize(hook_type)}." if hook_type and hook_type != "auto" else " Hook type: Auto (infer best)."
        persona_clause = f" Persona: {humanize(persona)}." if persona and persona != "auto" else " Persona: Auto (infer best)."
        tone_clause = f" Tone: {humanize(tone)}." if tone and tone != "auto" else " Tone: Auto (infer best)."
        goal_clause = f" Goal: {humanize(goal)}." if goal and goal != "auto" else " Goal: Auto (infer best)."
        if (emoji or "").lower() == "yes":
            emoji_clause = " Emoji: Allowed but sparse (0–3 max). No emoji spam."
        else:
            emoji_clause = " Emoji: Do not use emojis."
        length_clause = ""
        if length == "short":
            length_clause = " Length: Short (1–2 short paragraphs, ~80–140 words)."
        elif length == "medium":
            length_clause = " Length: Medium (2–4 short paragraphs, ~150–260 words)."
        elif length == "long":
            length_clause = " Length: Long (4–6 short paragraphs, ~280–420 words)."
        else:
            length_clause = " Length: Auto (pick the best length)."
        ending_clause = ""
        if ending == "mic-drop":
            ending_clause = " Ending: Mic Drop (end with a strong statement; no question)."
        elif ending == "discussion":
            ending_clause = " Ending: Discussion (end with a thought-provoking open question)."
        elif ending == "the-hand-raiser":
            ending_clause = " Ending: The Hand-Raiser (ask readers to comment 'GUIDE' to get a resource)."
        elif ending == "the-pitch":
            ending_clause = " Ending: The Pitch (invite qualified leads to DM you or book a call)."
        elif ending == "profile-funnel":
            ending_clause = " Ending: Profile Funnel (ask readers to visit your profile and follow for more)."
        else:
            ending_clause = " Ending: Auto (choose the best ending style for the goal)."
        language_clause = f" Write the post in {language}." if language else " Write in the language of the Facts."
        user_prompt_clause = (
            f" Additional user instructions: {user_prompt.strip()}."
            if user_prompt and user_prompt.strip()
            else ""
        )
        system = (
            "You write concise, topic-grounded LinkedIn posts. Start with a strong hook. 2–4 short paragraphs. "
            + persona_clause
            + tone_clause
            + goal_clause
            + length_clause
            + ending_clause
            + emoji_clause
            + " Keep paragraphs under 60 words."
            + hook_clause
            + " Output only the post text. Do not include headings."
            + language_clause
            + user_prompt_clause
        )
        facts_text = "\n- " + "\n- ".join(facts[:20])
        prompt = (
            "Using ONLY these facts, write a short LinkedIn-style post that clearly reflects them.\n"
            f"Facts:{facts_text}"
        )
        resp = self.client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join([c.text for c in resp.content if getattr(c, "text", None)])
        return text.strip()

