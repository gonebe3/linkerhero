from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Optional

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for, flash
from werkzeug.security import check_password_hash, generate_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import select, update

from ..db import db_session
from ..models import User, Session as UserSession
from datetime import datetime, timedelta, timezone

bp = Blueprint("auth", __name__, url_prefix="")
def _register_form(request_form):
    """Create the register WTForm lazily to avoid import errors at app import time."""
    from wtforms import Form, StringField, PasswordField
    from wtforms.validators import Email, DataRequired, Length, Regexp

    class _Form(Form):
        email = StringField(
            "Email",
            validators=[DataRequired(), Email(message="Enter a valid email")],
        )
        password = PasswordField(
            "Password",
            validators=[
                DataRequired(),
                Length(min=8, message="Minimum 8 characters"),
                Regexp(r".*[A-Z].*", message="At least one uppercase letter"),
                Regexp(r".*[^A-Za-z0-9].*", message="At least one special character"),
            ],
        )

    return _Form(request_form)


@bp.route("/register", methods=["GET", "POST"])
def register():
    try:
        form = _register_form(request.form)
    except Exception:
        # Fallback minimal validation if WTForms import fails for any reason
        class _Minimal:
            def __init__(self, f):
                self.email = type("_", (), {"data": f.get("email", "")})
                self.password = type("_", (), {"data": f.get("password", "")})

            def validate(self):
                import re
                email_ok = bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", self.email.data))
                pwd = self.password.data
                pwd_ok = len(pwd) >= 8 and any(c.isupper() for c in pwd) and any(not c.isalnum() for c in pwd)
                return email_ok and pwd_ok

        form = _Minimal(request.form)
    is_valid = getattr(form, "validate_on_submit", None)
    if request.method == "POST" and (is_valid() if is_valid else form.validate()):
        email = form.email.data.strip().lower()
        pwd = form.password.data
        with db_session() as session_db:
            existing = session_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if existing:
                return render_template("auth_login_spaceship.html", sent=False, error="Email already registered. Please log in.")
            user = User(
                email=email,
                password_hash=generate_password_hash(pwd),
                plan="free",
            )
            session_db.add(user)
            session["user_id"] = user.id
            flash("Welcome! Your account has been created.")
            return redirect(url_for("main.index"))
    return render_template("auth_register_spaceship.html")



def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="magic")


def _send_email(to_email: str, subject: str, body: str) -> None:
    mail_from = current_app.config.get("MAIL_FROM")
    host = current_app.config.get("SMTP_HOST")
    if not mail_from or not host:
        print(f"Magic link for {to_email}: {body}")
        return
    port = current_app.config.get("SMTP_PORT", 587)
    user = current_app.config.get("SMTP_USER")
    pwd = current_app.config.get("SMTP_PASS")
    msg = EmailMessage()
    msg["From"] = mail_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(host, port) as s:
        s.starttls()
        if user and pwd:
            s.login(user, pwd)
        s.send_message(msg)


def ensure_admin(email: str) -> None:
    with db_session() as session_db:
        user = session_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            user = User(email=email, plan="admin")
            session_db.add(user)
        else:
            session_db.execute(update(User).where(User.id == user.id).values(plan="admin"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            return render_template("auth_login_spaceship.html", sent=False, error="Email required")
        token = _serializer().dumps(email)
        link = f"{current_app.config['APP_BASE_URL']}{url_for('auth.magic')}?token={token}"
        _send_email(email, "Your LinkerHero login", f"Click to sign in: {link}")
        return render_template("auth_magic_spaceship.html")
    return render_template("auth_login_spaceship.html", sent=False)


@bp.route("/magic")
def magic():
    token = request.args.get("token")
    if not token:
        return redirect(url_for("main.index"))
    try:
        email = _serializer().loads(token, max_age=3600)
    except (BadSignature, SignatureExpired):
        return redirect(url_for("auth.login"))
    with db_session() as session_db:
        user = session_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            user = User(email=email)
            session_db.add(user)
        session["user_id"] = user.id
        # create a device session entry
        ua = request.headers.get("User-Agent")
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        now = datetime.now(timezone.utc)
        s.add(UserSession(user_id=user.id, user_agent=ua, ip_address=ip, created_at=now, last_seen_at=now))
    return redirect(url_for("main.index"))


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.index"))


@bp.route("/login_password", methods=["POST"])
def login_password():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    if not email or not password:
        return render_template("auth_login_spaceship.html", sent=False, error="Email and password required")
    with db_session() as s:
        user = s.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None or not user.password_hash or not check_password_hash(user.password_hash, password):
            return render_template("auth_login_spaceship.html", sent=False, error="Invalid credentials")
        session["user_id"] = user.id
        ua = request.headers.get("User-Agent")
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        now = datetime.now(timezone.utc)
        s.add(UserSession(user_id=user.id, user_agent=ua, ip_address=ip, created_at=now, last_seen_at=now))
    return redirect(url_for("main.index"))

