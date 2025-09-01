from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Optional

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for, flash
from werkzeug.security import check_password_hash, generate_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import select, update

from ..db import db_session
from ..models import User, Session as UserSession, Generation
from ..utils import next_month
from datetime import datetime, timedelta, timezone
import json
import httpx
from urllib.parse import urlencode, quote_plus
import os
import secrets

bp = Blueprint("auth", __name__, url_prefix="")


def _absolute_url_for(endpoint: str) -> str:
    """Build an absolute URL for OAuth redirects, preferring APP_BASE_URL.

    This avoids localhost/127.0.0.1, port, or http/https mismatches that cause
    provider errors like "redirect_uri does not match the registered value".
    """
    base = current_app.config.get("APP_BASE_URL")
    if base:
        base = base.rstrip("/")
        path = url_for(endpoint)
        return f"{base}{path}"
    return url_for(endpoint, _external=True)
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
        confirm_password = PasswordField(
            "Confirm Password",
            validators=[DataRequired(), Length(min=8)],
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
        cpw = getattr(form, "confirm_password", None)
        if cpw and getattr(cpw, "data", None) != pwd:
            return render_template("auth_register_spaceship.html", error="Passwords do not match.")
        # Checkboxes
        marketing_opt_in = request.form.get("marketing_opt_in") == "on"
        privacy_ok = request.form.get("privacy_ok") == "on"
        if not privacy_ok:
            return render_template("auth_register_spaceship.html", error="You must agree to the Privacy Policy.")
        with db_session() as session_db:
            existing = session_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if existing:
                return render_template("auth_login_spaceship.html", sent=False, error="Email already registered. Please log in.")
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
            # Send confirmation email
            token = _confirm_serializer().dumps(email)
            link = f"{current_app.config['APP_BASE_URL']}{url_for('auth.confirm')}?token={token}"
            _send_email(email, "Confirm your LinkerHero email", f"Please confirm your email: {link}")
            flash("Confirmation email sent. Please check your inbox.")
            return render_template("auth_magic_spaceship.html")
    return render_template("auth_register_spaceship.html")



def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="magic")


def _confirm_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="confirm")


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
        # Require email confirmation before allowing magic-link login
        with db_session() as s:
            existing = s.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if existing and not existing.email_verified_at:
                return redirect(url_for("auth.resend_confirm", email=email))
        token = _serializer().dumps(email)
        # Preserve next param for smoother UX after magic link
        next_url = request.args.get("next") or request.form.get("next") or url_for('main.index')
        link = f"{current_app.config['APP_BASE_URL']}{url_for('auth.magic')}?token={token}&next={next_url}"
        _send_email(email, "Your LinkerHero login", f"Click to sign in: {link}")
        return render_template("auth_magic_spaceship.html")
    return render_template("auth_login_spaceship.html", sent=False)


@bp.route("/magic")
def magic():
    token = request.args.get("token")
    next_url = request.args.get("next") or url_for('main.index')
    if not token:
        return redirect(url_for("main.index"))
    try:
        email = _serializer().loads(token, max_age=3600)
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
            # Materialize user.id for FK references below
            session_db.flush()
        # Enforce email verification for magic link as well
        if not user.email_verified_at:
            return redirect(url_for("auth.resend_confirm", email=email))
        session["user_id"] = user.id
        # create a device session entry
        ua = request.headers.get("User-Agent")
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        now = datetime.now(timezone.utc)
        session_db.add(UserSession(user_id=user.id, user_agent=ua, ip_address=ip, created_at=now, last_seen_at=now))
    return redirect(next_url)


@bp.route("/confirm/resend")
def resend_confirm():
    email = request.args.get("email", "").strip().lower()
    if not email:
        return redirect(url_for("auth.login"))
    token = _confirm_serializer().dumps(email)
    link = f"{current_app.config['APP_BASE_URL']}{url_for('auth.confirm')}?token={token}"
    _send_email(email, "Confirm your LinkerHero email", f"Please confirm your email: {link}")
    flash("Confirmation email sent. Please check your inbox.")
    return render_template("auth_magic_spaceship.html")


@bp.route("/confirm")
def confirm():
    token = request.args.get("token")
    if not token:
        return redirect(url_for("auth.login"))
    try:
        email = _confirm_serializer().loads(token, max_age=3 * 24 * 3600)
    except (BadSignature, SignatureExpired):
        return redirect(url_for("auth.login"))
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    with db_session() as s:
        user = s.execute(select(User).where(User.email == email)).scalar_one_or_none()
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
def login_password():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    if not email or not password:
        return render_template("auth_login_spaceship.html", sent=False, error="Email and password required")
    with db_session() as s:
        user = s.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None or not user.password_hash or not check_password_hash(user.password_hash, password):
            return render_template("auth_login_spaceship.html", sent=False, error="Invalid credentials")
        if not user.email_verified_at:
            return redirect(url_for("auth.resend_confirm", email=email))
        session["user_id"] = user.id
        ua = request.headers.get("User-Agent")
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        now = datetime.now(timezone.utc)
        s.add(UserSession(user_id=user.id, user_agent=ua, ip_address=ip, created_at=now, last_seen_at=now))
    return redirect(url_for("main.index"))


# --- LinkedIn OAuth (Authorization Code + PKCE not required for confidential apps) ---

@bp.route("/login/linkedin")
def login_linkedin_start():
    client_id = current_app.config.get("LINKEDIN_CLIENT_ID")
    if not client_id:
        return redirect(url_for("auth.login"))
    # Use the current host to avoid localhost/127.0.0.1 mismatches in dev
    redirect_uri = _absolute_url_for('auth.login_linkedin_callback')
    # Use OpenID Connect scopes per LinkedIn docs (openid, profile, email)
    scopes = current_app.config.get("LINKEDIN_SCOPES", "openid profile email")
    # CSRF protection state
    state = secrets.token_urlsafe(16)
    session['li_oauth_state'] = state
    next_url = request.args.get('next') or request.args.get('return_to') or url_for('main.index')
    session['li_oauth_next'] = next_url
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scopes,
        "state": state,
    }
    auth_url = "https://www.linkedin.com/oauth/v2/authorization?" + urlencode(params, quote_via=quote_plus)
    return redirect(auth_url)


# Start LinkedIn share flow requesting w_member_social scope
@bp.route("/share/linkedin/start")
def share_linkedin_start():
    gen_id = request.args.get("gen_id", "").strip()
    uid = session.get("user_id")
    if not uid or not gen_id:
        return redirect(url_for("auth.login"))
    # Ensure the generation belongs to the user
    with db_session() as sdb:
        gen = sdb.get(Generation, gen_id)
        if not gen or gen.user_id != uid:
            return redirect(url_for("main.dashboard"))
    client_id = current_app.config.get("LINKEDIN_CLIENT_ID")
    if not client_id:
        return redirect(url_for("auth.login"))
    # Preserve the share intent across OAuth
    session['li_share_gen_id'] = gen_id
    session['li_oauth_next'] = request.referrer or url_for('main.dashboard')
    redirect_uri = _absolute_url_for('auth.login_linkedin_callback')
    scopes = current_app.config.get("LINKEDIN_SCOPES", "openid profile email")
    if "w_member_social" not in scopes:
        scopes = scopes + " w_member_social"
    state = secrets.token_urlsafe(16)
    session['li_oauth_state'] = state
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scopes,
        "state": state,
    }
    auth_url = "https://www.linkedin.com/oauth/v2/authorization?" + urlencode(params, quote_via=quote_plus)
    return redirect(auth_url)

# Backward-compatible alias for older template links
@bp.route("/oauth/linkedin/start")
def login_linkedin_start_alias():
    return redirect(url_for("auth.login_linkedin_start"))


@bp.route("/auth/linkedin/callback")
def login_linkedin_callback():
    code = request.args.get("code")
    state = request.args.get("state")
    if not state or state != session.get('li_oauth_state'):
        return redirect(url_for("auth.login"))
    if not code:
        return redirect(url_for("auth.login"))
    client_id = current_app.config.get("LINKEDIN_CLIENT_ID")
    client_secret = current_app.config.get("LINKEDIN_CLIENT_SECRET")
    redirect_uri = _absolute_url_for('auth.login_linkedin_callback')
    if not client_id or not client_secret:
        return redirect(url_for("auth.login"))

    # Exchange code for access token
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    try:
        resp = httpx.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        token_data = resp.json()
    except Exception:
        return redirect(url_for("auth.login"))

    access_token = token_data.get("access_token")
    if not access_token:
        return redirect(url_for("auth.login"))

    # Fetch profile using OIDC userinfo; fallback to classic email endpoint if needed
    headers = {"Authorization": f"Bearer {access_token}"}
    sub = None
    email = ""
    try:
        prof = httpx.get("https://api.linkedin.com/v2/userinfo", headers=headers, timeout=20.0).json()
        sub = prof.get("sub")
        email = (prof.get("email") or "").lower().strip()
    except Exception:
        prof = {}
    if not email:
        try:
            email_resp = httpx.get(
                "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))",
                headers=headers,
                timeout=20.0,
            ).json()
            email = (
                (email_resp.get("elements") or [{}])[0]
                .get("handle~", {})
                .get("emailAddress", "")
                .lower()
                .strip()
            )
        except Exception:
            email = ""

    if not (email or sub):
        return redirect(url_for("auth.login"))

    with db_session() as sdb:
        user = None
        if email:
            user = sdb.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None and sub:
            user = sdb.execute(
                select(User).where(User.oauth_provider == "linkedin", User.oauth_sub == sub)
            ).scalar_one_or_none()
        if user is None:
            # Prefer OIDC given_name for display
            given_name = None
            try:
                given_name = (prof.get("given_name") or None) if isinstance(prof, dict) else None
            except Exception:
                given_name = None
            now = datetime.now(timezone.utc)
            user = User(
                email=email or f"li_{sub}@example.local",
                display_name=(given_name or (email.split("@")[0].split(".")[0].split("_")[0].capitalize() if email else None)),
                oauth_provider="linkedin",
                oauth_sub=sub,
                plan="free",
                plan_started_at=now,
                plan_renews_at=next_month(now),
            )
            sdb.add(user)
            sdb.flush()
        else:
            # Update display name from LinkedIn profile if available and not already set
            try:
                given_name = (prof.get("given_name") or None) if isinstance(prof, dict) else None
            except Exception:
                given_name = None
            if given_name and (not getattr(user, "display_name", None)):
                user.display_name = given_name
        # Mark email verified for OAuth users (trusted provider email)
        if email and not user.email_verified_at:
            user.email_verified_at = datetime.now(timezone.utc)
        # Only set LinkerHero session if this is a normal login, not a share flow
        is_share_flow = bool(session.get('li_share_gen_id'))
        if not is_share_flow:
            session["user_id"] = user.id
            ua = request.headers.get("User-Agent")
            ip = request.headers.get("X-Forwarded-For", request.remote_addr)
            now = datetime.now(timezone.utc)
            sdb.add(UserSession(user_id=user.id, user_agent=ua, ip_address=ip, created_at=now, last_seen_at=now))
    # If we came back with a pending share, post to UGC API now
    pending_gen_id = session.pop('li_share_gen_id', None)
    if pending_gen_id and sub:
        try:
            # Reuse our access token to post UGC
            ugc_headers = {
                "Authorization": f"Bearer {access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json",
            }
            with db_session() as s:
                gen = s.get(Generation, pending_gen_id)
                # Allow share as long as the logged-in app user owns it
                app_uid = session.get('user_id')
                if gen and app_uid and gen.user_id == app_uid:
                    payload = {
                        "author": f"urn:li:person:{sub}",
                        "lifecycleState": "PUBLISHED",
                        "specificContent": {
                            "com.linkedin.ugc.ShareContent": {
                                "shareCommentary": {"text": gen.draft_text[:2800]},
                                "shareMediaCategory": "NONE",
                            }
                        },
                        "visibility": {
                            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                        },
                    }
                    resp = httpx.post("https://api.linkedin.com/v2/ugcPosts", headers=ugc_headers, content=json.dumps(payload), timeout=20.0)
                    if resp.status_code == 201:
                        flash("Shared on LinkedIn successfully.")
                    else:
                        flash("LinkedIn share failed. Please try again later.")
        except Exception:
            flash("LinkedIn share failed. Please try again.")
    next_url = session.pop('li_oauth_next', None) or url_for('main.index')
    return redirect(next_url)


# --- Google OAuth (Authorization Code; confidential app) ---

@bp.route("/oauth/google/start")
def login_google_start():
    client_id = current_app.config.get("GOOGLE_CLIENT_ID") or os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        return redirect(url_for("auth.login"))
    redirect_uri = _absolute_url_for('auth.login_google_callback')
    scopes = (current_app.config.get("GOOGLE_SCOPES") or os.getenv("GOOGLE_SCOPES") or "openid email profile")
    state = secrets.token_urlsafe(16)
    session['gg_oauth_state'] = state
    next_url = request.args.get('next') or request.args.get('return_to') or url_for('main.index')
    session['gg_oauth_next'] = next_url
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scopes,
        "state": state,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params, quote_via=quote_plus)
    return redirect(auth_url)


@bp.route("/auth/google/callback")
def login_google_callback():
    code = request.args.get("code")
    state = request.args.get("state")
    if not state or state != session.get('gg_oauth_state'):
        return redirect(url_for("auth.login"))
    if not code:
        return redirect(url_for("auth.login"))
    client_id = current_app.config.get("GOOGLE_CLIENT_ID") or os.getenv("GOOGLE_CLIENT_ID")
    client_secret = current_app.config.get("GOOGLE_CLIENT_SECRET") or os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = _absolute_url_for('auth.login_google_callback')
    if not client_id or not client_secret:
        return redirect(url_for("auth.login"))

    token_url = "https://oauth2.googleapis.com/token"
    try:
        resp = httpx.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        token_data = resp.json()
    except Exception:
        return redirect(url_for("auth.login"))

    access_token = token_data.get("access_token")
    if not access_token:
        return redirect(url_for("auth.login"))

    headers = {"Authorization": f"Bearer {access_token}"}
    sub = None
    email = ""
    given_name = None
    try:
        prof = httpx.get("https://openidconnect.googleapis.com/v1/userinfo", headers=headers, timeout=20.0).json()
        sub = prof.get("sub")
        email = (prof.get("email") or "").lower().strip()
        given_name = prof.get("given_name")
    except Exception:
        prof = {}

    if not (email or sub):
        return redirect(url_for("auth.login"))

    with db_session() as sdb:
        user = None
        if email:
            user = sdb.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None and sub:
            user = sdb.execute(
                select(User).where(User.oauth_provider == "google", User.oauth_sub == sub)
            ).scalar_one_or_none()
        if user is None:
            now = datetime.now(timezone.utc)
            user = User(
                email=email or f"gg_{sub}@example.local",
                display_name=(given_name or (email.split("@")[0].split(".")[0].split("_")[0].capitalize() if email else None)),
                oauth_provider="google",
                oauth_sub=sub,
                plan="free",
                plan_started_at=now,
                plan_renews_at=next_month(now),
                email_verified_at=now,
            )
            sdb.add(user)
            sdb.flush()
        else:
            if given_name and (not getattr(user, "display_name", None)):
                user.display_name = given_name
            if email and not user.email_verified_at:
                user.email_verified_at = datetime.now(timezone.utc)
        session["user_id"] = user.id
        ua = request.headers.get("User-Agent")
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        now = datetime.now(timezone.utc)
        sdb.add(UserSession(user_id=user.id, user_agent=ua, ip_address=ip, created_at=now, last_seen_at=now))
    next_url = session.pop('gg_oauth_next', None) or url_for('main.index')
    return redirect(next_url)

