from __future__ import annotations

from flask import Blueprint, render_template, session
from sqlalchemy import select

from ..db import db_session
from ..models import Generation

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    is_logged_in = "user_id" in session
    return render_template("main_index.html", is_logged_in=is_logged_in)


@bp.route("/me/history")
def me_history():
    uid = session.get("user_id")
    if not uid:
        return render_template("me_history.html", generations=[])
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
    return render_template("me_history.html", generations=gens)

