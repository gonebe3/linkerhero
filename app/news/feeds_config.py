"""
RSS Feeds configuration organized by category.

This module defines all news categories and their associated RSS feed URLs.
Follows Single Responsibility Principle - only configuration, no logic.

Each feed includes a URL and source name for proper attribution.
Paid/paywalled sources are listed separately and filtered during fetch.
"""
from __future__ import annotations

from typing import TypedDict


class FeedConfig(TypedDict):
    """Type definition for a single feed."""
    url: str
    name: str


class CategoryConfig(TypedDict):
    """Type definition for category configuration."""
    name: str
    slug: str
    image: str
    feeds: list[FeedConfig]


# Paid/paywalled sources to skip during fetch
# These require subscriptions and will block most content
PAID_SOURCES = {
    "wsj.com",
    "feeds.a.dj.com",      # Wall Street Journal
    "bloomberg.com",        # Bloomberg
    "fortune.com",          # Fortune
    "nytimes.com",          # New York Times
    "ft.com",               # Financial Times
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
            # Free sources
            {"url": "http://feeds.harvardbusiness.org/harvardbusiness/", "name": "Harvard Business Review"},
            {"url": "http://feeds.feedburner.com/entrepreneur/latest", "name": "Entrepreneur"},
            {"url": "http://www.inc.com/rss/homepage.xml", "name": "Inc."},
            {"url": "https://www.wired.com/feed/category/business/latest/rss", "name": "Wired Business"},
            # Paid sources (will be marked as paid)
            {"url": "http://fortune.com/feed/", "name": "Fortune"},
            {"url": "http://www.nytimes.com/services/xml/rss/nyt/Business.xml", "name": "NY Times Business"},
        ],
    },
    "leadership-management-careers": {
        "name": "Leadership, Management & Careers",
        "slug": "leadership-management-careers",
        "image": "/static/images/categories/leadership.jpg",
        "feeds": [
            {"url": "https://www.fastcompany.com/leadership/rss", "name": "Fast Company"},
            {"url": "http://feeds.harvardbusiness.org/managementtip", "name": "Harvard Business Review"},
            {"url": "http://letsgrowleaders.com/feed/", "name": "Let's Grow Leaders"},
            {"url": "http://feeds.feedburner.com/mitsmr", "name": "MIT Sloan Management Review"},
        ],
    },
    "people-hr-future-of-work": {
        "name": "People, HR & Future of Work",
        "slug": "people-hr-future-of-work",
        "image": "/static/images/categories/hr.jpg",
        "feeds": [
            {"url": "http://feeds.feedburner.com/HrBartender", "name": "HR Bartender"},
            {"url": "https://www.hrdive.com/feeds/news/", "name": "HR Dive"},
            {"url": "https://hrexecutive.com/feed/", "name": "Human Resource Executive"},
            {"url": "https://www.hcamag.com/us/rss", "name": "Human Capital Magazine"},
            # Alternatives for blocked feeds
            {"url": "https://www.shrm.org/resourcesandtools/hr-topics/pages/hr-topics.aspx/rss", "name": "SHRM"},
            {"url": "https://www.personneltoday.com/feed/", "name": "Personnel Today"},
        ],
    },
    "marketing-brand-growth": {
        "name": "Marketing, Brand & Growth",
        "slug": "marketing-brand-growth",
        "image": "/static/images/categories/marketing.jpg",
        "feeds": [
            {"url": "https://www.marketingdive.com/feeds/news/", "name": "Marketing Dive"},
            {"url": "https://www.dmnews.com/feed/", "name": "DM News"},
            {"url": "https://www.socialmediatoday.com/rss.xml", "name": "Social Media Today"},
            {"url": "https://searchengineland.com/feed/", "name": "Search Engine Land"},
            {"url": "https://www.searchenginejournal.com/feed/", "name": "Search Engine Journal"},
            # Alternatives for blocked feeds
            {"url": "https://blog.hubspot.com/marketing/rss.xml", "name": "HubSpot Marketing"},
            {"url": "https://contentmarketinginstitute.com/feed/", "name": "Content Marketing Institute"},
            {"url": "https://www.adweek.com/feed/", "name": "Adweek"},
        ],
    },
    "technology-ai-software": {
        "name": "Technology, AI & Software Engineering",
        "slug": "technology-ai-software",
        "image": "/static/images/categories/technology.jpg",
        "feeds": [
            {"url": "https://techcrunch.com/feed/", "name": "TechCrunch"},
            {"url": "https://venturebeat.com/feed/", "name": "VentureBeat"},
            {"url": "https://feeds.feedburner.com/TheHackersNews", "name": "The Hacker News"},
            {"url": "https://www.theverge.com/rss/index.xml", "name": "The Verge"},
            {"url": "https://www.wired.com/feed/tag/ai/latest/rss", "name": "Wired AI"},
            {"url": "https://www.theguardian.com/uk/technology/rss", "name": "The Guardian"},
            {"url": "https://openai.com/news/rss.xml", "name": "OpenAI"},
            {"url": "https://www.wired.com/feed/category/security/latest/rss", "name": "Wired Security"},
        ],
    },
    "product-ux-design": {
        "name": "Product, UX & Design",
        "slug": "product-ux-design",
        "image": "/static/images/categories/design.jpg",
        "feeds": [
            {"url": "https://uxplanet.org/feed", "name": "UX Planet"},
            {"url": "https://productcoalition.com/feed", "name": "Product Coalition"},
            {"url": "https://feeds2.feedburner.com/webdesignerdepot", "name": "Webdesigner Depot"},
            {"url": "https://www.designweek.co.uk/feed/", "name": "Design Week"},
            {"url": "https://www.wired.com/feed/category/ideas/latest/rss", "name": "Wired Ideas"},
            # Alternatives
            {"url": "https://www.smashingmagazine.com/feed/", "name": "Smashing Magazine"},
            {"url": "https://uxdesign.cc/feed", "name": "UX Collective"},
            {"url": "https://www.creativebloq.com/feed", "name": "Creative Bloq"},
        ],
    },
    "startups-entrepreneurship-vc": {
        "name": "Startups, Entrepreneurship & Venture Capital",
        "slug": "startups-entrepreneurship-vc",
        "image": "/static/images/categories/startups.jpg",
        "feeds": [
            {"url": "https://techcrunch.com/category/startups/feed/", "name": "TechCrunch Startups"},
            {"url": "https://news.crunchbase.com/feed/", "name": "Crunchbase News"},
            {"url": "https://www.eu-startups.com/feed/", "name": "EU-Startups"},
            {"url": "https://www.saastr.com/feed/", "name": "SaaStr"},
            {"url": "http://tomtunguz.com/index.xml", "name": "Tomasz Tunguz"},
        ],
    },
    "markets-investing-fintech": {
        "name": "Markets, Investing & Fintech",
        "slug": "markets-investing-fintech",
        "image": "/static/images/categories/markets.jpg",
        "feeds": [
            # Free sources
            {"url": "https://www.marketwatch.com/rss/topstories", "name": "MarketWatch"},
            {"url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "name": "CNBC"},
            {"url": "https://www.investing.com/rss/news.rss", "name": "Investing.com"},
            {"url": "http://finance.yahoo.com/rss/topstories", "name": "Yahoo Finance"},
            # Paid sources (will be marked as paid)
            {"url": "https://feeds.bloomberg.com/markets/news.rss", "name": "Bloomberg"},
            {"url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", "name": "Wall Street Journal"},
            {"url": "https://www.ft.com/news-feed?format=rss", "name": "Financial Times"},
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


def get_all_feeds() -> list[tuple[str, str, str]]:
    """
    Get all RSS feed URLs with their category slug and source name.
    
    Returns:
        List of tuples (feed_url, category_slug, source_name)
    """
    result = []
    for slug, config in CATEGORIES.items():
        for feed in config["feeds"]:
            result.append((feed["url"], slug, feed["name"]))
    return result


def get_category_slugs() -> list[str]:
    """Get list of all category slugs."""
    return list(CATEGORIES.keys())


def is_paid_source(url: str) -> bool:
    """Check if a URL belongs to a paid/paywalled source."""
    url_lower = url.lower()
    return any(paid in url_lower for paid in PAID_SOURCES)
