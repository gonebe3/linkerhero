from __future__ import annotations

from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_limiter.util import get_remote_address
from itsdangerous import BadSignature, SignatureExpired
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from ...db import db_session
from ...limiter import limiter
from ...models import Session as UserSession, User
from ..services import reset_serializer, send_email
from . import bp


@bp.route("/forgot", methods=["GET", "POST"])
@limiter.limit(
    "10 per hour",
    key_func=lambda: (request.form.get("email", "").strip().lower() or get_remote_address()),
    methods=["POST"],
)
@limiter.limit("20 per hour", key_func=get_remote_address, methods=["POST"])
def forgot_password():
    if request.method == "GET":
        pre = request.args.get("email", "").strip()
        if pre:
            with db_session() as session_db:
                user = session_db.execute(select(User).where(User.email == pre.lower())).scalar_one_or_none()
                if user and getattr(user, "password_reset_sent_at", None):
                    now = datetime.now(timezone.utc)
                    remain = 300 - int((now - user.password_reset_sent_at).total_seconds())
                    if remain > 0:
                        return redirect(url_for("auth.forgot_sent", email=pre, remain=remain))
        return render_template("auth_forgot_password.html", prefill_email=pre)

    email = (request.form.get("email") or "").strip().lower()
    if not email:
        return redirect(url_for("auth.forgot_sent"))

    now = datetime.now(timezone.utc)
    remain = 0
    with db_session() as session_db:
        user = session_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user:
            last_sent = getattr(user, "password_reset_sent_at", None)
            if last_sent is None or (now - last_sent) >= timedelta(minutes=5):
                nonce = token_urlsafe(16)
                user.password_reset_nonce = nonce
                user.password_reset_sent_at = now
                payload = {"email": email, "nonce": nonce}
                token = reset_serializer().dumps(payload)
                link = f"{current_app.config['APP_BASE_URL']}{url_for('auth.reset_password')}?token={token}"
                text_body = f"Click to reset your password: {link}\nThis link will expire in 30 minutes."
                html_body = render_template(
                    "emails/reset_password.html",
                    reset_link=link,
                    app_name="LinkerHero",
                    app_base_url=current_app.config.get("APP_BASE_URL", ""),
                )
                send_email(email, "Reset your LinkerHero password", text_body, html_body=html_body)
            else:
                remain = 300 - int((now - last_sent).total_seconds())
                if remain < 0:
                    remain = 0
    return redirect(url_for("auth.forgot_sent", email=email, remain=remain))


@bp.route("/forgot/sent")
def forgot_sent():
    email = request.args.get("email", "").strip().lower()
    try:
        remain = int(request.args.get("remain", "0"))
    except Exception:
        remain = 0
    return render_template("auth_reset_sent.html", email=email, remain=remain)


@bp.route("/reset", methods=["GET", "POST"])
@limiter.limit("5 per minute", key_func=get_remote_address, methods=["POST"])
def reset_password():
    token = request.args.get("token", "").strip()
    if not token:
        flash("Reset link is invalid or expired. Request a new one.", "error")
        return redirect(url_for("auth.forgot_password"))
    try:
        data = reset_serializer().loads(token, max_age=1800)
        email = (data.get("email") or "").strip().lower()
        nonce = (data.get("nonce") or "").strip()
    except (BadSignature, SignatureExpired):
        flash("Reset link is invalid or expired. Request a new one.", "error")
        return redirect(url_for("auth.forgot_password"))

    with db_session() as session_db:
        user = session_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if not user or not nonce or user.password_reset_nonce != nonce:
            flash("Reset link is invalid or expired. Request a new one.", "error")
            return redirect(url_for("auth.forgot_password", email=email))

    if request.method == "GET":
        return render_template("auth_reset_password.html", token=token)

    pwd = (request.form.get("password") or "").strip()
    confirm = (request.form.get("confirm_password") or "").strip()
    if pwd != confirm:
        flash("Passwords do not match.", "error")
        return redirect(url_for("auth.reset_password", token=token))

    import re as _re

    if not (len(pwd) >= 8 and _re.search(r"[A-Z]", pwd) and _re.search(r"[^A-Za-z0-9]", pwd)):
        flash("Password must be at least 8 characters and include 1 uppercase and 1 special character.", "error")
        return redirect(url_for("auth.reset_password", token=token))

    now = datetime.now(timezone.utc)
    with db_session() as session_db:
        user = session_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if not user or user.password_reset_nonce != nonce:
            flash("Reset link is invalid or expired. Request a new one.", "error")
            return redirect(url_for("auth.forgot_password"))
        user.password_hash = generate_password_hash(pwd)
        user.password_reset_nonce = None
        user.password_reset_sent_at = None
        user.last_login_at = now
        ua = request.headers.get("User-Agent", "")[:255]
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        session_db.add(UserSession(user_id=user.id, user_agent=ua, ip_address=ip, created_at=now, last_seen_at=now))
    return redirect(url_for("main.dashboard"))

