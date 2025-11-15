from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlencode

import httpx
from flask import current_app, redirect, request, session, url_for
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
    redirect_uri = absolute_url_for("auth.login_google_callback")
    scopes = current_app.config.get("GOOGLE_SCOPES") or os.getenv("GOOGLE_SCOPES") or "openid email profile"
    state = secrets.token_urlsafe(16)
    session["gg_oauth_state"] = state
    next_url = request.args.get("next") or request.args.get("return_to") or url_for("main.index")
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
        return redirect(url_for("auth.login"))
    if not code:
        return redirect(url_for("auth.login"))
    client_id = current_app.config.get("GOOGLE_CLIENT_ID") or os.getenv("GOOGLE_CLIENT_ID")
    client_secret = current_app.config.get("GOOGLE_CLIENT_SECRET") or os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = absolute_url_for("auth.login_google_callback")
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

    with db_session() as session_db:
        user = None
        if email:
            user = session_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None and sub:
            user = session_db.execute(
                select(User).where(User.oauth_provider == "google", User.oauth_sub == sub)
            ).scalar_one_or_none()
        if user is None:
            now = datetime.now(timezone.utc)
            user = User(
                email=email or f"gg_{sub}@example.local",
                display_name=given_name
                or (email.split("@")[0].split(".")[0].split("_")[0].capitalize() if email else None),
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
            if email and not user.email_verified_at:
                user.email_verified_at = datetime.now(timezone.utc)
        session["user_id"] = user.id
        ua = request.headers.get("User-Agent")
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        now = datetime.now(timezone.utc)
        session_db.add(UserSession(user_id=user.id, user_agent=ua, ip_address=ip, created_at=now, last_seen_at=now))
    next_url = session.pop("gg_oauth_next", None) or url_for("main.index")
    return redirect(next_url)

