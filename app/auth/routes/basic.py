from __future__ import annotations

from datetime import datetime, timezone

from flask import (
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_limiter.util import get_remote_address
from itsdangerous import BadSignature, SignatureExpired
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from ...db import db_session
from ...limiter import limiter
from ...models import Session as UserSession, User
from ...utils import next_month
from ..services import (
    confirm_serializer,
    magic_serializer,
    register_form,
    send_email,
)
from . import bp


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("3 per minute", key_func=get_remote_address, methods=["POST"])
@limiter.limit(
    "10 per hour",
    key_func=lambda: (request.form.get("email", "").strip().lower() or get_remote_address()),
    methods=["POST"],
)
def register():
    if request.method == "GET":
        pre = request.args.get("email", "").strip()
        already = request.args.get("already") == "1"
        return render_template("auth_register_spaceship.html", prefill_email=pre, already_registered=already)

    form = register_form(request.form)
    if not (
        getattr(form, "validate_on_submit", None)
        and form.validate_on_submit()
    ) and not (hasattr(form, "validate") and form.validate()):
        flash("Please correct the highlighted fields and try again.", "error")
        return redirect(url_for("auth.register", email=request.form.get("email", "").strip()))

    email = form.email.data.strip().lower()
    pwd = form.password.data
    cpw = getattr(form, "confirm_password", None)
    if cpw and getattr(cpw, "data", None) != pwd:
        flash("Passwords do not match.", "error")
        return redirect(url_for("auth.register", email=email))

    marketing_opt_in = request.form.get("marketing_opt_in") == "on"
    privacy_ok = request.form.get("privacy_ok") == "on"
    if not privacy_ok:
        flash("You must agree to the Privacy Policy.", "error")
        return redirect(url_for("auth.register", email=email))

    with db_session() as session_db:
        existing = session_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if existing:
            if not getattr(existing, "email_verified_at", None):
                token = confirm_serializer().dumps(email)
                link = f"{current_app.config['APP_BASE_URL']}{url_for('auth.confirm')}?token={token}"
                text_body = f"Please confirm your email: {link}"
                html_body = render_template(
                    "emails/confirm_email.html",
                    confirm_link=link,
                    app_name="LinkerHero",
                    app_base_url=current_app.config.get("APP_BASE_URL", ""),
                )
                send_email(email, "Confirm your LinkerHero email", text_body, html_body=html_body)
                flash("This email is already registered. We re-sent the confirmation link.", "success")
                return redirect(url_for("auth.register", email=email))
            return redirect(url_for("auth.register", email=email, already=1))

        now = datetime.now(timezone.utc)
        user = User(
            email=email,
            display_name=(email.split("@")[0].split(".")[0].split("_")[0].capitalize() if email else None),
            password_hash=generate_password_hash(pwd),
            plan="free",
            plan_started_at=now,
            plan_renews_at=next_month(now),
            marketing_opt_in=marketing_opt_in,
            privacy_accepted_at=datetime.now(timezone.utc),
        )
        session_db.add(user)
        session_db.flush()
        token = confirm_serializer().dumps(email)
        link = f"{current_app.config['APP_BASE_URL']}{url_for('auth.confirm')}?token={token}"
        text_body = f"Please confirm your email: {link}"
        html_body = render_template(
            "emails/confirm_email.html",
            confirm_link=link,
            app_name="LinkerHero",
            app_base_url=current_app.config.get("APP_BASE_URL", ""),
        )
        send_email(email, "Confirm your LinkerHero email", text_body, html_body=html_body)
        flash("Confirmation email sent. Please check your inbox.", "success")
    return redirect(url_for("auth.register", email=email))


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("3 per minute", key_func=get_remote_address, methods=["POST"])
@limiter.limit(
    "10 per hour",
    key_func=lambda: (request.form.get("email", "").strip().lower() or get_remote_address()),
    methods=["POST"],
)
def login():
    if request.method == "GET":
        pre = request.args.get("email", "").strip()
        next_param = request.args.get("next", "").strip()
        return render_template("auth_login_spaceship.html", sent=False, prefill_email=pre, next_param=next_param)
    email = request.form.get("email", "").strip().lower()
    if not email:
        flash("Email required", "error")
        return redirect(url_for("auth.login"))
    with db_session() as session_db:
        existing = session_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if existing and not existing.email_verified_at:
            return redirect(url_for("auth.resend_confirm", email=email))
    token = magic_serializer().dumps(email)
    next_url = request.args.get("next") or request.form.get("next") or url_for("main.index")
    link = f"{current_app.config['APP_BASE_URL']}{url_for('auth.magic')}?token={token}&next={next_url}"
    send_email(email, "Your LinkerHero login", f"Click to sign in: {link}")
    flash("Magic sign-in link sent. Check your inbox.", "success")
    return redirect(url_for("auth.login", email=email))


@bp.route("/magic")
def magic():
    token = request.args.get("token")
    next_url = request.args.get("next") or url_for("main.index")
    if not token:
        return redirect(url_for("main.index"))
    try:
        email = magic_serializer().loads(token, max_age=3600)
    except (BadSignature, SignatureExpired):
        return redirect(url_for("auth.login"))

    with db_session() as session_db:
        user = session_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            now = datetime.now(timezone.utc)
            user = User(
                email=email,
                display_name=(email.split("@")[0].split(".")[0].split("_")[0].capitalize() if email else None),
                plan_started_at=now,
                plan_renews_at=next_month(now),
            )
            session_db.add(user)
            session_db.flush()
        if not user.email_verified_at:
            return redirect(url_for("auth.resend_confirm", email=email))
        session["user_id"] = user.id
        ua = request.headers.get("User-Agent")
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        now = datetime.now(timezone.utc)
        session_db.add(UserSession(user_id=user.id, user_agent=ua, ip_address=ip, created_at=now, last_seen_at=now))
    return redirect(next_url)


@bp.route("/confirm/resend")
@limiter.limit(
    "3 per hour",
    key_func=lambda: (request.args.get("email", "").strip().lower() or get_remote_address()),
)
def resend_confirm():
    email = request.args.get("email", "").strip().lower()
    if not email:
        return redirect(url_for("auth.login"))
    token = confirm_serializer().dumps(email)
    link = f"{current_app.config['APP_BASE_URL']}{url_for('auth.confirm')}?token={token}"
    text_body = f"Please confirm your email: {link}"
    html_body = render_template(
        "emails/confirm_email.html",
        confirm_link=link,
        app_name="LinkerHero",
        app_base_url=current_app.config.get("APP_BASE_URL", ""),
    )
    send_email(email, "Confirm your LinkerHero email", text_body, html_body=html_body)
    flash("Confirmation email sent. Please check your inbox.")
    return render_template("auth_magic_spaceship.html")


@bp.route("/confirm")
def confirm():
    token = request.args.get("token")
    if not token:
        return redirect(url_for("auth.login"))
    try:
        email = confirm_serializer().loads(token, max_age=3 * 24 * 3600)
    except (BadSignature, SignatureExpired):
        return redirect(url_for("auth.login"))
    now = datetime.now(timezone.utc)
    with db_session() as session_db:
        user = session_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            return redirect(url_for("auth.login"))
        if not user.email_verified_at:
            user.email_verified_at = now
        session["user_id"] = user.id
    return redirect(url_for("main.index"))


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.index"))


@bp.route("/login_password", methods=["POST"])
@limiter.limit("5 per minute", key_func=get_remote_address, methods=["POST"])
@limiter.limit(
    "20 per hour",
    key_func=lambda: (request.form.get("email", "").strip().lower() or get_remote_address()),
    methods=["POST"],
)
def login_password():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    if not email or not password:
        flash("Email and password required", "error")
        return redirect(url_for("auth.login", email=email))
    with db_session() as session_db:
        user = session_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None or not user.password_hash or not check_password_hash(user.password_hash, password):
            flash("Invalid credentials", "error")
            return redirect(url_for("auth.login", email=email))
        if not user.email_verified_at:
            return redirect(url_for("auth.resend_confirm", email=email))
        session["user_id"] = user.id
        ua = request.headers.get("User-Agent")
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        now = datetime.now(timezone.utc)
        session_db.add(UserSession(user_id=user.id, user_agent=ua, ip_address=ip, created_at=now, last_seen_at=now))
    next_url = request.form.get("next") or url_for("main.index")
    return redirect(next_url)

