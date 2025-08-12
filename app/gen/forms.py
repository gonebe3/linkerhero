from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import Length, Optional, URL


class GenerateForm(FlaskForm):
    url = StringField("URL", validators=[Optional(), URL(require_tld=True, message="Enter a valid URL")])
    text = TextAreaField("Text", validators=[Optional(), Length(max=20000)])

    persona = SelectField(
        "Persona",
        choices=[
            ("PM", "Product Manager"),
            ("Consultant", "Consultant"),
            ("Engineer", "Engineer"),
            ("Founder", "Founder"),
            ("Marketer", "Marketer"),
            ("Sales", "Sales"),
        ],
        default="PM",
    )

    tone = SelectField(
        "Tone",
        choices=[
            ("analytical", "Analytical"),
            ("bold", "Bold"),
            ("conversational", "Conversational"),
            ("storytelling", "Storytelling"),
            ("data-driven", "Data-driven"),
        ],
        default="analytical",
    )

    hook_type = SelectField(
        "Hook Type",
        choices=[
            ("auto", "Auto"),
            ("question", "Question"),
            ("contrarian", "Contrarian"),
            ("numbered", "Numbered"),
            ("how_to", "How-to"),
            ("story", "Short Story"),
        ],
        default="auto",
    )

    model = SelectField(
        "Model",
        choices=[("claude", "Claude 3.5 Sonnet"), ("gpt-5", "ChatGPT 5")],
        default="claude",
    )

    submit = SubmitField("Generate")

    def validate(self, extra_validators=None) -> bool:  # type: ignore[override]
        ok = super().validate(extra_validators=extra_validators)
        if not ok:
            return False
        url_val = (self.url.data or "").strip()
        text_val = (self.text.data or "").strip()
        # exactly one of URL or text must be provided
        if bool(url_val) == bool(text_val):
            self.url.errors.append("Provide either a URL or your text (not both).")
            return False
        return True


