from __future__ import annotations

from datetime import datetime
from typing import Any

import feedparser
import httpx
from sqlalchemy import select

from ..db import db_session
from ..models import Article

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
                article = Article(
                    source=feed_url,
                    url=link,
                    title=t[:1000],
                    summary=s,
                    topics=_keywords(t, s),
                    published_at=published_at,
                )
                session_db.add(article)


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

