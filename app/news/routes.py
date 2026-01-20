"""
News routes - handles category selection and article browsing.

Routes:
- GET /news - Category selection page (8 cards)
- GET /news/<slug> - Articles for specific category
- POST /api/news/refresh/<slug> - Refresh feeds for one category (admin only)
"""
from __future__ import annotations

from datetime import datetime, timezone
from flask import Blueprint, abort, jsonify, redirect, render_template, request, session, url_for, flash

from ..db import db_session
from ..models import User, UserNewsPreference, Category as DbCategory, ArticleCategory as DbArticleCategory
from .services import CategoryService, ArticleService
from .feeds_config import get_category_by_slug as get_category_config
from sqlalchemy import select

bp = Blueprint("news", __name__, url_prefix="")


def _safe_int(value, default: int = 1) -> int:
    """Safely parse an integer from request args."""
    try:
        return max(1, int(value))
    except (ValueError, TypeError):
        return default


def _parse_as_of(value: str | None) -> datetime:
    """
    Parse an ISO8601 timestamp used to freeze pagination ("snapshot pagination").

    Accepts both "+00:00" and "Z" suffixes. Falls back to 'now' if invalid/missing.
    Always returns timezone-aware UTC datetime.
    """
    if not value:
        return datetime.now(timezone.utc)
    raw = (value or "").strip()
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _require_login():
    """Redirect to login (with return path) if user isn't authenticated."""
    if session.get("user_id"):
        return None
    flash("Please log in to access Content Ideas.", "error")
    return redirect(url_for("auth.login", next=request.full_path))

def _get_user_news_pref(user_id: str) -> UserNewsPreference | None:
    with db_session() as s:
        return s.execute(
            select(UserNewsPreference).where(UserNewsPreference.user_id == user_id)
        ).scalar_one_or_none()


def _save_user_news_pref(
    user_id: str,
    slugs: list[str],
    *,
    show_only_my_categories: bool,
    onboarded: bool = True,
) -> None:
    payload = {"slugs": slugs, "onboarded": bool(onboarded)}
    with db_session() as s:
        pref = s.execute(
            select(UserNewsPreference).where(UserNewsPreference.user_id == user_id)
        ).scalar_one_or_none()
        if pref is None:
            pref = UserNewsPreference(
                user_id=user_id,
                categories=payload,
                show_only_my_categories=bool(show_only_my_categories),
            )
            s.add(pref)
        else:
            pref.categories = payload
            pref.show_only_my_categories = bool(show_only_my_categories)


@bp.route("/news/topics", methods=["GET", "POST"])
def news_topics():
    """Pick or edit preferred news categories (one-time onboarding + anytime edits)."""
    maybe_redirect = _require_login()
    if maybe_redirect:
        return maybe_redirect
    user_id = session.get("user_id") or ""

    categories = CategoryService.get_all_categories()
    slug_to_name = {c["slug"]: c["name"] for c in categories}

    pref = _get_user_news_pref(user_id)
    existing = (pref.categories or {}) if pref else {}
    selected_slugs = list(existing.get("slugs") or [])
    selected_slugs = [s for s in selected_slugs if s in slug_to_name]
    show_only = bool(getattr(pref, "show_only_my_categories", False)) if pref else False

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        if action == "skip":
            _save_user_news_pref(
                user_id,
                [],
                show_only_my_categories=False,
                onboarded=True,
            )
            return redirect(url_for("news.my_feed"))

        slugs = request.form.getlist("slugs")
        slugs = [s for s in slugs if s in slug_to_name]
        slugs = list(dict.fromkeys(slugs))  # preserve order, dedupe
        _save_user_news_pref(
            user_id,
            slugs,
            show_only_my_categories=bool(slugs),
            onboarded=True,
        )
        return redirect(url_for("news.my_feed"))

    mode = (request.args.get("mode") or "edit").strip().lower()
    return render_template(
        "news_topics_picker.html",
        categories=categories,
        selected_slugs=selected_slugs,
        show_only_my_categories=show_only,
        mode=mode,
    )


@bp.route("/news", methods=["GET"])
def my_feed():
    """
    Personalized aggregated feed across preferred categories.
    If the user hasn't onboarded yet, prompt for topics once.
    """
    maybe_redirect = _require_login()
    if maybe_redirect:
        return maybe_redirect

    user_id = session.get("user_id") or ""
    categories = CategoryService.get_all_categories()
    slug_to_cat = {c["slug"]: c for c in categories}

    pref = _get_user_news_pref(user_id)
    pref_cats = (pref.categories or {}) if pref else {}
    onboarded = bool(pref_cats.get("onboarded")) if pref else False

    # First-time flow: ask once.
    if not onboarded:
        return redirect(url_for("news.news_topics", mode="onboarding"))

    selected_slugs = list(pref_cats.get("slugs") or [])
    selected_slugs = [s for s in selected_slugs if s in slug_to_cat]
    show_only = bool(getattr(pref, "show_only_my_categories", False)) if pref else False

    page = _safe_int(request.args.get("page"), 1)
    query = (request.args.get("q") or "").strip()
    active_cat = (request.args.get("cat") or "").strip()
    if active_cat and active_cat not in slug_to_cat:
        active_cat = ""
    as_of_dt = _parse_as_of(request.args.get("as_of"))
    as_of = as_of_dt.isoformat()

    page_size = 20

    effective_slugs: list[str] = selected_slugs if (show_only and selected_slugs) else []
    if active_cat:
        effective_slugs = [active_cat]
    articles, total_count, total_pages = ArticleService.get_articles_for_categories(
        category_slugs=effective_slugs,
        page=page,
        page_size=page_size,
        query=query or None,
        as_of=as_of_dt,
    )

    selected_categories = [slug_to_cat[s] for s in selected_slugs if s in slug_to_cat]

    # Build per-article category pills (all categories the article belongs to)
    article_categories_map: dict[str, list[dict]] = {}
    try:
        article_ids = [a.id for a in articles]
        if article_ids:
            with db_session() as s:
                rows = s.execute(
                    select(
                        DbArticleCategory.article_id,
                        DbCategory.slug,
                        DbCategory.name,
                    )
                    .join(DbCategory, DbCategory.id == DbArticleCategory.category_id)
                    .where(DbArticleCategory.article_id.in_(article_ids))
                ).all()
            for article_id, cat_slug, cat_name in rows:
                article_categories_map.setdefault(str(article_id), []).append(
                    {"slug": cat_slug, "name": cat_name}
                )
            # keep stable order by name
            for k in list(article_categories_map.keys()):
                article_categories_map[k] = sorted(article_categories_map[k], key=lambda x: x["name"])
    except Exception:
        article_categories_map = {}

    return render_template(
        "news_board_spaceship.html",
        articles=articles,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        q=query,
        as_of=as_of,
        show_only_my_categories=show_only,
        selected_slugs=selected_slugs,
        selected_categories=selected_categories,
        active_cat=active_cat,
        article_categories_map=article_categories_map,
    )


@bp.route("/news/<slug>")
def category_detail(slug: str):
    """
    Display articles for a specific category with pagination.
    
    Args:
        slug: Category slug (e.g., 'technology-ai-software')
    """
    maybe_redirect = _require_login()
    if maybe_redirect:
        return maybe_redirect
    # Validate category exists
    category = CategoryService.get_category_by_slug(slug)
    if not category:
        abort(404)
    
    # Parse pagination, search, and source filter params
    page = _safe_int(request.args.get("page"), 1)
    query = request.args.get("q", "").strip()
    source_filter = request.args.get("source", "").strip() or None
    as_of_dt = _parse_as_of(request.args.get("as_of"))
    as_of = as_of_dt.isoformat()

    page_size = 20

    # Get available sources for this category (for sidebar)
    sources = ArticleService.get_sources_for_category(slug)
    
    # Get articles (with optional search and source filter)
    if query:
        articles, total_count, total_pages = ArticleService.search_articles_in_category(
            category_slug=slug,
            query=query,
            page=page,
            page_size=page_size,
            source_filter=source_filter,
            as_of=as_of_dt,
        )
    else:
        articles, total_count, total_pages = ArticleService.get_articles_for_category(
            category_slug=slug,
            page=page,
            page_size=page_size,
            source_filter=source_filter,
            as_of=as_of_dt,
        )
    
    # Get most generated articles for "Most Popular" section
    most_generated_articles = ArticleService.get_most_generated_articles(slug)
    
    return render_template(
        "news_category_detail.html",
        category=category,
        articles=articles,
        sources=sources,
        current_source=source_filter,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        query=query,
        as_of=as_of,
        most_generated_articles=most_generated_articles,
    )


@bp.route("/api/news/refresh", methods=["POST"])
def news_refresh_all():
    """
    Refresh all RSS feeds (admin only).
    
    This triggers a refresh of all category feeds.
    """
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))
    
    with db_session() as s:
        user = s.get(User, user_id)
        if not user or user.plan != "admin":
            return ("forbidden", 403)
    
    # Import here to avoid circular imports
    from .rss import refresh_all_feeds
    
    try:
        count = refresh_all_feeds()
        return jsonify({"status": "ok", "articles_added": count})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/api/news/refresh/<slug>", methods=["POST"])
def news_refresh_category(slug: str):
    """
    Refresh RSS feeds for a specific category (admin only).
    
    Args:
        slug: Category slug to refresh
    """
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))
    
    with db_session() as s:
        user = s.get(User, user_id)
        if not user or user.plan != "admin":
            return ("forbidden", 403)
    
    # Validate category exists
    category_config = get_category_config(slug)
    if not category_config:
        return jsonify({"status": "error", "message": "Category not found"}), 404
    
    # Import here to avoid circular imports
    from .rss import refresh_category_feeds
    
    try:
        count = refresh_category_feeds(slug)
        return jsonify({"status": "ok", "category": slug, "articles_added": count})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/api/news/preferences", methods=["POST"])
def save_news_preferences():
    """Save user's preferred news categories (for future personalization)."""

    user_id = session.get("user_id")
    if not user_id:
        return ("unauthorized", 401)

    if request.is_json:
        slugs = request.json.get("slugs", []) or []
        show_only = bool(request.json.get("show_only_my_categories", False))
        onboarded = bool(request.json.get("onboarded", True))
    else:
        raw = (request.form.get("slugs") or "").strip()
        slugs = [s for s in raw.split(",") if s]
        show_only = (request.form.get("show_only_my_categories") or "").strip().lower() in {"1", "true", "yes", "on"}
        onboarded = (request.form.get("onboarded") or "").strip().lower() not in {"0", "false", "no"}

    categories = CategoryService.get_all_categories()
    allowed = {c["slug"] for c in categories}
    slugs = [s for s in slugs if s in allowed]
    slugs = list(dict.fromkeys(slugs))

    # If user has no slugs, forcing show_only doesn't make sense.
    if not slugs:
        show_only = False

    _save_user_news_pref(
        user_id,
        slugs,
        show_only_my_categories=show_only,
        onboarded=onboarded,
    )

    return jsonify({"ok": True, "slugs": slugs, "show_only_my_categories": show_only, "onboarded": onboarded})


@bp.route("/api/extract")
async def api_extract():
    """Extract content from a URL (for generation preview)."""
    from .article_extractor import extract_full_article
    
    url = request.args.get("url", "")
    if not url:
        return jsonify({"error": "url required"}), 400
    
    try:
        data = await extract_full_article(url)
        return jsonify(
            {
                "title": data.title,
                "summary": data.summary,
                "content_text": data.content_text,
                "word_count": data.word_count,
                "final_url": data.final_url,
                "extractor": data.extractor,
            }
        )
    except Exception as e:
        return jsonify({"error": "extract_failed", "message": str(e)}), 400
