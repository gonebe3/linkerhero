from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlencode

import httpx
from flask import current_app, flash, redirect, request, session, url_for
from flask_limiter.util import get_remote_address
from sqlalchemy import select

from ...db import db_session
from ...limiter import limiter
from ...models import Generation, Session as UserSession, User
from ...utils import next_month
from ..services import absolute_url_for
from . import bp


@bp.route("/login/linkedin")
@limiter.limit("10 per minute", key_func=get_remote_address)
def login_linkedin_start():
    client_id = current_app.config.get("LINKEDIN_CLIENT_ID")
    if not client_id:
        return redirect(url_for("auth.login"))
    redirect_uri = absolute_url_for("auth.login_linkedin_callback")
    scopes = current_app.config.get("LINKEDIN_SCOPES", "openid profile email")
    state = secrets.token_urlsafe(16)
    session["li_oauth_state"] = state
    next_url = request.args.get("next") or request.args.get("return_to") or url_for("main.index")
    session["li_oauth_next"] = next_url
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scopes,
        "state": state,
    }
    auth_url = "https://www.linkedin.com/oauth/v2/authorization?" + urlencode(params, quote_via=quote_plus)
    return redirect(auth_url)


@bp.route("/share/linkedin/start")
def share_linkedin_start():
    gen_id = request.args.get("gen_id", "").strip()
    uid = session.get("user_id")
    if not uid or not gen_id:
        return redirect(url_for("auth.login"))
    with db_session() as session_db:
        gen = session_db.get(Generation, gen_id)
        if not gen or gen.user_id != uid:
            return redirect(url_for("main.dashboard"))
    client_id = current_app.config.get("LINKEDIN_CLIENT_ID")
    if not client_id:
        return redirect(url_for("auth.login"))
    session["li_share_gen_id"] = gen_id
    session["li_oauth_next"] = request.referrer or url_for("main.dashboard")
    redirect_uri = absolute_url_for("auth.login_linkedin_callback")
    scopes = current_app.config.get("LINKEDIN_SCOPES", "openid profile email")
    if "w_member_social" not in scopes:
        scopes = scopes + " w_member_social"
    state = secrets.token_urlsafe(16)
    session["li_oauth_state"] = state
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scopes,
        "state": state,
    }
    auth_url = "https://www.linkedin.com/oauth/v2/authorization?" + urlencode(params, quote_via=quote_plus)
    return redirect(auth_url)


@bp.route("/oauth/linkedin/start")
def login_linkedin_start_alias():
    return redirect(url_for("auth.login_linkedin_start"))


@bp.route("/auth/linkedin/callback")
def login_linkedin_callback():
    code = request.args.get("code")
    state = request.args.get("state")
    if not state or state != session.get("li_oauth_state"):
        return redirect(url_for("auth.login"))
    if not code:
        return redirect(url_for("auth.login"))
    client_id = current_app.config.get("LINKEDIN_CLIENT_ID")
    client_secret = current_app.config.get("LINKEDIN_CLIENT_SECRET")

    redirect_uri = absolute_url_for("auth.login_linkedin_callback")
    if not client_id or not client_secret:
        return redirect(url_for("auth.login"))

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

    with db_session() as session_db:
        user = None
        if email:
            user = session_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None and sub:
            user = session_db.execute(
                select(User).where(User.oauth_provider == "linkedin", User.oauth_sub == sub)
            ).scalar_one_or_none()
        if user is None:
            given_name = None
            try:
                given_name = (prof.get("given_name") or None) if isinstance(prof, dict) else None
            except Exception:
                given_name = None
            now = datetime.now(timezone.utc)
            user = User(
                email=email or f"li_{sub}@example.local",
                display_name=given_name
                or (email.split("@")[0].split(".")[0].split("_")[0].capitalize() if email else None),
                oauth_provider="linkedin",
                oauth_sub=sub,
                plan="free",
                plan_started_at=now,
                plan_renews_at=next_month(now),
            )
            session_db.add(user)
            session_db.flush()
        else:
            try:
                given_name = (prof.get("given_name") or None) if isinstance(prof, dict) else None
            except Exception:
                given_name = None
            if given_name and (not getattr(user, "display_name", None)):
                user.display_name = given_name
        if email and not user.email_verified_at:
            user.email_verified_at = datetime.now(timezone.utc)
        is_share_flow = bool(session.get("li_share_gen_id"))
        if not is_share_flow:
            session["user_id"] = user.id
            ua = request.headers.get("User-Agent")
            ip = request.headers.get("X-Forwarded-For", request.remote_addr)
            now = datetime.now(timezone.utc)
            session_db.add(UserSession(user_id=user.id, user_agent=ua, ip_address=ip, created_at=now, last_seen_at=now))

    pending_gen_id = session.pop("li_share_gen_id", None)
    if pending_gen_id and sub:
        try:
            ugc_headers = {
                "Authorization": f"Bearer {access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json",
            }
            with db_session() as session_db:
                gen = session_db.get(Generation, pending_gen_id)
                app_uid = session.get("user_id")
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
                    resp = httpx.post(
                        "https://api.linkedin.com/v2/ugcPosts",
                        headers=ugc_headers,
                        content=json.dumps(payload),
                        timeout=20.0,
                    )
                    if resp.status_code == 201:
                        flash("Shared on LinkedIn successfully.")
                    else:
                        flash("LinkedIn share failed. Please try again later.")
        except Exception:
            flash("LinkedIn share failed. Please try again.")
    next_url = session.pop("li_oauth_next", None) or url_for("main.index")
    return redirect(next_url)

