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

bp = Blueprint("gen", __name__, url_prefix="")

LENGTH_MIN_CHARS: int = 0

def _detect_language_hint(text: str) -> str | None:
    if re.search(r"[ąčęėįšųūžĄČĘĖĮŠŲŪŽ]", text):
        return "Lithuanian"
    return None


@bp.route("/generate", methods=["GET"])
def generate_form():
    if not session.get("user_id"):
        # Redirect to login with return path
        return redirect(url_for("auth.login") + "?next=" + url_for("gen.generate_form"))
    prefill_url = request.args.get("url", "").strip()
    form = GenerateForm(url=prefill_url)
    return render_template("gen_form_spaceship_v2.html", form=form, prefill_url=prefill_url)

@bp.route("/generate_v2", methods=["GET"])
def generate_form_v2():
    prefill_url = request.args.get("url", "").strip()
    return redirect(url_for("gen.generate_form", url=prefill_url))


@bp.route("/api/generate", methods=["POST"])
def api_generate():
    form = GenerateForm()
    user_id = session.get("user_id")
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
        return render_template("gen_results_spaceship.html", variants=[], error="Could not read any content from your input.")

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
        return render_template("gen_results_spaceship.html", variants=[], error="The uploaded content doesn’t have enough usable text to write a grounded post. Please upload a richer file or paste more text.")

    # MVP: no scoring; just pass strings to template
    results = variants

    # Persist only if a user is logged in
    if user_id:
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

