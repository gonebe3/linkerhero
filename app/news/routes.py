"""
News routes - handles category selection and article browsing.

Routes:
- GET /news - Category selection page (8 cards)
- GET /news/<slug> - Articles for specific category
- POST /api/news/refresh/<slug> - Refresh feeds for one category (admin only)
"""
from __future__ import annotations

from flask import Blueprint, abort, jsonify, redirect, render_template, request, session, url_for

from ..db import db_session
from ..models import User
from .services import CategoryService, ArticleService
from .feeds_config import get_category_by_slug as get_category_config

bp = Blueprint("news", __name__, url_prefix="")


def _safe_int(value, default: int = 1) -> int:
    """Safely parse an integer from request args."""
    try:
        return max(1, int(value))
    except (ValueError, TypeError):
        return default


@bp.route("/news")
def news_categories():
    """
    Category selection page - displays all 8 categories as cards.
    
    User clicks a category to see articles in that category.
    """
    categories = CategoryService.get_all_categories()
    total_articles = ArticleService.get_total_article_count()
    return render_template("news_categories.html", categories=categories, total_articles=total_articles)


@bp.route("/news/<slug>")
def category_detail(slug: str):
    """
    Display articles for a specific category with pagination.
    
    Args:
        slug: Category slug (e.g., 'technology-ai-software')
    """
    # Validate category exists
    category = CategoryService.get_category_by_slug(slug)
    if not category:
        abort(404)
    
    # Parse pagination, search, source filter, and free/paid filter params
    page = _safe_int(request.args.get("page"), 1)
    query = request.args.get("q", "").strip()
    source_filter = request.args.get("source", "").strip() or None
    # Default to showing all (both free and paid), "free" means hide paid
    show_paid = request.args.get("filter", "all") != "free"
    current_filter = "free" if not show_paid else "all"
    page_size = 20
    
    # Get free/paid counts for the filter toggle
    paid_free_counts = ArticleService.get_paid_free_counts(slug)
    
    # Get available sources for this category (for tabs)
    sources = ArticleService.get_sources_for_category(slug, show_paid=show_paid)
    
    # Get articles (with optional search and source filter)
    if query:
        articles, total_count, total_pages = ArticleService.search_articles_in_category(
            category_slug=slug,
            query=query,
            page=page,
            page_size=page_size,
            source_filter=source_filter,
            show_paid=show_paid,
        )
    else:
        articles, total_count, total_pages = ArticleService.get_articles_for_category(
            category_slug=slug,
            page=page,
            page_size=page_size,
            source_filter=source_filter,
            show_paid=show_paid,
        )
    
    # Get most generated articles for "Most Popular" section
    most_generated_articles = ArticleService.get_most_generated_articles(slug)
    
    return render_template(
        "news_category_detail.html",
        category=category,
        articles=articles,
        sources=sources,
        current_source=source_filter,
        current_filter=current_filter,
        paid_free_counts=paid_free_counts,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        query=query,
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
    from ..models import UserNewsPreference
    from sqlalchemy import select
    
    user_id = session.get("user_id")
    if not user_id:
        return ("unauthorized", 401)
    
    slugs = request.json.get("slugs", []) if request.is_json else request.form.get("slugs", "").split(",")
    slugs = [s for s in slugs if s]
    
    with db_session() as s:
        pref = s.execute(
            select(UserNewsPreference).where(UserNewsPreference.user_id == user_id)
        ).scalar_one_or_none()
        
        payload = {"slugs": slugs}
        if pref is None:
            pref = UserNewsPreference(user_id=user_id, categories=payload)
            s.add(pref)
        else:
            pref.categories = payload
    
    return jsonify({"ok": True})


@bp.route("/api/extract")
async def api_extract():
    """Extract content from a URL (for generation preview)."""
    from .rss import extract_url
    
    url = request.args.get("url", "")
    if not url:
        return jsonify({"error": "url required"}), 400
    
    data = await extract_url(url)
    return jsonify(data)
