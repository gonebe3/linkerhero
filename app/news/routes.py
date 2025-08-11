from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import select

from ..db import db_session
from ..models import Article, User
from .rss import refresh_feeds, extract_url

bp = Blueprint("news", __name__, url_prefix="")


@bp.route("/news")
def news_board():
    page = int(request.args.get("page", 1))
    q = request.args.get("q", "").strip().lower()
    page_size = 20
    with db_session() as s:
        stmt = select(Article).where(Article.deleted_at.is_(None)).order_by(Article.created_at.desc())
        articles = s.execute(stmt).scalars().all()
    if q:
        articles = [a for a in articles if q in (a.title.lower() + " " + a.summary.lower())]
    start = (page - 1) * page_size
    end = start + page_size
    return render_template("news_board.html", articles=articles[start:end], page=page, q=q)


@bp.route("/api/news/refresh", methods=["POST"])
def news_refresh():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))
    with db_session() as s:
        user = s.get(User, user_id)
        if not user or user.plan != "admin":
            return ("forbidden", 403)
    refresh_feeds()
    return jsonify({"status": "ok"})


@bp.route("/api/extract")
async def api_extract():
    url = request.args.get("url", "")
    if not url:
        return jsonify({"error": "url required"}), 400
    data = await extract_url(url)
    return jsonify(data)

