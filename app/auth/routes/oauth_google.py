from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlencode, urlparse

import httpx
from flask import current_app, flash, redirect, request, session, url_for
from flask_limiter.util import get_remote_address
from sqlalchemy import select

from ...db import db_session
from ...limiter import limiter
from ...models import Session as UserSession, User
from ...utils import next_month
from ..services import absolute_url_for
from . import bp


@bp.route("/oauth/google/start")
@limiter.limit("10 per minute", key_func=get_remote_address)
def login_google_start():
    client_id = current_app.config.get("GOOGLE_CLIENT_ID") or os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        return redirect(url_for("auth.login"))
    # Keep OAuth redirect_uri stable (must match Google Console whitelist),
    # but canonicalize local host before starting OAuth so the session cookie survives.
    try:
        base = str(current_app.config.get("APP_BASE_URL", "")).rstrip("/")
        base_host = (urlparse(base).netloc or "").strip()
        req_host = (request.host or "").strip()
        if base_host and req_host and base_host != req_host:
            base_name = base_host.split(":", 1)[0]
            req_name = req_host.split(":", 1)[0]
            local_aliases = {"localhost", "127.0.0.1"}
            if base_name in local_aliases and req_name in local_aliases:
                qs = ("?" + request.query_string.decode("utf-8", errors="ignore")) if request.query_string else ""
                target = f"{base}{request.path}{qs}"
                return redirect(target)
    except Exception:
        pass
    redirect_uri = absolute_url_for("auth.login_google_callback")
    scopes = current_app.config.get("GOOGLE_SCOPES") or os.getenv("GOOGLE_SCOPES") or "openid email profile"
    state = secrets.token_urlsafe(16)
    session["gg_oauth_state"] = state
    # Default to dashboard so the user clearly sees they're logged in.
    next_url = request.args.get("next") or request.args.get("return_to") or url_for("main.dashboard")
    session["gg_oauth_next"] = next_url
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
    if not state or state != session.get("gg_oauth_state"):
        flash(
            "Google sign-in failed (session was lost). Check cookies, and ensure APP_BASE_URL matches your current domain (www vs non-www, http vs https).",
            "error",
        )
        return redirect(url_for("auth.login"))
    if not code:
        flash("Google sign-in failed (missing authorization code). Please try again.", "error")
        return redirect(url_for("auth.login"))
    client_id = current_app.config.get("GOOGLE_CLIENT_ID") or os.getenv("GOOGLE_CLIENT_ID")
    client_secret = current_app.config.get("GOOGLE_CLIENT_SECRET") or os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = absolute_url_for("auth.login_google_callback")
    if not client_id or not client_secret:
        flash("Google sign-in is not configured on the server (missing client ID/secret).", "error")
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
        flash("Google sign-in failed while exchanging the authorization code. Please try again.", "error")
        return redirect(url_for("auth.login"))

    access_token = token_data.get("access_token")
    if not access_token:
        flash("Google sign-in failed (no access token returned). Please try again.", "error")
        return redirect(url_for("auth.login"))

    headers = {"Authorization": f"Bearer {access_token}"}
    sub = None
    email = ""
    given_name = None
    full_name = None
    picture = None
    try:
        prof = httpx.get("https://openidconnect.googleapis.com/v1/userinfo", headers=headers, timeout=20.0).json()
        sub = prof.get("sub")
        email = (prof.get("email") or "").lower().strip()
        given_name = prof.get("given_name")
        full_name = prof.get("name")
        picture = prof.get("picture")
    except Exception:
        prof = {}

    if not (email or sub):
        flash("Google sign-in failed (no email returned by Google).", "error")
        return redirect(url_for("auth.login"))

    with db_session() as session_db:
        user = None
        # Prefer stable OAuth identity lookup first
        if sub:
            user = session_db.execute(
                select(User).where(User.oauth_provider == "google", User.oauth_sub == sub)
            ).scalar_one_or_none()
        # Optionally link by email (default behavior)
        if user is None and email and current_app.config.get("OAUTH_LINK_BY_EMAIL", True):
            user = session_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        # If we are NOT linking by email and an account already exists for that email, refuse OAuth login.
        if user is None and email and not current_app.config.get("OAUTH_LINK_BY_EMAIL", True):
            existing_by_email = session_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if existing_by_email is not None:
                flash(
                    "An account already exists for this email. Please sign in using the original method "
                    "(email/password or the provider you used before), or use a different Google account/email.",
                    "error",
                )
                return redirect(url_for("auth.login", email=email))
        if user is None:
            now = datetime.now(timezone.utc)
            user = User(
                email=email or f"gg_{sub}@example.local",
                display_name=given_name
                or (email.split("@")[0].split(".")[0].split("_")[0].capitalize() if email else None),
                full_name=full_name or None,
                profile_image_url=picture or None,
                profile_source="google",
                oauth_provider="google",
                oauth_sub=sub,
                plan="free",
                plan_started_at=now,
                plan_renews_at=next_month(now),
                email_verified_at=now,
            )
            session_db.add(user)
            session_db.flush()
        else:
            if given_name and (not getattr(user, "display_name", None)):
                user.display_name = given_name
            if full_name and (not getattr(user, "full_name", None)):
                user.full_name = full_name
            if picture and (not getattr(user, "profile_image_url", None)):
                user.profile_image_url = picture
            if not getattr(user, "profile_source", None):
                user.profile_source = "google"
            if email and not user.email_verified_at:
                user.email_verified_at = datetime.now(timezone.utc)
        session["user_id"] = user.id
        ua = request.headers.get("User-Agent")
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        now = datetime.now(timezone.utc)
        session_db.add(UserSession(user_id=user.id, user_agent=ua, ip_address=ip, created_at=now, last_seen_at=now))
    next_url = session.pop("gg_oauth_next", None) or url_for("main.index")
    return redirect(next_url)

