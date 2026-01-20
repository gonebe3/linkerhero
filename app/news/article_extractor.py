"""
Full-article extraction for generation.

Goals:
- SSRF-safe URL fetching (reuses validate_url)
- Robust full text extraction (trafilatura)
- Hard limits (timeout/max bytes/max chars) to keep generation fast & safe
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Any

import httpx
from flask import current_app

from .url_validator import validate_url


@dataclass(frozen=True)
class ArticleExtractionResult:
    url: str
    final_url: str
    title: str
    summary: str
    content_text: str
    word_count: int
    extractor: str


def _clean_text(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    # Normalize whitespace
    s = s.replace("\r", "\n")
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"[ \t\x0b\x0c]+", " ", s)
    return s.strip()


def smart_truncate_for_llm(text: str, *, max_chars: int = 8000) -> str:
    """
    Truncate while preserving both beginning and later context.
    Avoids feeding the model only the headline/lede.
    """
    t = _clean_text(text)
    if len(t) <= max_chars:
        return t
    if max_chars < 800:
        return t[:max_chars]

    # Keep: start + middle + end
    start_len = int(max_chars * 0.45)
    mid_len = int(max_chars * 0.15)
    end_len = max_chars - start_len - mid_len - 80

    start = t[:start_len].rstrip()
    mid_start = max(0, (len(t) // 2) - (mid_len // 2))
    mid = t[mid_start : mid_start + mid_len].strip()
    end = t[-end_len:].lstrip() if end_len > 0 else ""

    sep = "\n\n[...snip...]\n\n"
    out = (start + sep + mid + sep + end).strip()
    return out[:max_chars]


def _cfg_float(key: str, default: float) -> float:
    try:
        return float(current_app.config.get(key, default))
    except Exception:
        return default


def _cfg_int(key: str, default: int) -> int:
    try:
        return int(current_app.config.get(key, default))
    except Exception:
        return default


async def extract_full_article(url: str) -> ArticleExtractionResult:
    """
    Fetch + extract full article text from a URL (SSRF-safe).

    Returns an ArticleExtractionResult. Raises ValueError on validation failures.
    """
    is_valid, err = validate_url(url)
    if not is_valid:
        raise ValueError(err or "unsafe url")

    timeout_s = _cfg_float("ARTICLE_EXTRACT_TIMEOUT_S", 15.0)
    max_bytes = _cfg_int("ARTICLE_EXTRACT_MAX_BYTES", 2 * 1024 * 1024)
    max_chars = _cfg_int("ARTICLE_EXTRACT_MAX_CHARS", 20000)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    content_bytes = bytearray()
    final_url = url

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(timeout_s, connect=timeout_s),
        headers=headers,
    ) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            final_url = str(resp.url)
            # Validate redirected final URL too (SSRF hardening)
            ok2, err2 = validate_url(final_url)
            if not ok2:
                raise ValueError(err2 or "unsafe redirected url")

            async for chunk in resp.aiter_bytes():
                if not chunk:
                    continue
                content_bytes.extend(chunk)
                if len(content_bytes) > max_bytes:
                    break

    html = bytes(content_bytes)
    if not html:
        raise ValueError("empty response")

    # Extract with trafilatura from HTML (avoid its internal fetching; we already validated/fetched)
    try:
        import trafilatura  # type: ignore
    except Exception as e:  # pragma: no cover
        raise ValueError(f"trafilatura not available: {e}")

    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        output_format="txt",
    )
    text = _clean_text(extracted or "")
    if max_chars and len(text) > max_chars:
        text = text[:max_chars]

    # Title/summary fallback for callers that need it
    title = ""
    summary = ""
    if text:
        first_line = (text.split("\n", 1)[0] or "").strip()
        title = first_line[:140]
        summary = text[:500]

    words = len(re.findall(r"\b\w+\b", text))
    return ArticleExtractionResult(
        url=url,
        final_url=final_url,
        title=title or url,
        summary=summary,
        content_text=text,
        word_count=words,
        extractor="trafilatura",
    )


def is_cached_content_fresh(extracted_at: datetime | None) -> bool:
    if not extracted_at:
        return False
    ttl_hours = _cfg_int("ARTICLE_CONTENT_TTL_HOURS", 168)
    try:
        now = datetime.now(timezone.utc)
    except Exception:
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
    return extracted_at >= (now - timedelta(hours=max(1, ttl_hours)))

