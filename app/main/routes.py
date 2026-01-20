from __future__ import annotations

from flask import Blueprint, render_template, session, redirect, url_for, request
from sqlalchemy import select, func

from ..db import db_session
from ..models import Generation, User
from datetime import datetime, timezone
from ..utils import next_month
import os
from flask import current_app

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    is_logged_in = "user_id" in session
    return render_template("main_index_spaceship.html", is_logged_in=is_logged_in)


@bp.route("/pricing")
def pricing():
    return render_template("pricing_spaceship.html")


@bp.route("/privacy")
def privacy():
    return render_template("privacy_spaceship.html")


@bp.route("/email-policy")
def email_policy():
    return render_template("email_policy_spaceship.html")


@bp.route("/me/history")
def me_history():
    uid = session.get("user_id")
    if not uid:
        return render_template("me_history_spaceship.html", generations=[])
    with db_session() as s:
        gens = (
            s.execute(
                select(Generation)
                .where(Generation.user_id == uid, Generation.deleted_at.is_(None))
                .order_by(Generation.created_at.desc())
                .limit(10)
            )
            .scalars()
            .all()
        )
    return render_template("me_history_spaceship.html", generations=gens)


@bp.route("/me/dashboard")
def dashboard():
    uid = session.get("user_id")
    if not uid:
        return render_template("main_index_spaceship.html", is_logged_in=False)
    with db_session() as s:
        user = s.get(User, uid)
        # If returning from Stripe Checkout, eagerly synchronize subscription status
        try:
            if request.args.get("sub") == "success":
                import stripe
                stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY") or os.getenv("STRIPE_SECRET_KEY") or ""
                sub = None
                if request.args.get("session_id"):
                    sess = stripe.checkout.Session.retrieve(request.args["session_id"])
                    sub_id = sess.get("subscription")
                    if sub_id:
                        sub = stripe.Subscription.retrieve(sub_id)
                # Fallback: if no session_id or retrieval failed, look up latest subscription for this customer
                if not sub and getattr(user, "stripe_customer_id", None):
                    subs = stripe.Subscription.list(customer=user.stripe_customer_id, status="all", limit=10)
                    # Prefer an active/trialing subscription
                    candidates = [it for it in subs.data if it.get("status") in ("active", "trialing")]
                    if not candidates and subs.data:
                        candidates = subs.data
                    sub = candidates[0] if candidates else None
                if sub:
                    status = sub.get("status")
                    cancel_at_period_end = bool(sub.get("cancel_at_period_end"))
                    current_period_end = sub.get("current_period_end")
                    if status in ("active", "trialing"):
                        user.plan = "personal"
                        user.quota_claude_monthly = 30
                        user.quota_gpt_monthly = 50
                        user.cancel_at_period_end = cancel_at_period_end
                        if current_period_end:
                            user.plan_renews_at = datetime.fromtimestamp(current_period_end, tz=timezone.utc)
                    elif status in ("canceled", "incomplete_expired", "unpaid", "paused"):
                        user.plan = "free"
                        user.cancel_at_period_end = False
                        user.plan_renews_at = None
        except Exception:
            # Non-fatal if sync fails; webhook will catch up
            pass
        # Handle renewal boundary
        now = datetime.now(timezone.utc)
        if user and user.plan_renews_at and now >= user.plan_renews_at:
            # If user had requested cancel at period end, move to free and reset quotas to free baseline
            if getattr(user, 'cancel_at_period_end', False):
                user.plan = 'free'
                user.cancel_at_period_end = False
                user.quota_claude_monthly = 3
                user.quota_gpt_monthly = 2
                user.quota_claude_used = min(user.quota_claude_used or 0, user.quota_claude_monthly)
                user.quota_gpt_used = min(user.quota_gpt_used or 0, user.quota_gpt_monthly)
                user.plan_renews_at = None
            else:
                # Normal renewal: reset usage and schedule next month
                user.quota_gpt_used = 0
                user.quota_claude_used = 0
                user.plan_renews_at = next_month(now)
        gens = (
            s.execute(
                select(Generation)
                .where(Generation.user_id == uid, Generation.deleted_at.is_(None))
                .order_by(Generation.created_at.desc())
                .limit(20)
            )
            .scalars()
            .all()
        )
        generations_count = s.execute(
            select(func.count(Generation.id)).where(
                Generation.user_id == uid, Generation.deleted_at.is_(None)
            )
        ).scalar() or 0
    left_gpt = max(0, (user.quota_gpt_monthly or 0) - (user.quota_gpt_used or 0)) if user else 0
    left_claude = max(0, (user.quota_claude_monthly or 0) - (user.quota_claude_used or 0)) if user else 0
    left_total = left_gpt + left_claude
    return render_template(
        "dashboard_spaceship.html",
        user=user,
        generations=gens,
        generations_count=generations_count,
        left_gpt=left_gpt,
        left_claude=left_claude,
        left_total=left_total,
    )


@bp.route("/me/generations/<gen_id>/delete", methods=["POST"])
def delete_generation(gen_id: str):
    uid = session.get("user_id")
    if not uid:
        return redirect(url_for("auth.login"))
    with db_session() as s:
        gen = s.get(Generation, gen_id)
        if gen and gen.user_id == uid:
            gen.deleted_at = func.now()
    next_url = request.referrer or url_for("main.dashboard")
    return redirect(next_url)


# Public preview page for sharing a generation as a link (for LinkedIn offsite share)
@bp.route("/share/preview/<gen_id>")
def share_preview(gen_id: str):
    with db_session() as s:
        gen = s.get(Generation, gen_id)
        if not gen or gen.deleted_at is not None:
            return redirect(url_for("main.index"))
        # Simple title from first line
        title = (gen.draft_text.split("\n", 1)[0] or "LinkerHero Draft").strip()[:120]
        description = gen.draft_text.strip()[:300]
    return render_template("share_preview.html", title=title, description=description, body=gen.draft_text)


@bp.route("/api/generations/<gen_id>/draft", methods=["POST"])
def update_generation_draft(gen_id: str):
    """
    Update a generated draft text (for LinkedIn-like composer edits).
    CSRF is enforced globally; HTMX requests include X-CSRFToken automatically.
    """
    uid = session.get("user_id")
    if not uid:
        return ("unauthorized", 401)
    draft_text = (request.form.get("draft_text") or "").strip()
    if not draft_text:
        return ("draft_text required", 400)
    # Keep a reasonable upper bound (LinkedIn UGC uses <= 2800; we allow more but cap storage)
    if len(draft_text) > 10000:
        draft_text = draft_text[:10000]
    with db_session() as s:
        gen = s.get(Generation, gen_id)
        if not gen or gen.deleted_at is not None or gen.user_id != uid:
            return ("not found", 404)
        gen.draft_text = draft_text
    return ("", 204)

