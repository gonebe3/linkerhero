from __future__ import annotations

from flask import Blueprint, render_template, session
from sqlalchemy import select

from ..db import db_session
from ..models import Generation, User

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
    left_gpt = max(0, (user.quota_gpt_monthly or 0) - (user.quota_gpt_used or 0)) if user else 0
    left_claude = max(0, (user.quota_claude_monthly or 0) - (user.quota_claude_used or 0)) if user else 0
    left_total = left_gpt + left_claude
    return render_template(
        "dashboard_spaceship.html",
        user=user,
        generations=gens,
        left_gpt=left_gpt,
        left_claude=left_claude,
        left_total=left_total,
    )

