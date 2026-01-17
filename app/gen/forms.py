from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import Length, Optional, URL
from flask_wtf.file import FileField, FileAllowed


class GenerateForm(FlaskForm):
    class Meta:
        csrf = False  # Disable CSRF for this HTMX endpoint
    url = StringField("URL", validators=[Optional(), URL(require_tld=True, message="Enter a valid URL")])
    text = TextAreaField("Text", validators=[Optional(), Length(max=20000)])
    file = FileField(
        "File",
        validators=[
            Optional(),
            FileAllowed(
                ["txt", "pdf", "docx"],
                "Unsupported file type. Allowed: txt, pdf, docx.",
            ),
        ],
    )

    persona = SelectField(
        "Persona",
        choices=[
            ("auto", "Auto"),
            ("the-founder", "The Founder"),
            ("the-expert", "The Expert"),
            ("the-storyteller", "The Storyteller"),
            ("the-disruptor", "The Disruptor"),
            ("the-executive", "The Executive"),
            ("the-growth-hacker", "The Growth Hacker"),
        ],
        default="auto",
    )

    tone = SelectField(
        "Tone",
        choices=[
            ("auto", "Auto"),
            ("professional", "Professional"),
            ("empathetic", "Empathetic"),
            ("direct", "Direct"),
            ("witty", "Witty"),
            ("inspirational", "Inspirational"),
            ("casual", "Casual"),
        ],
        default="auto",
    )

    hook_type = SelectField(
        "Hook Type",
        choices=[
            ("auto", "Auto"),
            ("the-hot-take", "The Hot Take"),
            ("hard-lesson", "Hard Lesson"),
            ("the-blueprint-how-to", "The Blueprint (How-To)"),
            ("zero-to-hero-transformation", "Zero to Hero (Transformation)"),
            ("cheat-sheet-listicle", "Cheat Sheet (Listicle)"),
            ("the-call-out-direct-audience", "The Call-Out (Direct Audience)"),
            ("shock-stat-statistic", "Shock Stat (Statistic)"),
        ],
        default="auto",
    )

    goal = SelectField(
        "Goal",
        choices=[
            ("auto", "Auto"),
            ("viral-reach", "Viral Reach"),
            ("engagement", "Engagement"),
            ("authority", "Authority"),
            ("lead-gen", "Lead Gen"),
            ("personal-story", "Personal Story"),
        ],
        default="auto",
    )

    length = SelectField(
        "Length",
        choices=[("auto", "Auto"), ("short", "Short"), ("medium", "Medium"), ("long", "Long")],
        default="auto",
    )

    ending = SelectField(
        "Ending",
        choices=[
            ("auto", "Auto"),
            ("mic-drop", "Mic Drop"),
            ("discussion", "Discussion"),
            ("the-hand-raiser", "The Hand-Raiser"),
            ("the-pitch", "The Pitch"),
            ("profile-funnel", "Profile Funnel"),
        ],
        default="auto",
    )

    emoji = SelectField("Emoji", choices=[("no", "No"), ("yes", "Yes")], default="no")

    language = SelectField(
        "Language",
        choices=[
            ("English", "English"),
            ("Spanish", "Spanish"),
            ("French", "French"),
            ("German", "German"),
            ("Portuguese", "Portuguese"),
            ("Italian", "Italian"),
            ("Dutch", "Dutch"),
            ("Japanese", "Japanese"),
            ("Korean", "Korean"),
            ("Chinese", "Chinese"),
        ],
        default="English",
    )

    model = SelectField(
        "Model",
        choices=[("claude", "Claude 3.5 Sonnet"), ("gpt-5", "ChatGPT 5")],
        default="claude",
    )

    submit = SubmitField("Generate")

    def validate(self, extra_validators=None) -> bool:  # type: ignore[override]
        # We allow empty here and handle all validation in the route to avoid client/htmx edge cases.
        super().validate(extra_validators=extra_validators)
        return True


