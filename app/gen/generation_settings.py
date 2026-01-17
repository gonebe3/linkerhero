from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Sequence


CategoryId = Literal["hook_type", "persona", "tone", "goal", "length", "ending"]


@dataclass(frozen=True)
class GenerationOption:
    id: str
    name: str
    description: str
    image_filename: str


@dataclass(frozen=True)
class GenerationCategory:
    id: CategoryId
    name: str
    slug: str
    options: Sequence[GenerationOption]


def _img(category_slug: str, option_id: str) -> str:
    # Stored under: app/static/assets/categories/<category-slug>/<option-id>.webp
    return f"assets/categories/{category_slug}/{option_id}.webp"


GENERATION_CATEGORIES: List[GenerationCategory] = [
    GenerationCategory(
        id="hook_type",
        name="Hook Type",
        slug="hook-type",
        options=[
            GenerationOption(
                id="auto",
                name="Auto",
                description="Analyzes your topic to select the most effective hook automatically.",
                image_filename=_img("hook-type", "auto"),
            ),
            GenerationOption(
                id="the-hot-take",
                name="The Hot Take",
                description="State a bold, controversial opinion that challenges the status quo.",
                image_filename=_img("hook-type", "the-hot-take"),
            ),
            GenerationOption(
                id="hard-lesson",
                name="Hard Lesson",
                description="Share a significant mistake you made and the lesson learned.",
                image_filename=_img("hook-type", "hard-lesson"),
            ),
            GenerationOption(
                id="the-blueprint-how-to",
                name="The Blueprint (How-To)",
                description="Provide a clear, actionable step-by-step guide to solve a problem.",
                image_filename=_img("hook-type", "the-blueprint-how-to"),
            ),
            GenerationOption(
                id="zero-to-hero-transformation",
                name="Zero to Hero (Transformation)",
                description="Tell a powerful story of transformation from struggle to success.",
                image_filename=_img("hook-type", "zero-to-hero-transformation"),
            ),
            GenerationOption(
                id="cheat-sheet-listicle",
                name="Cheat Sheet (Listicle)",
                description="Share a concise list of tools, tips, or resources for quick wins.",
                image_filename=_img("hook-type", "cheat-sheet-listicle"),
            ),
            GenerationOption(
                id="the-call-out-direct-audience",
                name="The Call-Out (Direct Audience)",
                description="Target a specific job title or audience to grab their immediate attention.",
                image_filename=_img("hook-type", "the-call-out-direct-audience"),
            ),
            GenerationOption(
                id="shock-stat-statistic",
                name="Shock Stat (Statistic)",
                description="Start with a surprising fact or number to establish immediate authority.",
                image_filename=_img("hook-type", "shock-stat-statistic"),
            ),
        ],
    ),
    GenerationCategory(
        id="persona",
        name="Persona",
        slug="persona",
        options=[
            GenerationOption(
                id="auto",
                name="Auto",
                description="Analyzes your topic to select the best persona automatically.",
                image_filename=_img("persona", "auto"),
            ),
            GenerationOption(
                id="the-founder",
                name="The Founder",
                description="Share strategic insights and high-level lessons from building a business.",
                image_filename=_img("persona", "the-founder"),
            ),
            GenerationOption(
                id="the-expert",
                name="The Expert",
                description="Teach deep tactical advice and frameworks with absolute authority.",
                image_filename=_img("persona", "the-expert"),
            ),
            GenerationOption(
                id="the-storyteller",
                name="The Storyteller",
                description="Vulnerable, human, & relatable. Focus on personal journey, vulnerability, and human connection.",
                image_filename=_img("persona", "the-storyteller"),
            ),
            GenerationOption(
                id="the-disruptor",
                name="The Disruptor",
                description="Challenge industry norms with bold, polarizing, and sharp opinions.",
                image_filename=_img("persona", "the-disruptor"),
            ),
            GenerationOption(
                id="the-executive",
                name="The Executive",
                description="Use a polished, diplomatic tone suitable for corporate leadership.",
                image_filename=_img("persona", "the-executive"),
            ),
            GenerationOption(
                id="the-growth-hacker",
                name="The Growth Hacker",
                description="Drive action with persuasive, high-energy, and results-oriented language.",
                image_filename=_img("persona", "the-growth-hacker"),
            ),
        ],
    ),
    GenerationCategory(
        id="tone",
        name="Tone",
        slug="tone",
        options=[
            GenerationOption(
                id="auto",
                name="Auto",
                description="Analyzes your topic to select the most appropriate tone automatically.",
                image_filename=_img("tone", "auto"),
            ),
            GenerationOption(
                id="professional",
                name="Professional",
                description="Keep it safe, formal, and respectful, suitable for corporate environments.",
                image_filename=_img("tone", "professional"),
            ),
            GenerationOption(
                id="empathetic",
                name="Empathetic",
                description="Focus on understanding feelings, support, and emotional connection.",
                image_filename=_img("tone", "empathetic"),
            ),
            GenerationOption(
                id="direct",
                name="Direct",
                description="Get straight to the point with concise, confident, and no-nonsense language.",
                image_filename=_img("tone", "direct"),
            ),
            GenerationOption(
                id="witty",
                name="Witty",
                description="Add a touch of humor, cleverness, or sarcasm to entertain the reader.",
                image_filename=_img("tone", "witty"),
            ),
            GenerationOption(
                id="inspirational",
                name="Inspirational",
                description="Uplift and motivate the audience with positive, high-energy vibes.",
                image_filename=_img("tone", "inspirational"),
            ),
            GenerationOption(
                id="casual",
                name="Casual",
                description="Write like a friend using conversational, relaxed, and accessible language.",
                image_filename=_img("tone", "casual"),
            ),
        ],
    ),
    GenerationCategory(
        id="goal",
        name="Goal",
        slug="goal",
        options=[
            GenerationOption(
                id="auto",
                name="Auto",
                description="Analyzes your topic to select the most effective goal automatically.",
                image_filename=_img("goal", "auto"),
            ),
            GenerationOption(
                id="viral-reach",
                name="Viral Reach",
                description="Optimize for maximum views using broad appeal and simple language.",
                image_filename=_img("goal", "viral-reach"),
            ),
            GenerationOption(
                id="engagement",
                name="Engagement",
                description="Spark conversation and community debate to boost comments.",
                image_filename=_img("goal", "engagement"),
            ),
            GenerationOption(
                id="authority",
                name="Authority",
                description="Demonstrate deep expertise to build trust and industry credibility.",
                image_filename=_img("goal", "authority"),
            ),
            GenerationOption(
                id="lead-gen",
                name="Lead Gen",
                description="Convert readers into leads by targeting pain points with a solution.",
                image_filename=_img("goal", "lead-gen"),
            ),
            GenerationOption(
                id="personal-story",
                name="Personal Story",
                description="Build emotional bonds through vulnerability and relatable experiences.",
                image_filename=_img("goal", "personal-story"),
            ),
        ],
    ),
    GenerationCategory(
        id="length",
        name="Length",
        slug="length",
        options=[
            GenerationOption(
                id="auto",
                name="Auto",
                description="Analyzes your topic to select the ideal length automatically.",
                image_filename=_img("length", "auto"),
            ),
            GenerationOption(
                id="short",
                name="Short",
                description="Create a concise, punchy update ideal for quick scanning.",
                image_filename=_img("length", "short"),
            ),
            GenerationOption(
                id="medium",
                name="Medium",
                description="Write a balanced post perfect for standard feed engagement.",
                image_filename=_img("length", "medium"),
            ),
            GenerationOption(
                id="long",
                name="Long",
                description="Develop a detailed deep-dive or story for maximum value.",
                image_filename=_img("length", "long"),
            ),
        ],
    ),
    GenerationCategory(
        id="ending",
        name="Ending",
        slug="ending",
        options=[
            GenerationOption(
                id="auto",
                name="Auto",
                description="Analyzes the post goal to select the highest converting ending automatically.",
                image_filename=_img("ending", "auto"),
            ),
            GenerationOption(
                id="mic-drop",
                name="Mic Drop",
                description="Ends abruptly with a powerful statement to demonstrate absolute authority.",
                image_filename=_img("ending", "mic-drop"),
            ),
            GenerationOption(
                id="discussion",
                name="Discussion",
                description="Asks a provocative open-ended question to spark debate and boost reach.",
                image_filename=_img("ending", "discussion"),
            ),
            GenerationOption(
                id="the-hand-raiser",
                name="The Hand-Raiser",
                description="Asks readers to comment a specific keyword to receive a resource or guide.",
                image_filename=_img("ending", "the-hand-raiser"),
            ),
            GenerationOption(
                id="the-pitch",
                name="The Pitch",
                description="Directs qualified leads to DM you or book a call to solve their pain point.",
                image_filename=_img("ending", "the-pitch"),
            ),
            GenerationOption(
                id="profile-funnel",
                name="Profile Funnel",
                description="Encourages readers to visit your profile and ring the bell for more insights.",
                image_filename=_img("ending", "profile-funnel"),
            ),
        ],
    ),
]


def categories_by_id() -> Dict[CategoryId, GenerationCategory]:
    return {c.id: c for c in GENERATION_CATEGORIES}


def option_label(category_id: CategoryId, option_id: str) -> str:
    cat = categories_by_id().get(category_id)
    if not cat:
        return option_id
    for opt in cat.options:
        if opt.id == option_id:
            return opt.name
    return option_id

