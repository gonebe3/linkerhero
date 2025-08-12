from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import feedparser
import httpx
from sqlalchemy import select

from ..db import db_session
from ..models import Article, Category, ArticleCategory

FEEDS = [
    "https://news.ycombinator.com/rss",
    "https://www.theverge.com/rss/index.xml",
    "https://techcrunch.com/feed/",
    "https://www.nature.com/subjects/artificial-intelligence.rss",
    "https://www.ft.com/technology?format=rss",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
]


def _extract_summary_fallback(url: str) -> tuple[str, str]:
    try:
        import trafilatura

        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            res = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
            if res:
                text = res.strip()
                title = text.split("\n", 1)[0][:120]
                summary = text[:500]
                return title or url, summary
    except Exception:
        pass
    return url, ""


def _keywords(title: str, summary: str) -> dict[str, float]:
    text = f"{title} {summary}".lower()
    keys = {}
    for token in text.split():
        if len(token) > 3 and token.isalpha():
            keys[token] = keys.get(token, 0.0) + 1.0
    total = sum(keys.values()) or 1.0
    return {k: round(v / total, 4) for k, v in sorted(keys.items(), key=lambda x: -x[1])[:15]}


def refresh_feeds() -> None:
    for feed_url in FEEDS:
        parsed = feedparser.parse(feed_url)
        for entry in parsed.entries[:50]:
            link = entry.get("link")
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            published = entry.get("published_parsed")
            published_at = None
            if published:
                published_at = datetime(*published[:6])
            if not link:
                continue
            with db_session() as session_db:
                exists = (
                    session_db.execute(select(Article).where(Article.url == link)).scalar_one_or_none()
                    is not None
                )
                if exists:
                    continue
                if not title or not summary:
                    t, s = _extract_summary_fallback(link)
                else:
                    t, s = title, summary
                # Only ingest items that have an explicit image URL in RSS metadata
                img = _extract_image_url(entry)
                if not img:
                    continue
                article = Article(
                    source=feed_url,
                    url=link,
                    title=t[:1000],
                    summary=s,
                    topics=_keywords(t, s),
                    image_url=img,
                    published_at=published_at,
                )
                session_db.add(article)
                session_db.flush()
                # categorize article heuristically
                _assign_categories(session_db, article)


async def extract_url(url: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except Exception:
            title, summary = _extract_summary_fallback(url)
            return {"title": title, "summary": summary}
    title, summary = _extract_summary_fallback(url)
    return {"title": title, "summary": summary}


def _extract_image_url(entry: Any) -> Optional[str]:
    # Common RSS fields used by feedparser
    # media_content / media_thumbnail
    try:
        if hasattr(entry, 'media_content'):
            media = entry.media_content
            if isinstance(media, list) and media:
                url = media[0].get('url')
                if url:
                    return url
        if hasattr(entry, 'media_thumbnail'):
            thumbs = entry.media_thumbnail
            if isinstance(thumbs, list) and thumbs:
                url = thumbs[0].get('url')
                if url:
                    return url
        # enclosures
        for link in entry.get('links', []) or []:
            if link.get('rel') == 'enclosure' and link.get('type', '').startswith('image/'):
                return link.get('href')
        # image field sometimes exists
        img = entry.get('image')
        if isinstance(img, dict):
            if img.get('href'):
                return img.get('href')
            if img.get('url'):
                return img.get('url')
    except Exception:
        pass
    return None


CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "ai": ["ai", "artificial", "machine", "ml", "model", "llm", "neural", "gpt", "claude"],
    "startups": ["startup", "seed", "series", "vc", "founder", "funding"],
    "technology": ["tech", "software", "hardware", "cloud", "saas", "dev", "api"],
    "business": ["business", "revenue", "profit", "market", "strategy", "sales", "marketing"],
    "research": ["paper", "research", "study", "benchmark", "arxiv"],
}


def _assign_categories(session_db, article: Article) -> None:
    text = f"{article.title} {article.summary}".lower()
    matched_slugs: list[str] = []
    for slug, kws in CATEGORY_KEYWORDS.items():
        if any(k in text for k in kws):
            matched_slugs.append(slug)
    if not matched_slugs:
        return
    # ensure Category rows exist
    existing: dict[str, Category] = {c.slug: c for c in session_db.execute(select(Category)).scalars().all()}
    for slug in matched_slugs:
        if slug not in existing:
            c = Category(name=slug.capitalize(), slug=slug)
            session_db.add(c)
            session_db.flush()
            existing[slug] = c
        session_db.add(ArticleCategory(article_id=article.id, category_id=existing[slug].id))

