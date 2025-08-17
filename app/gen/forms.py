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
        # We allow empty here and handle all validation in the route to avoid client/htmx edge cases.
        super().validate(extra_validators=extra_validators)
        return True


