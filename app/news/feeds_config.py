"""
RSS Feeds configuration organized by category.

This module defines all news categories and their associated RSS feed URLs.
Follows Single Responsibility Principle - only configuration, no logic.

Each feed includes a URL, source name, and source_type for proper attribution.
source_type: 'free' | 'freemium' | 'paid'
  - free: Fully accessible content, no paywall
  - freemium: Some free articles, limited access or article count restrictions
  - paid: Requires subscription, most content blocked
"""
from __future__ import annotations

from typing import TypedDict, Literal


SourceType = Literal["free", "freemium", "paid"]


class FeedConfig(TypedDict):
    """Type definition for a single feed."""
    url: str
    name: str
    source_type: SourceType


class CategoryConfig(TypedDict):
    """Type definition for category configuration."""
    name: str
    slug: str
    image: str
    feeds: list[FeedConfig]


# Source type definitions for URL matching (fallback when feed config not found)
# Maps domain patterns to source types
PAID_DOMAINS = {
    "wsj.com",
    "feeds.a.dj.com",      # Wall Street Journal
    "bloomberg.com",        # Bloomberg
    "ft.com",               # Financial Times
    "nytimes.com",          # New York Times
}

FREEMIUM_DOMAINS = {
    "fortune.com",          # Fortune - some free articles
    "hbr.org",              # Harvard Business Review
    "harvardbusiness.org",
    "inc.com",              # Inc. - ad-heavy but some free
    "forbes.com",           # Forbes - metered
    "businessinsider.com",  # Business Insider - metered
    "economist.com",        # The Economist
}


# Default placeholder images for sources without article images
# You can replace these with your own hosted logos
SOURCE_LOGOS: dict[str, str] = {
    # Business
    "Harvard Business Review": "/static/images/logos/hbr.png",
    "Entrepreneur": "/static/images/logos/entrepreneur.png",
    "Inc.": "/static/images/logos/inc.png",
    "Wired Business": "/static/images/logos/wired.png",
    "Fortune": "/static/images/logos/fortune.png",
    "NY Times Business": "/static/images/logos/nyt.png",
    # Leadership
    "Fast Company": "/static/images/logos/fastcompany.png",
    "Let's Grow Leaders": "/static/images/logos/default.png",
    "MIT Sloan Management Review": "/static/images/logos/mit.png",
    # HR
    "HR Bartender": "/static/images/logos/default.png",
    "HR Dive": "/static/images/logos/hrdive.png",
    "Human Resource Executive": "/static/images/logos/default.png",
    "Human Capital Magazine": "/static/images/logos/default.png",
    "Personnel Today": "/static/images/logos/default.png",
    # Marketing
    "Marketing Dive": "/static/images/logos/marketingdive.png",
    "Social Media Today": "/static/images/logos/default.png",
    "Search Engine Land": "/static/images/logos/sel.png",
    "Search Engine Journal": "/static/images/logos/sej.png",
    "HubSpot Marketing": "/static/images/logos/hubspot.png",
    "Adweek": "/static/images/logos/adweek.png",
    # Tech
    "TechCrunch": "/static/images/logos/techcrunch.png",
    "VentureBeat": "/static/images/logos/venturebeat.png",
    "The Hacker News": "/static/images/logos/hackernews.png",
    "The Verge": "/static/images/logos/theverge.png",
    "Wired AI": "/static/images/logos/wired.png",
    "Wired Security": "/static/images/logos/wired.png",
    "The Guardian": "/static/images/logos/guardian.png",
    "OpenAI": "/static/images/logos/openai.png",
    # Design
    "UX Planet": "/static/images/logos/default.png",
    "Product Coalition": "/static/images/logos/default.png",
    "Webdesigner Depot": "/static/images/logos/default.png",
    "Design Week": "/static/images/logos/default.png",
    "Wired Ideas": "/static/images/logos/wired.png",
    "Smashing Magazine": "/static/images/logos/smashing.png",
    "UX Collective": "/static/images/logos/default.png",
    "Creative Bloq": "/static/images/logos/creativebloq.png",
    # Startups
    "TechCrunch Startups": "/static/images/logos/techcrunch.png",
    "Crunchbase News": "/static/images/logos/crunchbase.png",
    "EU-Startups": "/static/images/logos/default.png",
    "SaaStr": "/static/images/logos/saastr.png",
    "Tomasz Tunguz": "/static/images/logos/default.png",
    # Finance
    "MarketWatch": "/static/images/logos/marketwatch.png",
    "CNBC": "/static/images/logos/cnbc.png",
    "Investing.com": "/static/images/logos/investing.png",
    "Yahoo Finance": "/static/images/logos/yahoo.png",
    "Bloomberg": "/static/images/logos/bloomberg.png",
    "Wall Street Journal": "/static/images/logos/wsj.png",
    "Financial Times": "/static/images/logos/ft.png",
}

# Default fallback image when no logo is configured
DEFAULT_PLACEHOLDER = "/static/images/logos/default.png"


def get_source_logo(source_name: str) -> str:
    """Get the logo URL for a source, or default placeholder."""
    return SOURCE_LOGOS.get(source_name, DEFAULT_PLACEHOLDER)


# All categories with their RSS feeds
CATEGORIES: dict[str, CategoryConfig] = {
    "business-economy-geopolitics": {
        "name": "Business, Economy & Geopolitics",
        "slug": "business-economy-geopolitics",
        "image": "/static/images/categories/business.jpg",
        "feeds": [
            # === FREE SOURCES (fully accessible) ===
            {"url": "http://feeds.feedburner.com/entrepreneur/latest", "name": "Entrepreneur", "source_type": "free"},
            {"url": "https://www.wired.com/feed/category/business/latest/rss", "name": "Wired Business", "source_type": "freemium"},
            {"url": "http://feeds.bbci.co.uk/news/business/rss.xml", "name": "BBC Business", "source_type": "free"},
            {"url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "name": "CNBC", "source_type": "free"},
            {"url": "https://www.theguardian.com/business/rss", "name": "The Guardian Business", "source_type": "free"},
            {"url": "https://feeds.npr.org/1006/rss.xml", "name": "NPR Business", "source_type": "free"},
            {"url": "https://theconversation.com/us/business/articles.atom", "name": "The Conversation Business", "source_type": "free"},
            # === FREEMIUM SOURCES (limited free articles) ===
            {"url": "http://feeds.harvardbusiness.org/harvardbusiness/", "name": "Harvard Business Review", "source_type": "freemium"},
            {"url": "http://www.inc.com/rss/homepage.xml", "name": "Inc.", "source_type": "freemium"},
            {"url": "http://fortune.com/feed/", "name": "Fortune", "source_type": "freemium"},
            # === PAID SOURCES (subscription required - excluded from generation) ===
            # Removed: NY Times, WSJ, Bloomberg, FT - paywalled content
        ],
    },
    "leadership-management-careers": {
        "name": "Leadership, Management & Careers",
        "slug": "leadership-management-careers",
        "image": "/static/images/categories/leadership.jpg",
        "feeds": [
            # === FREE SOURCES ===
            {"url": "https://www.fastcompany.com/leadership/rss", "name": "Fast Company", "source_type": "free"},
            {"url": "http://letsgrowleaders.com/feed/", "name": "Let's Grow Leaders", "source_type": "free"},
            {"url": "https://hbswk.hbs.edu/rss/rss.xml", "name": "HBS Working Knowledge", "source_type": "free"},
            # === FREEMIUM SOURCES ===
            {"url": "http://feeds.harvardbusiness.org/managementtip", "name": "Harvard Business Review", "source_type": "freemium"},
            {"url": "http://feeds.feedburner.com/mitsmr", "name": "MIT Sloan Management Review", "source_type": "freemium"},
        ],
    },
    "people-hr-future-of-work": {
        "name": "People, HR & Future of Work",
        "slug": "people-hr-future-of-work",
        "image": "/static/images/categories/hr.jpg",
        "feeds": [
            # === FREE SOURCES ===
            {"url": "http://feeds.feedburner.com/HrBartender", "name": "HR Bartender", "source_type": "free"},
            {"url": "https://www.hrdive.com/feeds/news/", "name": "HR Dive", "source_type": "free"},
            {"url": "https://hrexecutive.com/feed/", "name": "Human Resource Executive", "source_type": "free"},
            {"url": "https://www.hcamag.com/us/rss", "name": "Human Capital Magazine", "source_type": "free"},
            {"url": "https://www.personneltoday.com/feed/", "name": "Personnel Today", "source_type": "free"},
            {"url": "https://workplaceinsight.net/feed/", "name": "Workplace Insight", "source_type": "free"},
            # === FREEMIUM SOURCES ===
            {"url": "https://www.shrm.org/rss/pages/rss.aspx", "name": "SHRM", "source_type": "freemium"},
        ],
    },
    "marketing-brand-growth": {
        "name": "Marketing, Brand & Growth",
        "slug": "marketing-brand-growth",
        "image": "/static/images/categories/marketing.jpg",
        "feeds": [
            # === FREE SOURCES ===
            {"url": "https://www.marketingdive.com/feeds/news/", "name": "Marketing Dive", "source_type": "free"},
            {"url": "https://www.socialmediatoday.com/rss.xml", "name": "Social Media Today", "source_type": "free"},
            {"url": "https://searchengineland.com/feed/", "name": "Search Engine Land", "source_type": "free"},
            {"url": "https://www.searchenginejournal.com/feed/", "name": "Search Engine Journal", "source_type": "free"},
            {"url": "https://blog.hubspot.com/marketing/rss.xml", "name": "HubSpot Marketing", "source_type": "free"},
            {"url": "https://contentmarketinginstitute.com/feed/", "name": "Content Marketing Institute", "source_type": "free"},
            {"url": "https://moz.com/blog/feed", "name": "Moz Blog", "source_type": "free"},
            {"url": "https://neilpatel.com/blog/feed/", "name": "Neil Patel", "source_type": "free"},
            # === FREEMIUM SOURCES ===
            {"url": "https://www.adweek.com/feed/", "name": "Adweek", "source_type": "freemium"},
            {"url": "https://www.dmnews.com/feed/", "name": "DM News", "source_type": "freemium"},
        ],
    },
    "technology-ai-software": {
        "name": "Technology, AI & Software Engineering",
        "slug": "technology-ai-software",
        "image": "/static/images/categories/technology.jpg",
        "feeds": [
            # === FREE SOURCES ===
            {"url": "https://techcrunch.com/feed/", "name": "TechCrunch", "source_type": "free"},
            {"url": "https://venturebeat.com/feed/", "name": "VentureBeat", "source_type": "free"},
            {"url": "https://feeds.feedburner.com/TheHackersNews", "name": "The Hacker News", "source_type": "free"},
            {"url": "https://www.theverge.com/rss/index.xml", "name": "The Verge", "source_type": "free"},
            {"url": "https://www.wired.com/feed/tag/ai/latest/rss", "name": "Wired AI", "source_type": "free"},
            {"url": "https://www.theguardian.com/uk/technology/rss", "name": "The Guardian Tech", "source_type": "free"},
            {"url": "https://openai.com/news/rss.xml", "name": "OpenAI", "source_type": "free"},
            {"url": "https://www.wired.com/feed/category/security/latest/rss", "name": "Wired Security", "source_type": "free"},
            {"url": "https://arstechnica.com/feed/", "name": "Ars Technica", "source_type": "free"},
            {"url": "https://www.zdnet.com/news/rss.xml", "name": "ZDNet", "source_type": "free"},
        ],
    },
    "product-ux-design": {
        "name": "Product, UX & Design",
        "slug": "product-ux-design",
        "image": "/static/images/categories/design.jpg",
        "feeds": [
            # === FREE SOURCES ===
            {"url": "https://uxplanet.org/feed", "name": "UX Planet", "source_type": "free"},
            {"url": "https://productcoalition.com/feed", "name": "Product Coalition", "source_type": "free"},
            {"url": "https://feeds2.feedburner.com/webdesignerdepot", "name": "Webdesigner Depot", "source_type": "free"},
            {"url": "https://www.designweek.co.uk/feed/", "name": "Design Week", "source_type": "free"},
            {"url": "https://www.wired.com/feed/category/ideas/latest/rss", "name": "Wired Ideas", "source_type": "free"},
            {"url": "https://www.smashingmagazine.com/feed/", "name": "Smashing Magazine", "source_type": "free"},
            {"url": "https://uxdesign.cc/feed", "name": "UX Collective", "source_type": "free"},
            {"url": "https://www.creativebloq.com/feed", "name": "Creative Bloq", "source_type": "free"},
            {"url": "https://alistapart.com/main/feed/", "name": "A List Apart", "source_type": "free"},
        ],
    },
    "startups-entrepreneurship-vc": {
        "name": "Startups, Entrepreneurship & Venture Capital",
        "slug": "startups-entrepreneurship-vc",
        "image": "/static/images/categories/startups.jpg",
        "feeds": [
            # === FREE SOURCES ===
            {"url": "https://techcrunch.com/category/startups/feed/", "name": "TechCrunch Startups", "source_type": "free"},
            {"url": "https://news.crunchbase.com/feed/", "name": "Crunchbase News", "source_type": "free"},
            {"url": "https://www.eu-startups.com/feed/", "name": "EU-Startups", "source_type": "free"},
            {"url": "https://www.saastr.com/feed/", "name": "SaaStr", "source_type": "free"},
            {"url": "http://tomtunguz.com/index.xml", "name": "Tomasz Tunguz", "source_type": "free"},
            {"url": "https://bothsidesofthetable.com/feed", "name": "Both Sides of the Table", "source_type": "free"},
            {"url": "https://avc.com/feed/", "name": "AVC (Fred Wilson)", "source_type": "free"},
        ],
    },
    "markets-investing-fintech": {
        "name": "Markets, Investing & Fintech",
        "slug": "markets-investing-fintech",
        "image": "/static/images/categories/markets.jpg",
        "feeds": [
            # === FREE SOURCES ===
            {"url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "name": "CNBC Markets", "source_type": "free"},
            {"url": "https://www.investing.com/rss/news.rss", "name": "Investing.com", "source_type": "free"},
            {"url": "http://finance.yahoo.com/rss/topstories", "name": "Yahoo Finance", "source_type": "free"},
            {"url": "https://www.finextra.com/rss/headlines.aspx", "name": "Finextra", "source_type": "free"},
            {"url": "https://www.pymnts.com/feed/", "name": "PYMNTS", "source_type": "free"},
            # === FREEMIUM SOURCES ===
            {"url": "https://www.marketwatch.com/rss/topstories", "name": "MarketWatch", "source_type": "freemium"},
            # === PAID SOURCES (removed - content is blocked) ===
            # Bloomberg, WSJ, FT - require subscription
        ],
    },
}


def get_all_categories() -> list[dict]:
    """Return all categories as a list (without feed details for display)."""
    return [
        {
            "name": config["name"],
            "slug": config["slug"],
            "image": config["image"],
        }
        for config in CATEGORIES.values()
    ]


def get_category_by_slug(slug: str) -> CategoryConfig | None:
    """Get a category by its slug."""
    return CATEGORIES.get(slug)


def get_feeds_for_category(slug: str) -> list[FeedConfig]:
    """Get all RSS feeds for a specific category."""
    category = CATEGORIES.get(slug)
    if category:
        return category["feeds"]
    return []


def get_all_feeds() -> list[tuple[str, str, str, SourceType]]:
    """
    Get all RSS feed URLs with their category slug, source name, and source type.
    
    Returns:
        List of tuples (feed_url, category_slug, source_name, source_type)
    """
    result = []
    for slug, config in CATEGORIES.items():
        for feed in config["feeds"]:
            result.append((feed["url"], slug, feed["name"], feed.get("source_type", "free")))
    return result


def get_category_slugs() -> list[str]:
    """Get list of all category slugs."""
    return list(CATEGORIES.keys())


def get_source_type_for_feed(feed_url: str, source_name: str | None = None) -> SourceType:
    """
    Get the source type for a given feed URL.
    
    First checks the feed config, then falls back to domain matching.
    
    Args:
        feed_url: The feed URL to check
        source_name: Optional source name to match against config
        
    Returns:
        'free', 'freemium', or 'paid'
    """
    # First, try to find in feed configs
    for config in CATEGORIES.values():
        for feed in config["feeds"]:
            if feed["url"] == feed_url or (source_name and feed["name"] == source_name):
                return feed.get("source_type", "free")
    
    # Fallback to domain matching
    url_lower = feed_url.lower()
    
    if any(paid in url_lower for paid in PAID_DOMAINS):
        return "paid"
    
    if any(freemium in url_lower for freemium in FREEMIUM_DOMAINS):
        return "freemium"
    
    return "free"


def is_paid_source(url: str) -> bool:
    """
    Check if a URL belongs to a paid/paywalled source.
    
    DEPRECATED: Use get_source_type_for_feed() instead.
    Kept for backward compatibility.
    """
    return get_source_type_for_feed(url) == "paid"
