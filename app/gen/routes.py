from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request, session, current_app, redirect, url_for
from sqlalchemy import select

from ..db import db_session
from ..models import Article, Generation, User
from .scoring import score_text
from ..news.rss import extract_url, _keywords
import asyncio
from .llm_router import get_provider
from .forms import GenerateForm

bp = Blueprint("gen", __name__, url_prefix="")


@bp.route("/generate", methods=["GET"])
def generate_form():
    prefill_url = request.args.get("url", "").strip()
    # Redirect canonical /generate to the new v2 page to avoid any stale caches
    return redirect(url_for("gen.generate_form_v2", url=prefill_url))

@bp.route("/generate_v2", methods=["GET"])
def generate_form_v2():
    prefill_url = request.args.get("url", "").strip()
    form = GenerateForm(url=prefill_url)
    return render_template("gen_form_spaceship_v2.html", form=form, prefill_url=prefill_url)


@bp.route("/api/generate", methods=["POST"])
def api_generate():
    form = GenerateForm()
    if not form.validate_on_submit():
        return render_template("gen_results_spaceship.html", variants=[], error=" ".join([*sum(form.errors.values(), [])]))
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "login required"}), 401
    url = (form.url.data or "").strip()
    article_id = ""  # legacy, removed from UI
    persona = form.persona.data or "PM"
    tone = form.tone.data or "analytical"
    hook_type = (form.hook_type.data or "auto").strip()
    model_choice = (form.model.data or "claude").strip().lower()

    source_text = ""
    selected_article = None
    scraped_keywords: dict[str, float] = {}
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
            source_text = (form.text.data or "").strip()
            # If URL provided but not found in DB and no manual text, try scraping now
            if not source_text and url:
                try:
                    data = asyncio.run(extract_url(url))
                    title = (data.get("title") or url).strip()
                    summary = (data.get("summary") or "").strip()
                    combined = (title + "\n\n" + summary).strip()
                    source_text = combined[:8000]
                    scraped_keywords = _keywords(title, summary)
                except Exception:
                    # Best-effort; leave source_text empty if scraping fails
                    pass

    # Enforce mutual exclusivity: one of (url or text), not both
    if url and (form.text.data or "").strip():
        return render_template("gen_results_spaceship.html", variants=[], error="Please provide either a URL or your own text — not both.")
    if not (url or source_text):
        return render_template("gen_results_spaceship.html", variants=[], error="Please provide a URL or paste your text.")

    provider = get_provider("openai" if model_choice in {"gpt", "gpt5", "openai", "chatgpt", "gpt-5"} else "anthropic")
    kw_dict: dict[str, float] = {}
    if selected_article and selected_article.topics:
        kw_dict = dict(selected_article.topics)
    elif scraped_keywords:
        kw_dict = scraped_keywords

    # Truncate manual text as well
    if not url and source_text:
        source_text = source_text[:8000]

    variants = provider.generate_post_variants(
        source_text=source_text,
        persona=persona,
        tone=tone,
        n_variants=3,
        max_tokens=400,
        keywords=list(kw_dict.keys()),
        hook_type=hook_type,
    )

    # MVP: no scoring; just pass strings to template
    results = variants

    with db_session() as s:
        for v in results:
            g = Generation(
                user_id=user_id,
                article_id=(selected_article.id if selected_article else None),
                model=("gpt-5" if model_choice in {"gpt", "gpt5", "openai", "chatgpt", "gpt-5"} else "claude-3-5-sonnet-20240620"),
                prompt=f"persona={persona}, tone={tone}, hook_type={hook_type}",
                draft_text=v,
                persona=persona,
                tone=tone,
            )
            s.add(g)

    return render_template("gen_results_spaceship.html", variants=results)

