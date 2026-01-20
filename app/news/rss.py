"""
RSS feed fetching and article ingestion.

This module handles:
- Fetching RSS feeds for each category
- Parsing feed entries
- Extracting article content
- Saving articles to the database

 Includes SSRF protection for URL fetching.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

import aiohttp
import feedparser
from sqlalchemy import select, delete

from ..db import db_session
from ..models import Article, Category, ArticleCategory
from .feeds_config import CATEGORIES, get_feeds_for_category, get_category_slugs, get_all_feeds
from .url_validator import validate_url, is_url_safe
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

logger = logging.getLogger(__name__)


def _normalize_url(url: str) -> str:
    """
    Normalize URL for deduplication by removing tracking parameters.
    
    Strips common UTM and tracking query params, trailing slashes.
    """
    try:
        parsed = urlparse(url)
        # Remove common tracking params
        tracking_params = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
                          'ref', 'source', 'fbclid', 'gclid', 'mc_cid', 'mc_eid'}
        query_params = parse_qs(parsed.query)
        filtered_params = {k: v for k, v in query_params.items() if k.lower() not in tracking_params}
        new_query = urlencode(filtered_params, doseq=True) if filtered_params else ''
        # Rebuild URL without tracking params, strip trailing slash
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip('/'),
            parsed.params,
            new_query,
            ''  # Remove fragment
        ))
        return normalized
    except Exception:
        return url


def _normalize_feed_key(url: str) -> str:
    """
    Normalize an RSS feed URL into a stable key for mapping.

    Purpose: robust matching between stored Article.source and feeds_config URLs,
    even if scheme differs (http vs https) or case differs.

    Returns: "<host><path>" lowercased, without trailing slash, without query/fragment.
    Example: "finance.yahoo.com/news/rssindex"
    """
    try:
        p = urlparse(url or "")
        host = (p.netloc or "").lower()
        path = (p.path or "").rstrip("/").lower()
        return f"{host}{path}"
    except Exception:
        return (url or "").strip().lower()


def _build_feed_url_to_category_slug() -> dict[str, str]:
    """
    Build a mapping of normalized feed URL -> category slug.

    This is used as the source of truth for category assignment to prevent
    mismatches between UI selection and persisted article categories.
    """
    mapping: dict[str, str] = {}
    for feed_url, category_slug, _source_name in get_all_feeds():
        mapping[_normalize_feed_key(feed_url)] = category_slug
    return mapping


# Source-of-truth mapping for category assignment
FEED_URL_TO_CATEGORY_SLUG: dict[str, str] = _build_feed_url_to_category_slug()

# Timeout for individual feed fetches
FEED_TIMEOUT_SECONDS = 20
# Maximum entries to process per feed
MAX_ENTRIES_PER_FEED = 50

# User-Agent to avoid 403 errors from bot detection
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, application/atom+xml, text/xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}


def _extract_summary_fallback(url: str) -> tuple[str, str]:
    """
    Extract title and summary from a URL using trafilatura.
    
    Used as fallback when RSS entry doesn't have title/summary.
    """
    # Validate URL before fetching (SSRF protection)
    if not is_url_safe(url):
        logger.warning(f"Blocked unsafe URL in fallback: {url}")
        return url, ""
    
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
    except Exception as e:
        logger.debug(f"Fallback extraction failed for {url}: {e}")
    
    return url, ""


def _keywords(title: str, summary: str) -> dict[str, float]:
    """
    Extract keywords from title and summary.
    
    Returns a dict of keyword -> normalized frequency.
    """
    text = f"{title} {summary}".lower()
    keys: dict[str, float] = {}
    for token in text.split():
        if len(token) > 3 and token.isalpha():
            keys[token] = keys.get(token, 0.0) + 1.0
    
    total = sum(keys.values()) or 1.0
    return {k: round(v / total, 4) for k, v in sorted(keys.items(), key=lambda x: -x[1])[:15]}


def _extract_image_url(entry: Any) -> Optional[str]:
    """
    Extract image URL from RSS entry metadata.
    
    Checks various common RSS fields for images, including parsing HTML content.
    """
    import re
    
    def extract_img_from_html(html_content: str) -> Optional[str]:
        """Extract first usable image URL from HTML content."""
        import html as html_module
        if not html_content:
            return None
        
        # URLs to skip (tracking, CTA buttons, tiny images)
        skip_patterns = ['pixel', 'tracking', '1x1', '/cta/', 'no-cache.hubspot.com/cta']
        
        # Find ALL images in the HTML
        img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
        for url in img_matches:
            # Unescape HTML entities (e.g., &#038; -> &)
            url = html_module.unescape(url)
            # Skip unwanted images
            if any(skip in url.lower() for skip in skip_patterns):
                continue
            # Found a good image
            return url
        # Also check for figure > img or picture > source
        figure_match = re.search(r'<figure[^>]*>.*?<img[^>]+src=["\']([^"\']+)["\']', html_content, re.IGNORECASE | re.DOTALL)
        if figure_match:
            url = html_module.unescape(figure_match.group(1))
            return url
        return None
    
    try:
        # 1. media_content (most reliable)
        if hasattr(entry, 'media_content'):
            media = entry.media_content
            if isinstance(media, list) and media:
                for m in media:
                    url = m.get('url')
                    if url and ('image' in m.get('type', '') or m.get('medium') == 'image'):
                        return url
                # Fallback to first media_content
                if media[0].get('url'):
                    return media[0].get('url')
        
        # 2. media_thumbnail
        if hasattr(entry, 'media_thumbnail'):
            thumbs = entry.media_thumbnail
            if isinstance(thumbs, list) and thumbs:
                url = thumbs[0].get('url')
                if url:
                    return url
        
        # 3. enclosure (any type, not just image/)
        for link in entry.get('links', []) or []:
            if link.get('rel') == 'enclosure':
                href = link.get('href')
                if href:
                    # Check if it looks like an image URL
                    if any(ext in href.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                        return href
                    # If type indicates image
                    if 'image' in link.get('type', ''):
                        return href
        
        # 4. image field
        img = entry.get('image')
        if isinstance(img, dict):
            if img.get('href'):
                return img.get('href')
            if img.get('url'):
                return img.get('url')
        elif isinstance(img, str) and img:
            return img
        
        # 5. Extract from content:encoded HTML
        content_encoded = entry.get('content')
        if content_encoded and isinstance(content_encoded, list) and content_encoded:
            html = content_encoded[0].get('value', '')
            img_url = extract_img_from_html(html)
            if img_url:
                return img_url
        
        # 6. Extract from summary/description HTML
        summary = entry.get('summary', '') or entry.get('description', '')
        if summary:
            img_url = extract_img_from_html(summary)
            if img_url:
                return img_url
        
    except Exception as e:
        logger.debug(f"Error extracting image: {e}")
    
    return None


def _clean_html(text: str) -> str:
    """Strip HTML tags from text."""
    import re
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    import html
    clean = html.unescape(clean)
    # Clean up whitespace
    clean = ' '.join(clean.split())
    return clean.strip()


# Source name normalization to avoid duplicates
SOURCE_NAME_NORMALIZE = {
    # Yahoo variants - all should be "Yahoo Finance"
    "Yahoo": "Yahoo Finance",
    "yahoo": "Yahoo Finance",
    "Yahoo!": "Yahoo Finance",
    "Finance": "Yahoo Finance",  # finance.yahoo.com parses as "Finance"
    # Investing variants
    "Investing": "Investing.com",
    "investing": "Investing.com",
    # CNBC variants
    "Cnbc": "CNBC",
    # MarketWatch
    "Marketwatch": "MarketWatch",
    # TechCrunch
    "Techcrunch": "TechCrunch",
    "TechCrunch Startups": "TechCrunch",  # Merge startups with main
    # VentureBeat
    "Venturebeat": "VentureBeat",
    # HubSpot
    "Hubspot": "HubSpot",
    "Hubspot Marketing": "HubSpot Marketing",
    # Guardian
    "Guardian": "The Guardian",
    "Theguardian": "The Guardian",
    # Hacker News
    "Thehackersnews": "The Hacker News",
    "Hackernews": "The Hacker News",
}


def _normalize_source_name(name: str) -> str:
    """Normalize source name to avoid duplicates."""
    if not name:
        return "Unknown"
    
    # Check exact match first
    if name in SOURCE_NAME_NORMALIZE:
        return SOURCE_NAME_NORMALIZE[name]
    
    # Check case-insensitive
    name_lower = name.lower()
    for key, value in SOURCE_NAME_NORMALIZE.items():
        if key.lower() == name_lower:
            return value
    
    return name


async def _fetch_feed_async(
    session: aiohttp.ClientSession,
    feed_url: str,
    source_name: str,
) -> list[dict]:
    """
    Fetch and parse a single RSS feed asynchronously.
    
    Args:
        session: aiohttp session
        feed_url: URL of the RSS feed
        source_name: Human-readable source name
    Returns:
        List of parsed entries (dicts)
    """
    # Validate feed URL (SSRF protection)
    is_valid, error = validate_url(feed_url)
    if not is_valid:
        logger.warning(f"Blocked feed URL: {feed_url} - {error}")
        return []
    
    try:
        async with session.get(feed_url, headers=REQUEST_HEADERS) as response:
            if response.status != 200:
                logger.warning(f"Feed returned {response.status}: {source_name} ({feed_url})")
                return []
            
            content = await response.text()
            parsed = feedparser.parse(content)
            
            if not parsed.entries:
                logger.warning(f"No entries found in feed: {source_name} ({feed_url})")
                return []
            
            logger.info(f"Fetched {len(parsed.entries)} entries from {source_name}")
            
            entries = []
            for entry in parsed.entries[:MAX_ENTRIES_PER_FEED]:
                link = entry.get("link")
                if not link:
                    continue
                
                # Clean HTML from title and summary
                title = _clean_html(entry.get("title", ""))
                summary = _clean_html(entry.get("summary", "") or entry.get("description", ""))
                
                entries.append({
                    "link": link,
                    "title": title,
                    "summary": summary,
                    "published_parsed": entry.get("published_parsed"),
                    "image_url": _extract_image_url(entry),
                    "feed_url": feed_url,
                    "source_name": source_name,
                })
            
            return entries
    except asyncio.TimeoutError:
        logger.warning(f"Feed timeout: {source_name} ({feed_url})")
    except aiohttp.ClientError as e:
        logger.warning(f"Feed client error for {source_name}: {e}")
    except Exception as e:
        logger.warning(f"Feed error for {source_name} ({feed_url}): {e}")
    
    return []


async def _fetch_all_feeds_for_category(category_slug: str) -> list[dict]:
    """
    Fetch all RSS feeds for a category concurrently.
    
    Args:
        category_slug: The category to fetch feeds for
        
    Returns:
        Combined list of all entries from all feeds
    """
    feeds = get_feeds_for_category(category_slug)
    if not feeds:
        logger.warning(f"No feeds configured for category: {category_slug}")
        return []
    
    logger.info(f"Fetching {len(feeds)} feeds for category: {category_slug}")
    
    timeout = aiohttp.ClientTimeout(total=FEED_TIMEOUT_SECONDS)
    connector = aiohttp.TCPConnector(limit=10, ssl=False)  # Limit concurrent connections
    
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        # feeds is a list of dicts with 'url' and 'name'
        tasks = [
            _fetch_feed_async(
                session, 
                feed["url"], 
                feed["name"]
            ) 
            for feed in feeds
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Flatten results, filtering out exceptions
    all_entries = []
    for i, result in enumerate(results):
        if isinstance(result, list):
            all_entries.extend(result)
        elif isinstance(result, Exception):
            feed_name = feeds[i]["name"] if i < len(feeds) else "unknown"
            logger.warning(f"Feed fetch exception for {feed_name}: {result}")
    
    logger.info(f"Total entries fetched for {category_slug}: {len(all_entries)}")
    return all_entries


def _save_entries_to_db(entries: list[dict], category_slug: str) -> int:
    """
    Save feed entries to database.
    
    Args:
        entries: List of entry dicts from RSS feeds
        category_slug: Category to assign articles to
        
    Returns:
        Number of new articles added
    """
    added_count = 0
    skipped_no_title = 0
    skipped_duplicate = 0
    
    with db_session() as s:
        # Cache categories by slug (create on-demand)
        categories_by_slug: dict[str, Category] = {
            c.slug: c for c in s.execute(select(Category)).scalars().all()
        }

        def _ensure_category(slug: str) -> Category:
            cat = categories_by_slug.get(slug)
            if cat:
                # Keep metadata in sync with config (safe; slug is canonical key)
                cfg = CATEGORIES.get(slug)
                if cfg:
                    cat.name = cfg["name"]
                    cat.image_path = cfg["image"]
                return cat

            cfg = CATEGORIES.get(slug)
            if not cfg:
                # Fallback: create minimal row to avoid crashes; UI uses config anyway.
                cat = Category(name=slug, slug=slug, image_path=None)
            else:
                cat = Category(name=cfg["name"], slug=slug, image_path=cfg["image"])
            s.add(cat)
            s.flush()
            categories_by_slug[slug] = cat
            logger.info(f"Created category: {cat.name} ({cat.slug})")
            return cat

        # Existing URLs map: normalized_url -> article_id (enables relinking duplicates)
        existing_url_to_id: dict[str, str] = {}
        for article_id, url in s.execute(select(Article.id, Article.url)).all():
            existing_url_to_id[_normalize_url(url)] = article_id
        
        for entry in entries:
            link = entry["link"]
            normalized_link = _normalize_url(link)

            # Source-of-truth category is derived from the feed URL.
            # Fallback to passed category_slug to preserve current behavior if mapping is missing.
            feed_url = entry.get("feed_url") or ""
            feed_key = _normalize_feed_key(feed_url) if feed_url else ""
            intended_slug = FEED_URL_TO_CATEGORY_SLUG.get(feed_key) or category_slug
            category = _ensure_category(intended_slug)
            
            # Skip if already exists (using normalized URL)
            existing_article_id = existing_url_to_id.get(normalized_link)
            if existing_article_id:
                skipped_duplicate += 1
                # Enforce: each article belongs to exactly one category based on its feed URL.
                # This prevents cross-category contamination when a URL is seen in multiple refreshes.
                s.execute(
                    delete(ArticleCategory).where(
                        ArticleCategory.article_id == existing_article_id,
                        ArticleCategory.category_id != category.id,
                    )
                )
                exists = s.execute(
                    select(ArticleCategory.id).where(
                        ArticleCategory.article_id == existing_article_id,
                        ArticleCategory.category_id == category.id,
                    )
                ).first()
                if not exists:
                    s.add(ArticleCategory(article_id=existing_article_id, category_id=category.id))
                continue
            
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            
            # Skip entries without title
            if not title:
                skipped_no_title += 1
                continue
            
            # Use fallback extraction if no summary
            if not summary:
                _, sm = _extract_summary_fallback(link)
                summary = sm
            
            # Get image URL (no longer required - allow articles without images)
            img_url = entry.get("image_url")
            
            # Parse published date
            published_at = None
            published_parsed = entry.get("published_parsed")
            if published_parsed:
                try:
                    published_at = datetime(*published_parsed[:6])
                except Exception:
                    pass
            
            # Get source name from entry and normalize to avoid duplicates
            source_name = _normalize_source_name(entry.get("source_name", "Unknown"))
            
            # Create article
            article = Article(
                source=entry.get("feed_url", ""),
                source_name=source_name,
                url=link,
                title=title[:1000],
                summary=summary[:5000] if summary else "",
                topics=_keywords(title, summary),
                image_url=img_url,
                published_at=published_at,
            )
            s.add(article)
            s.flush()
            
            # Link to category
            article_category = ArticleCategory(
                article_id=article.id,
                category_id=category.id,
            )
            s.add(article_category)
            
            existing_url_to_id[normalized_link] = article.id
            added_count += 1
    
    logger.info(f"Category {category_slug}: Added {added_count}, Duplicates skipped: {skipped_duplicate}, No title: {skipped_no_title}")
    return added_count


def repair_article_categories_from_source(*, dry_run: bool = False) -> dict[str, int]:
    """
    Repair article->category links using Article.source (feed URL) as source of truth.

    This fixes historical mis-categorization when category config changed or when an
    article URL existed and was previously skipped for a later category refresh.
    """
    repaired = 0
    skipped_unknown_source = 0

    with db_session() as s:
        # Ensure categories exist and are in-sync with config metadata.
        categories_by_slug: dict[str, Category] = {
            c.slug: c for c in s.execute(select(Category)).scalars().all()
        }

        def _ensure_category(slug: str) -> Category:
            cat = categories_by_slug.get(slug)
            if cat:
                cfg = CATEGORIES.get(slug)
                if cfg:
                    cat.name = cfg["name"]
                    cat.image_path = cfg["image"]
                return cat
            cfg = CATEGORIES.get(slug)
            if not cfg:
                cat = Category(name=slug, slug=slug, image_path=None)
            else:
                cat = Category(name=cfg["name"], slug=slug, image_path=cfg["image"])
            s.add(cat)
            s.flush()
            categories_by_slug[slug] = cat
            return cat

        # Compute intended category per article
        intended: dict[str, str] = {}
        for article_id, source in s.execute(select(Article.id, Article.source)).all():
            feed_key = _normalize_feed_key(source or "")
            slug = FEED_URL_TO_CATEGORY_SLUG.get(feed_key)
            if not slug:
                skipped_unknown_source += 1
                continue
            intended[str(article_id)] = slug

        if not intended:
            return {"repaired": 0, "skipped_unknown_source": skipped_unknown_source}

        # Delete existing links, then re-insert correct ones
        if dry_run:
            return {"repaired": len(intended), "skipped_unknown_source": skipped_unknown_source}

        s.execute(delete(ArticleCategory).where(ArticleCategory.article_id.in_(list(intended.keys()))))
        for article_id, slug in intended.items():
            cat = _ensure_category(slug)
            s.add(ArticleCategory(article_id=article_id, category_id=cat.id))
            repaired += 1

    return {"repaired": repaired, "skipped_unknown_source": skipped_unknown_source}


def refresh_category_feeds(category_slug: str) -> int:
    """
    Refresh all RSS feeds for a specific category.
    
    Args:
        category_slug: The category slug to refresh
        
    Returns:
        Number of new articles added
    """
    logger.info(f"=== Refreshing feeds for category: {category_slug} ===")
    
    # Fetch all feeds concurrently
    entries = asyncio.run(_fetch_all_feeds_for_category(category_slug))
    
    if not entries:
        logger.warning(f"No entries fetched for category: {category_slug}")
        return 0
    
    # Save to database
    count = _save_entries_to_db(entries, category_slug)
    
    logger.info(f"=== Finished {category_slug}: Added {count} articles ===")
    return count


def refresh_all_feeds() -> int:
    """
    Refresh RSS feeds for all categories.
    
    Returns:
        Total number of new articles added
    """
    total_count = 0
    
    logger.info("Starting full RSS feed refresh for all categories")
    
    for slug in get_category_slugs():
        try:
            count = refresh_category_feeds(slug)
            total_count += count
        except Exception as e:
            logger.error(f"Error refreshing category {slug}: {e}", exc_info=True)
    
    logger.info(f"Full refresh complete. Total articles added: {total_count}")
    return total_count


async def extract_url(url: str) -> dict[str, Any]:
    """
    Extract title and summary from a URL.
    
    Used when generating posts from URLs not in our database.
    Includes SSRF protection.
    
    Args:
        url: The URL to extract content from
        
    Returns:
        Dict with 'title' and 'summary' keys
    """
    # Validate URL (SSRF protection)
    is_valid, error = validate_url(url)
    if not is_valid:
        logger.warning(f"Blocked URL extraction: {url} - {error}")
        return {"title": url, "summary": "", "error": error}
    
    title, summary = _extract_summary_fallback(url)
    return {"title": title, "summary": summary}


# Legacy compatibility - keep old function name
def refresh_feeds() -> None:
    """Legacy function - redirects to refresh_all_feeds."""
    refresh_all_feeds()
