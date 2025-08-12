from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
import re
from sqlalchemy import select

from ..db import db_session
from ..models import Article, User, Category, ArticleCategory, UserNewsPreference
from .rss import refresh_feeds, extract_url

bp = Blueprint("news", __name__, url_prefix="")


def _extract_img_from_html(summary: str) -> str | None:
    if not summary:
        return None
    try:
        # Look for <img ... src="...">
        m = re.search(r"<img[^>]+src=\"([^\"]+)\"", summary, flags=re.IGNORECASE)
        if m:
            return m.group(1)
        # Sometimes data-src is used
        m = re.search(r"<img[^>]+data-src=\"([^\"]+)\"", summary, flags=re.IGNORECASE)
        if m:
            return m.group(1)
    except Exception:
        return None
    return None


def _backfill_article_images(articles: list[Article]) -> None:
    # Best-effort: if an article has no image_url but summary contains <img>, persist it
    if not articles:
        return
    with db_session() as s:
        for a in articles:
            if not getattr(a, "image_url", None) and getattr(a, "summary", None):
                url = _extract_img_from_html(a.summary)
                if url:
                    # persist
                    obj = s.get(Article, a.id)
                    if obj:
                        obj.image_url = url


@bp.route("/news")
def news_board():
    page = int(request.args.get("page", 1))
    q = request.args.get("q", "").strip().lower()
    page_size = 20
    # Support both ?categories=slug,slug2 and repeated ?categories=slug params
    selected_list = request.args.getlist("categories")
    if selected_list:
        selected_slugs = [s for s in selected_list if s]
    else:
        selected = request.args.get("categories", "").strip()
        selected_slugs = [s for s in selected.split(",") if s]
    with db_session() as s:
        # base articles: only those with images
        stmt = (
            select(Article)
            .where(Article.deleted_at.is_(None))
            .where(Article.image_url.isnot(None))
            .order_by(Article.created_at.desc())
        )
        articles = s.execute(stmt).scalars().all()
        # categories for UI
        cats = s.execute(select(Category).order_by(Category.name.asc())).scalars().all()
        # filter by query
        if q:
            articles = [a for a in articles if q in (a.title.lower() + " " + a.summary.lower())]
        # filter by categories
        if selected_slugs:
            # find article ids that have any of selected categories
            cat_ids = [c.id for c in cats if c.slug in selected_slugs]
            if cat_ids:
                art_ids = set(
                    rid for rid, in s.execute(
                        select(ArticleCategory.article_id).where(ArticleCategory.category_id.in_(cat_ids))
                    )
                )
                articles = [a for a in articles if a.id in art_ids]
    start = (page - 1) * page_size
    end = start + page_size
    page_articles = articles[start:end]

    # Best-effort backfill of missing images for visible page
    _backfill_article_images(page_articles)

    return render_template(
        "news_board_spaceship.html",
        articles=page_articles,
        page=page,
        q=q,
        categories=cats,
        selected_slugs=selected_slugs,
    )


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


@bp.route("/api/news/preferences", methods=["POST"])
def save_news_preferences():
    user_id = session.get("user_id")
    if not user_id:
        return ("unauthorized", 401)
    slugs = request.json.get("slugs", []) if request.is_json else request.form.get("slugs", "").split(",")
    slugs = [s for s in slugs if s]
    with db_session() as s:
        pref = s.execute(select(UserNewsPreference).where(UserNewsPreference.user_id == user_id)).scalar_one_or_none()
        payload = {"slugs": slugs}
        if pref is None:
            pref = UserNewsPreference(user_id=user_id, categories=payload)
            s.add(pref)
        else:
            pref.categories = payload
    return jsonify({"ok": True})


@bp.route("/api/extract")
async def api_extract():
    url = request.args.get("url", "")
    if not url:
        return jsonify({"error": "url required"}), 400
    data = await extract_url(url)
    return jsonify(data)

