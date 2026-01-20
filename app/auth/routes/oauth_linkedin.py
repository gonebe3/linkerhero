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
    # Default to dashboard so the user clearly sees they're logged in.
    next_url = request.args.get("next") or request.args.get("return_to") or url_for("main.dashboard")
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
            flash(
                "This draft belongs to a different LinkerHero account. Please log out and sign in with the account that generated it.",
                "error",
            )
            return redirect(url_for("main.dashboard"))
    client_id = current_app.config.get("LINKEDIN_CLIENT_ID")
    if not client_id:
        return redirect(url_for("auth.login"))
    session["li_share_gen_id"] = gen_id
    session["li_oauth_flow"] = "share"
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
        flash(
            "LinkedIn sign-in failed (session was lost). Check cookies, and ensure APP_BASE_URL matches your current domain (www vs non-www, http vs https).",
            "error",
        )
        return redirect(url_for("auth.login"))
    if not code:
        flash("LinkedIn sign-in failed (missing authorization code). Please try again.", "error")
        return redirect(url_for("auth.login"))
    client_id = current_app.config.get("LINKEDIN_CLIENT_ID")
    client_secret = current_app.config.get("LINKEDIN_CLIENT_SECRET")

    redirect_uri = absolute_url_for("auth.login_linkedin_callback")
    if not client_id or not client_secret:
        flash("LinkedIn sign-in is not configured on the server (missing client ID/secret).", "error")
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
        flash("LinkedIn sign-in failed while exchanging the authorization code. Please try again.", "error")
        return redirect(url_for("auth.login"))

    access_token = token_data.get("access_token")
    if not access_token:
        flash("LinkedIn sign-in failed (no access token returned). Please try again.", "error")
        return redirect(url_for("auth.login"))

    headers = {"Authorization": f"Bearer {access_token}"}
    sub = None
    email = ""
    full_name = None
    picture = None
    try:
        prof = httpx.get("https://api.linkedin.com/v2/userinfo", headers=headers, timeout=20.0).json()
        sub = prof.get("sub")
        email = (prof.get("email") or "").lower().strip()
        try:
            full_name = (prof.get("name") or None) if isinstance(prof, dict) else None
        except Exception:
            full_name = None
        try:
            picture = (prof.get("picture") or None) if isinstance(prof, dict) else None
        except Exception:
            picture = None
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
        flash("LinkedIn sign-in failed (no email returned by LinkedIn).", "error")
        return redirect(url_for("auth.login"))

    # Share flow should NEVER create/switch LinkerHero accounts. It's only for connecting/sharing.
    is_share_flow = bool(session.get("li_share_gen_id")) or (session.get("li_oauth_flow") == "share")
    if is_share_flow:
        pending_gen_id = session.pop("li_share_gen_id", None)
        session.pop("li_oauth_flow", None)
        if not pending_gen_id:
            flash("LinkedIn share failed (missing draft). Please try again.", "error")
            return redirect(url_for("main.dashboard"))
        app_uid = session.get("user_id")
        if not app_uid:
            flash(
                "LinkedIn share failed (you were logged out during the LinkedIn sign-in). Please log in and try again.",
                "error",
            )
            return redirect(url_for("auth.login", next=url_for("main.dashboard")))
        if not sub:
            flash("LinkedIn share failed (missing LinkedIn user id). Please try again.", "error")
            return redirect(url_for("main.dashboard"))
        try:
            ugc_headers = {
                "Authorization": f"Bearer {access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json",
            }
            with db_session() as session_db:
                gen = session_db.get(Generation, pending_gen_id)
                if not gen or gen.user_id != app_uid:
                    flash(
                        "LinkedIn share failed (draft not found for this account). Please open the draft again and retry.",
                        "error",
                    )
                else:
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
                        flash("Shared on LinkedIn successfully.", "success")
                    else:
                        # Include some detail so debugging is possible (but keep it short)
                        flash(f"LinkedIn share failed ({resp.status_code}). Please try again.", "error")
        except Exception:
            flash("LinkedIn share failed. Please try again.", "error")
        next_url = session.pop("li_oauth_next", None) or url_for("main.dashboard")
        return redirect(next_url)

    with db_session() as session_db:
        user = None
        # Prefer stable OAuth identity lookup first
        if sub:
            user = session_db.execute(
                select(User).where(User.oauth_provider == "linkedin", User.oauth_sub == sub)
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
                    "(email/password or the provider you used before), or use a different LinkedIn account/email.",
                    "error",
                )
                return redirect(url_for("auth.login", email=email))
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
                full_name=full_name or None,
                profile_image_url=picture or None,
                profile_source="linkedin",
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
            if full_name and (not getattr(user, "full_name", None)):
                user.full_name = full_name
            if picture and (not getattr(user, "profile_image_url", None)):
                user.profile_image_url = picture
            if not getattr(user, "profile_source", None):
                user.profile_source = "linkedin"
        if email and not user.email_verified_at:
            user.email_verified_at = datetime.now(timezone.utc)
        session["user_id"] = user.id
        ua = request.headers.get("User-Agent")
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        now = datetime.now(timezone.utc)
        session_db.add(UserSession(user_id=user.id, user_agent=ua, ip_address=ip, created_at=now, last_seen_at=now))

    next_url = session.pop("li_oauth_next", None) or url_for("main.index")
    return redirect(next_url)

