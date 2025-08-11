from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Optional

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import select, update

from ..db import db_session
from ..models import User

bp = Blueprint("auth", __name__, url_prefix="")


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
            return render_template("auth_login.html", sent=False, error="Email required")
        token = _serializer().dumps(email)
        link = f"{current_app.config['APP_BASE_URL']}{url_for('auth.magic')}?token={token}"
        _send_email(email, "Your LinkerHero login", f"Click to sign in: {link}")
        return render_template("auth_magic.html")
    return render_template("auth_login.html", sent=False)


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
    return redirect(url_for("main.index"))


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.index"))

