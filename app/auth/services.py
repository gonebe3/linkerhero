from __future__ import annotations

import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any

from flask import current_app, render_template, url_for
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import select, update

from ..db import db_session
from ..models import User
from ..utils import next_month


def absolute_url_for(endpoint: str) -> str:
    """Build an absolute URL for OAuth redirects, preferring APP_BASE_URL."""
    base = current_app.config.get("APP_BASE_URL")
    if base:
        base = base.rstrip("/")
        path = url_for(endpoint)
        return f"{base}{path}"
    return url_for(endpoint, _external=True)


def register_form(request_form: Any):
    """Create the register WTForm lazily to avoid import errors at app import time."""
    try:
        from wtforms import Form, PasswordField, StringField
        from wtforms.validators import DataRequired, Email, Length, Regexp

        class _Form(Form):
            email = StringField("Email", validators=[DataRequired(), Email(message="Enter a valid email")])
            password = PasswordField(
                "Password",
                validators=[
                    DataRequired(),
                    Length(min=8, message="Minimum 8 characters"),
                    Regexp(r".*[A-Z].*", message="At least one uppercase letter"),
                    Regexp(r".*[^A-Za-z0-9].*", message="At least one special character"),
                ],
            )
            confirm_password = PasswordField(
                "Confirm Password",
                validators=[DataRequired(), Length(min=8)],
            )

        return _Form(request_form)
    except Exception:

        class _Minimal:
            def __init__(self, form_data: Any) -> None:
                self.email = type("_", (), {"data": form_data.get("email", "")})
                self.password = type("_", (), {"data": form_data.get("password", "")})
                self.confirm_password = type("_", (), {"data": form_data.get("confirm_password", "")})

            def validate(self) -> bool:
                import re

                email_ok = bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", self.email.data))
                pwd = self.password.data
                pwd_ok = len(pwd) >= 8 and any(c.isupper() for c in pwd) and any(not c.isalnum() for c in pwd)
                return email_ok and pwd_ok

        return _Minimal(request_form)


def _serializer(salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=salt)


def magic_serializer() -> URLSafeTimedSerializer:
    return _serializer("magic")


def confirm_serializer() -> URLSafeTimedSerializer:
    return _serializer("confirm")


def reset_serializer() -> URLSafeTimedSerializer:
    return _serializer("reset")


def send_email(to_email: str, subject: str, body: str, html_body: str | None = None) -> None:
    mail_from = current_app.config.get("MAIL_FROM")
    host = current_app.config.get("SMTP_HOST")
    if not mail_from or not host:
        print(f"Email to {to_email}: {subject}\n{body}")
        if html_body:
            print("[HTML email content omitted in console]")
        return
    port = current_app.config.get("SMTP_PORT", 587)
    user = current_app.config.get("SMTP_USER")
    pwd = current_app.config.get("SMTP_PASS")
    msg = EmailMessage()
    msg["From"] = mail_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP(host, port) as smtp:
        smtp.starttls()
        if user and pwd:
            smtp.login(user, pwd)
        smtp.send_message(msg)


def ensure_admin(email: str) -> None:
    with db_session() as session_db:
        user = session_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            now = datetime.now(timezone.utc)
            user = User(email=email, plan="admin", plan_started_at=now, plan_renews_at=next_month(now))
            session_db.add(user)
        else:
            session_db.execute(update(User).where(User.id == user.id).values(plan="admin"))

