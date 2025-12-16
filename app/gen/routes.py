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
from ..limiter import limiter
from flask_limiter.util import get_remote_address

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
    return render_template("gen_form_spaceship_v2.html", form=form, prefill_url=prefill_url)

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
    
    # Determine which model will be used (needed for quota check)
    model_choice = (form.model.data or "claude").strip().lower()
    use_gpt = model_choice in {"gpt", "gpt5", "openai", "chatgpt", "gpt-5"}
    
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
                    return render_template("gen_results_spaceship.html", variants=[], error="Monthly quota reached. Upgrade your plan or wait for renewal.")
                from flask import flash
                flash("Monthly quota reached. Upgrade your plan or wait for renewal.", "error")
                return redirect(url_for("main.dashboard"))
            
            # Check specific model quota
            if use_gpt and left_gpt <= 0:
                if request.headers.get('HX-Request'):
                    return render_template("gen_results_spaceship.html", variants=[], error="GPT quota reached. Try Claude instead or upgrade your plan.")
                from flask import flash
                flash("GPT quota reached. Try Claude instead or upgrade your plan.", "error")
                return redirect(url_for("gen.generate_form"))
            
            if not use_gpt and left_claude <= 0:
                if request.headers.get('HX-Request'):
                    return render_template("gen_results_spaceship.html", variants=[], error="Claude quota reached. Try GPT instead or upgrade your plan.")
                from flask import flash
                flash("Claude quota reached. Try GPT instead or upgrade your plan.", "error")
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
    
    url = (form.url.data or "").strip()
    article_id = ""  # legacy, removed from UI
    persona = form.persona.data or "PM"
    tone = form.tone.data or "analytical"
    hook_type = (form.hook_type.data or "auto").strip()
    model_choice = (form.model.data or "claude").strip().lower()

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
            if selected_article:
                source_text = (selected_article.title + "\n\n" + selected_article.summary).strip()[:8000]
            if not source_text:
                try:
                    data = asyncio.run(extract_url(url))
                    title = (data.get("title") or url).strip()
                    summary = (data.get("summary") or "").strip()
                    combined = (title + "\n\n" + summary).strip()
                    source_text = combined[:8000]
                    scraped_keywords = _keywords(title, summary)
                except Exception:
                    return render_template("gen_results_spaceship.html", variants=[], error="Could not fetch content from the URL.")
        elif mode == "text":
            text_val = (form.text.data or "").strip()
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

    provider = get_provider("openai" if model_choice in {"gpt", "gpt5", "openai", "chatgpt", "gpt-5"} else "anthropic")
    kw_dict: dict[str, float] = {}
    if selected_article and selected_article.topics:
        kw_dict = dict(selected_article.topics)
    elif scraped_keywords:
        kw_dict = scraped_keywords

    # Truncate
    source_text = (source_text or "").strip()[:8000]

    language_hint = _detect_language_hint(source_text)

    # 2-pass: extract grounded facts, then write
    try:
        facts = provider.extract_facts(source_text=source_text, language=language_hint, max_facts=14)
    except Exception:
        facts = []
    if facts:
        try:
            drafted = provider.write_post_from_facts(
                facts=facts,
                persona=persona,
                tone=tone,
                hook_type=hook_type,
                language=language_hint,
                max_tokens=600,
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
        max_tokens=600,
        keywords=list(kw_dict.keys()),
        hook_type=hook_type,
            language=language_hint,
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
    with db_session() as s:
        for v in results:
            g = Generation(
                user_id=user_id,
                article_id=(selected_article.id if selected_article else None),
                model=("gpt-5" if use_gpt else "claude-3-5-sonnet-20240620"),
                prompt=f"persona={persona}, tone={tone}, hook_type={hook_type}",
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

    if not gen_rows:
        gen_rows = [("", v) for v in results]

    # HTMX path returns fragment; non-HTMX redirects (PRG) to avoid resubmission dialogs
    if request.headers.get('HX-Request'):
        return render_template("gen_results_spaceship.html", variants=results, gen_rows=gen_rows)

    from flask import flash
    flash("Draft(s) generated successfully.", "success")
    return redirect(url_for("main.dashboard"))

