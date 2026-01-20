from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request, session, current_app, redirect, url_for
from werkzeug.utils import secure_filename
from sqlalchemy import select
import re

from ..db import db_session
from ..models import Article, Generation, User
# scoring removed for MVP
from ..news.rss import extract_url, _keywords
import asyncio
from .llm_router import get_provider
from .extractors import (
    extract_text_from_docx_bytes,
    extract_text_from_txt_bytes,
)
from .vision_extractor import extract_markdown_from_pdf_via_vision
from .easyocr_extractor import extract_text_from_pdf_via_easyocr
from .forms import GenerateForm
from .generation_settings import GENERATION_CATEGORIES
from ..limiter import limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timezone

from ..news.article_extractor import extract_full_article, is_cached_content_fresh, smart_truncate_for_llm

bp = Blueprint("gen", __name__, url_prefix="")


def _refund_quota(user_id: str, use_gpt: bool) -> None:
    """Refund one quota unit if generation failed after reservation."""
    try:
        with db_session() as s:
            user = s.execute(
                select(User).where(User.id == user_id).with_for_update()
            ).scalar_one_or_none()
            if user:
                if use_gpt:
                    user.quota_gpt_used = max(0, (user.quota_gpt_used or 0) - 1)
                else:
                    user.quota_claude_used = max(0, (user.quota_claude_used or 0) - 1)
    except Exception:
        pass  # Best effort refund

LENGTH_MIN_CHARS: int = 0

def _detect_language_hint(text: str) -> str | None:
    if re.search(r"[ąčęėįšųūžĄČĘĖĮŠŲŪŽ]", text):
        return "Lithuanian"
    return None


@bp.route("/generate", methods=["GET"])
def generate_form():
    if not session.get("user_id"):
        # Redirect to login with return path
        return redirect(url_for("auth.login", next=request.full_path))
    prefill_url = request.args.get("url", "").strip()
    form = GenerateForm(url=prefill_url)
    return render_template(
        "gen_form_spaceship_v2.html",
        form=form,
        prefill_url=prefill_url,
        generation_categories=GENERATION_CATEGORIES,
    )

@bp.route("/generate_v2", methods=["GET"])
def generate_form_v2():
    prefill_url = request.args.get("url", "").strip()
    return redirect(url_for("gen.generate_form", url=prefill_url))


@bp.route("/api/generate", methods=["POST"])
@limiter.limit("10 per minute")
@limiter.limit("10 per minute", key_func=get_remote_address)
def api_generate():
    form = GenerateForm()
    user_id = session.get("user_id")
    
    # Require login for generation
    if not user_id:
        if request.headers.get('HX-Request'):
            return render_template("gen_results_spaceship.html", variants=[], error="Please log in to generate posts.")
        from flask import flash
        flash("Please log in to generate posts.", "error")
        return redirect(url_for("auth.login", next=request.full_path))
    
    # Determine which model will be used (needed for quota check + provider routing)
    model_choice = (request.form.get("model") or form.model.data or "claude").strip().lower()
    # Normalize model keys coming from the UI (no hardcoding of vendor IDs in the browser)
    if model_choice in {"chatgpt 5.2", "chatgpt-5.2", "gpt-5.2", "gpt5.2", "gpt-5-2", "chatgpt-5-2"}:
        model_choice = "chatgpt-5-2"
    if model_choice in {"claude sonnet 4.5", "claude-sonnet-4.5", "claude-4.5", "sonnet-4.5", "claude-sonnet-4-5"}:
        model_choice = "claude-sonnet-4-5"

    use_gpt = model_choice in {"gpt", "gpt5", "openai", "chatgpt", "gpt-5", "chatgpt-5-2"}
    
    # Atomic quota check and reservation using SELECT FOR UPDATE
    # This prevents race conditions where multiple requests pass quota check simultaneously
    try:
        with db_session() as s:
            # Lock the user row to prevent concurrent modifications
            user = s.execute(
                select(User).where(User.id == user_id).with_for_update()
            ).scalar_one_or_none()
            
            if not user:
                if request.headers.get('HX-Request'):
                    return render_template("gen_results_spaceship.html", variants=[], error="User not found. Please log in again.")
                from flask import flash
                flash("User not found. Please log in again.", "error")
                return redirect(url_for("auth.login"))
            
            # Calculate remaining quota
            left_gpt = max(0, (user.quota_gpt_monthly or 0) - (user.quota_gpt_used or 0))
            left_claude = max(0, (user.quota_claude_monthly or 0) - (user.quota_claude_used or 0))
            
            # Check if user has any quota left
            if (left_gpt + left_claude) <= 0:
                if request.headers.get('HX-Request'):
                    renews_at = None
                    try:
                        renews_at = user.plan_renews_at.strftime("%Y-%m-%d") if user.plan_renews_at else None
                    except Exception:
                        renews_at = None
                    return render_template(
                        "gen_results_spaceship.html",
                        variants=[],
                        error="Monthly quota reached. Upgrade your plan or wait for renewal.",
                        error_code="quota",
                        renews_at=renews_at,
                    )
                from flask import flash
                flash("Monthly quota reached. Upgrade your plan or wait for renewal.", "error")
                return redirect(url_for("main.dashboard"))
            
            # Check specific model quota
            if use_gpt and left_gpt <= 0:
                if request.headers.get('HX-Request'):
                    renews_at = None
                    try:
                        renews_at = user.plan_renews_at.strftime("%Y-%m-%d") if user.plan_renews_at else None
                    except Exception:
                        renews_at = None
                    return render_template(
                        "gen_results_spaceship.html",
                        variants=[],
                        error="ChatGPT quota reached. Try Claude Sonnet instead or upgrade your plan.",
                        error_code="quota",
                        renews_at=renews_at,
                    )
                from flask import flash
                flash("ChatGPT quota reached. Try Claude Sonnet instead or upgrade your plan.", "error")
                return redirect(url_for("gen.generate_form"))
            
            if not use_gpt and left_claude <= 0:
                if request.headers.get('HX-Request'):
                    renews_at = None
                    try:
                        renews_at = user.plan_renews_at.strftime("%Y-%m-%d") if user.plan_renews_at else None
                    except Exception:
                        renews_at = None
                    return render_template(
                        "gen_results_spaceship.html",
                        variants=[],
                        error="Claude quota reached. Try ChatGPT 5.2 instead or upgrade your plan.",
                        error_code="quota",
                        renews_at=renews_at,
                    )
                from flask import flash
                flash("Claude quota reached. Try ChatGPT 5.2 instead or upgrade your plan.", "error")
                return redirect(url_for("gen.generate_form"))
            
            # Reserve quota NOW before generation (prevents race condition)
            if use_gpt:
                user.quota_gpt_used = (user.quota_gpt_used or 0) + 1
            else:
                user.quota_claude_used = (user.quota_claude_used or 0) + 1
            # Commit happens automatically at end of db_session context
    except Exception as e:
        if request.headers.get('HX-Request'):
            return render_template("gen_results_spaceship.html", variants=[], error="Error checking quota. Please try again.")
        from flask import flash
        flash("Error checking quota. Please try again.", "error")
        return redirect(url_for("gen.generate_form"))
    
    # Track if generation succeeds (for potential quota refund on failure)
    generation_succeeded = False
    
    url = (request.form.get("url") or form.url.data or "").strip()
    user_prompt = (request.form.get("prompt") or "").strip()
    article_id = ""  # legacy, removed from UI
    persona = (request.form.get("persona") or form.persona.data or "auto").strip()
    tone = (request.form.get("tone") or form.tone.data or "auto").strip()
    hook_type = (request.form.get("hook_type") or form.hook_type.data or "auto").strip()
    goal = (request.form.get("goal") or getattr(form, "goal", None) and form.goal.data or "auto").strip()  # type: ignore[attr-defined]
    length = (request.form.get("length") or getattr(form, "length", None) and form.length.data or "auto").strip()  # type: ignore[attr-defined]
    ending = (request.form.get("ending") or getattr(form, "ending", None) and form.ending.data or "auto").strip()  # type: ignore[attr-defined]
    emoji = (request.form.get("emoji") or getattr(form, "emoji", None) and form.emoji.data or "no").strip().lower()  # type: ignore[attr-defined]
    language_choice = (request.form.get("language") or getattr(form, "language", None) and form.language.data or "").strip()  # type: ignore[attr-defined]
    model_choice = (request.form.get("model") or form.model.data or "claude").strip().lower()
    if model_choice in {"chatgpt 5.2", "chatgpt-5.2", "gpt-5.2", "gpt5.2", "gpt-5-2", "chatgpt-5-2"}:
        model_choice = "chatgpt-5-2"
    if model_choice in {"claude sonnet 4.5", "claude-sonnet-4.5", "claude-4.5", "sonnet-4.5", "claude-sonnet-4-5"}:
        model_choice = "claude-sonnet-4-5"

    # If Text field has content, prioritize it regardless of mode
    mode = (request.form.get("source_mode") or "text").strip().lower()
    source_text = ""
    direct_text = (request.form.get("text") or "").strip()
    if direct_text:
        source_text = direct_text[:8000]
    selected_article = None
    scraped_keywords: dict[str, float] = {}
    if not source_text:
        # Strict mode routing: only use the selected source
        try:
            debug_enabled = current_app.config.get("FLASK_ENV") != "production" or request.args.get("debug") == "1"
        except Exception:
            debug_enabled = False
        if mode == "url":
            if not url:
                return render_template("gen_results_spaceship.html", variants=[], error="Please enter a URL.")
            with db_session() as s:
                selected_article = s.execute(select(Article).where(Article.url == url)).scalar_one_or_none()
            # Prefer cached full-article text when present and fresh
            if selected_article and getattr(selected_article, "content_text", None) and is_cached_content_fresh(
                getattr(selected_article, "content_extracted_at", None)
            ):
                source_text = smart_truncate_for_llm(getattr(selected_article, "content_text") or "", max_chars=8000)

            # Otherwise extract full article now (best-effort) and cache on the Article row if present
            if not source_text:
                try:
                    data = asyncio.run(extract_full_article(url))
                    content_text = (data.content_text or "").strip()
                    if content_text:
                        source_text = smart_truncate_for_llm(content_text, max_chars=8000)
                        scraped_keywords = _keywords(data.title or "", data.summary or "")
                        if selected_article:
                            try:
                                with db_session() as s:
                                    art = s.get(Article, selected_article.id)
                                    if art:
                                        art.content_text = content_text
                                        art.content_extracted_at = datetime.now(timezone.utc)
                                        art.content_extractor = data.extractor
                            except Exception:
                                pass
                except Exception:
                    # Fall back to legacy title/summary extraction if full-text fails
                    try:
                        data2 = asyncio.run(extract_url(url))
                        title = (data2.get("title") or url).strip()
                        summary = (data2.get("summary") or "").strip()
                        combined = (title + "\n\n" + summary).strip()
                        source_text = combined[:8000]
                        scraped_keywords = _keywords(title, summary)
                    except Exception:
                        return render_template("gen_results_spaceship.html", variants=[], error="Could not fetch content from the URL.")
        elif mode == "text":
            text_val = (request.form.get("text") or form.text.data or "").strip()
            if not text_val:
                return render_template("gen_results_spaceship.html", variants=[], error="Please paste your text.")
            source_text = text_val[:8000]
        else:  # file
            fs = getattr(form.file, "data", None)
            if not (fs and getattr(fs, "filename", "")):
                return render_template("gen_results_spaceship.html", variants=[], error="Please choose a file to upload.")
            try:
                # reset stream and extract via centralized extractor
                if hasattr(fs, "seek"):
                    fs.seek(0)  # type: ignore[attr-defined]
                elif hasattr(fs, "stream") and hasattr(fs.stream, "seek"):
                    fs.stream.seek(0)
            except Exception:
                pass
            filename = getattr(fs, "filename", "") or ""
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            raw_bytes = fs.read() or b""
            text_content = ""
            if ext == "pdf":
                try:
                    # Choose extraction strategy based on config
                    use = (current_app.config.get("PDF_EXTRACTOR", "easyocr") or "easyocr").lower()
                    if use == "easyocr":
                        text_content = extract_text_from_pdf_via_easyocr(
                            raw_bytes,
                            max_pages=int(current_app.config.get("PDF_OCR_MAX_PAGES", 15) or 15),
                            render_scale=float(current_app.config.get("PDF_OCR_RENDER_SCALE", 1.5) or 1.5),
                            timeout_per_page_s=float(current_app.config.get("PDF_OCR_TIMEOUT_PER_PAGE", 8.0) or 8.0),
                        )
                    else:
                        text_content = extract_markdown_from_pdf_via_vision(
                            raw_bytes,
                            max_pages=int(current_app.config.get("PDF_VISION_MAX_PAGES", 12) or 12),
                        )
                except Exception as e:
                    return render_template(
                        "gen_results_spaceship.html",
                        variants=[],
                        error=f"File processing error (pdf): {e}",
                    )
            elif ext == "docx":
                try:
                    text_content = extract_text_from_docx_bytes(raw_bytes)
                except Exception as e:
                    return render_template(
                        "gen_results_spaceship.html",
                        variants=[],
                        error=f"File processing error (docx): {e}",
                    )
            elif ext == "txt":
                try:
                    text_content = extract_text_from_txt_bytes(raw_bytes)
                except Exception as e:
                    return render_template(
                        "gen_results_spaceship.html",
                        variants=[],
                        error=f"File processing error (txt): {e}",
                    )
            else:
                # Fallback try decode
                try:
                    text_content = extract_text_from_txt_bytes(raw_bytes)
                except Exception as e:
                    return render_template(
                        "gen_results_spaceship.html",
                        variants=[],
                        error=f"File processing error (unknown ext): {e}",
                    )
            # Require at least some text
            source_text = (text_content or "").strip()[:8000]
            if len(source_text) == 0:
                preview = (text_content or "")[:500]
                return render_template(
                    "gen_results_spaceship.html",
                    variants=[],
                    error=(
                        "Could not extract readable text from the uploaded file. "
                        f"Got {len(text_content or '')} characters after processing. "
                        "Supported: .txt, .pdf, .docx."
                    ) + (f"\nPreview: {preview}" if preview else ""),
                )

    # We already respected explicit mode; double-check extracted text presence
    if not source_text:
        if request.headers.get('HX-Request'):
            return render_template("gen_results_spaceship.html", variants=[], error="Could not read any content from your input.")
        from flask import flash
        flash("Could not read any content from your input.", "error")
        return redirect(url_for("gen.generate_form"))

    provider_kind = "openai" if model_choice in {"gpt", "gpt5", "openai", "chatgpt", "gpt-5", "chatgpt-5-2"} else "anthropic"
    # Map UI selection to concrete provider model IDs via config (env-overridable)
    if provider_kind == "openai":
        selected_model_id = (current_app.config.get("OPENAI_MODEL_CHATGPT_5_2") or "gpt-5").strip()
    else:
        selected_model_id = (current_app.config.get("ANTHROPIC_MODEL_SONNET_4_5") or "claude-3-7-sonnet-20250219").strip()

    provider = get_provider(provider_kind)
    kw_dict: dict[str, float] = {}
    if selected_article and selected_article.topics:
        kw_dict = dict(selected_article.topics)
    elif scraped_keywords:
        kw_dict = scraped_keywords

    # Truncate
    source_text = (source_text or "").strip()[:8000]

    language_hint = _detect_language_hint(source_text)
    final_language = language_choice or language_hint

    # Adjust max tokens based on requested length
    length_key = (length or "auto").strip().lower()
    if length_key == "short":
        max_tokens = 250
    elif length_key == "long":
        max_tokens = 1600
    elif length_key == "medium":
        max_tokens = 750
    else:
        max_tokens = 900

    # 2-pass: extract grounded facts, then write
    try:
        facts = provider.extract_facts(source_text=source_text, language=language_hint, max_facts=14, model=selected_model_id)
    except Exception:
        facts = []
    if facts:
        try:
            drafted = provider.write_post_from_facts(
                facts=facts,
                persona=persona,
                tone=tone,
                hook_type=hook_type,
                goal=goal,
                length=length,
                ending=ending,
                emoji=emoji,
                user_prompt=user_prompt,
                language=final_language,
                max_tokens=max_tokens,
                model=selected_model_id,
            )
            variants = [drafted]
        except Exception:
            variants = []
    else:
        variants = []
    if not variants:
        variants = provider.generate_post_variants(
        source_text=source_text,
        persona=persona,
        tone=tone,
        n_variants=1,
        max_tokens=max_tokens,
        keywords=list(kw_dict.keys()),
        hook_type=hook_type,
            goal=goal,
            length=length,
            ending=ending,
            emoji=emoji,
            user_prompt=user_prompt,
            language=final_language,
            model=selected_model_id,
        )
    # If the model responded with our sentinel indicating insufficient grounding, return error
    if variants and isinstance(variants[0], str) and variants[0].strip().upper() == "INSUFFICIENT_SOURCE":
        # Refund the reserved quota since generation failed
        _refund_quota(user_id, use_gpt)
        if request.headers.get('HX-Request'):
            return render_template("gen_results_spaceship.html", variants=[], error="The uploaded content doesn't have enough usable text to write a grounded post. Please upload a richer file or paste more text.")
        from flask import flash
        flash("Not enough usable text to generate a grounded post. Try a richer source.", "error")
        return redirect(url_for("gen.generate_form"))
    
    # If no variants were generated at all, refund quota
    if not variants:
        _refund_quota(user_id, use_gpt)
        if request.headers.get('HX-Request'):
            return render_template("gen_results_spaceship.html", variants=[], error="Failed to generate content. Please try again.")
        from flask import flash
        flash("Failed to generate content. Please try again.", "error")
        return redirect(url_for("gen.generate_form"))

    # MVP: no scoring; just pass strings to template
    results = variants
    
    # Mark generation as successful (quota was already reserved)
    generation_succeeded = True

    # Persist the generated drafts
    gen_rows: list[tuple[str, str]] = []
    try:
        with db_session() as s:
            for v in results:
                g = Generation(
                    user_id=user_id,
                    article_id=(selected_article.id if selected_article else None),
                    model=selected_model_id,
                    prompt=(
                        f"persona={persona}, tone={tone}, hook_type={hook_type}, "
                        f"goal={goal}, length={length}, ending={ending}, emoji={emoji}, language={final_language}, "
                        f"user_prompt={user_prompt[:160]}"
                    ),
                    draft_text=v,
                    persona=persona,
                    tone=tone,
                )
                s.add(g)
                s.flush()
                gen_rows.append((g.id, v))
            # Note: Quota was already incremented atomically at the start
            # If we generated more than 1 variant, we need to add the extra usage
            extra_generations = len(results) - 1
            if extra_generations > 0:
                user = s.get(User, user_id)
                if user:
                    if use_gpt:
                        user.quota_gpt_used = (user.quota_gpt_used or 0) + extra_generations
                    else:
                        user.quota_claude_used = (user.quota_claude_used or 0) + extra_generations
            
            # Increment generation_count for the article if it was used
            if selected_article:
                article_to_update = s.get(Article, selected_article.id)
                if article_to_update:
                    article_to_update.generation_count = (article_to_update.generation_count or 0) + 1
    except Exception as e:
        # Database error during persistence - refund the reserved quota
        _refund_quota(user_id, use_gpt)
        if request.headers.get('HX-Request'):
            return render_template("gen_results_spaceship.html", variants=[], error="Failed to save generated content. Please try again.")
        from flask import flash
        flash("Failed to save generated content. Please try again.", "error")
        return redirect(url_for("gen.generate_form"))

    if not gen_rows:
        gen_rows = [("", v) for v in results]

    # Lightweight profile payload for LinkedIn-like preview UI
    user_profile: dict[str, str] = {}
    try:
        with db_session() as s:
            u = s.get(User, user_id)
            if u:
                full_name = (getattr(u, "full_name", None) or "").strip()
                display_name = (getattr(u, "display_name", None) or "").strip()
                email = (getattr(u, "email", None) or "").strip()
                profile_image_url = (getattr(u, "profile_image_url", None) or "").strip()
                name = full_name or display_name or (email.split("@", 1)[0] if email else "")
                user_profile = {
                    "name": name,
                    "profile_image_url": profile_image_url,
                }
    except Exception:
        user_profile = {}

    # HTMX path returns fragment; non-HTMX redirects (PRG) to avoid resubmission dialogs
    if request.headers.get('HX-Request'):
        return render_template(
            "gen_results_spaceship.html",
            variants=results,
            gen_rows=gen_rows,
            user_profile=user_profile,
        )

    from flask import flash
    flash("Draft(s) generated successfully.", "success")
    return redirect(url_for("main.dashboard"))

