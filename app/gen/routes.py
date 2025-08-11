from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request, session, current_app
from sqlalchemy import select

from ..db import db_session
from ..models import Article, Generation, User
from .llm_router import get_provider
from .scoring import score_text

bp = Blueprint("gen", __name__, url_prefix="")


@bp.route("/generate")
def generate_form():
    with db_session() as s:
        articles = (
            s.execute(
                select(Article)
                .where(Article.deleted_at.is_(None))
                .order_by(Article.created_at.desc())
                .limit(20)
            )
            .scalars()
            .all()
        )
    return render_template("gen_form.html", articles=articles)


@bp.route("/api/generate", methods=["POST"])
def api_generate():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "login required"}), 401
    url = request.form.get("url", "").strip()
    article_id = request.form.get("article_id", "").strip()
    persona = request.form.get("persona", "PM")
    tone = request.form.get("tone", "analytical")

    source_text = ""
    selected_article = None
    with db_session() as s:
        if article_id:
            selected_article = s.get(Article, article_id)
            if selected_article and selected_article.deleted_at is not None:
                selected_article = None
        elif url:
            selected_article = s.execute(select(Article).where(Article.url == url)).scalar_one_or_none()
        if selected_article:
            source_text = selected_article.title + "\n\n" + selected_article.summary
        else:
            source_text = request.form.get("text", "").strip()

    provider = get_provider()
    keywords = list((selected_article.topics.keys() if selected_article else []) )
    variants = provider.generate_post_variants(
        source_text=source_text,
        persona=persona,
        tone=tone,
        n_variants=3,
        max_tokens=400,
        keywords=keywords,
    )

    scored = []
    for v in variants:
        s, breakdown = score_text(v, today_keywords=(selected_article.topics if selected_article else {}))
        scored.append((v, s, breakdown))

    with db_session() as s:
        for v, sscore, breakdown in scored:
            g = Generation(
                user_id=user_id,
                article_id=(selected_article.id if selected_article else None),
                model=current_app.config.get("LLM_PROVIDER", "anthropic"),
                prompt=f"persona={persona}, tone={tone}",
                draft_text=v,
                score=sscore,
                score_breakdown=breakdown,
            )
            s.add(g)

    return render_template("gen_results.html", variants=scored)

