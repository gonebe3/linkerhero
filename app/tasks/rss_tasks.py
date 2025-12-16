"""
RSS feed refresh tasks for Celery.

These tasks run in the background to fetch and process RSS feeds.
"""
from __future__ import annotations

import logging
from app.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(
    bind=True,
    name="app.tasks.rss_tasks.refresh_all_rss_feeds",
    max_retries=3,
    default_retry_delay=300,  # 5 minutes between retries
)
def refresh_all_rss_feeds(self) -> dict:
    """
    Refresh all RSS feeds across all categories.
    
    This task is scheduled to run daily via Celery Beat.
    It ensures all categories exist in the database and then
    fetches new articles from all configured RSS feeds.
    
    Returns:
        Dict with status and count of articles added
    """
    logger.info("Starting scheduled RSS feed refresh...")
    
    try:
        from app.news.services import CategoryService
        from app.news.rss import refresh_all_feeds
        
        # Ensure all categories exist in database
        logger.info("Ensuring categories exist in database...")
        CategoryService.ensure_categories_exist()
        
        # Refresh all feeds
        logger.info("Fetching RSS feeds...")
        count = refresh_all_feeds()
        
        logger.info(f"RSS feed refresh complete. Added {count} new articles.")
        return {"status": "success", "articles_added": count}
        
    except Exception as exc:
        logger.error(f"RSS feed refresh failed: {exc}")
        # Retry the task
        raise self.retry(exc=exc)


@celery.task(
    bind=True,
    name="app.tasks.rss_tasks.refresh_category_feeds",
    max_retries=3,
    default_retry_delay=60,  # 1 minute between retries
)
def refresh_category_feeds(self, category_slug: str) -> dict:
    """
    Refresh RSS feeds for a specific category.
    
    Args:
        category_slug: The category slug to refresh
        
    Returns:
        Dict with status and count of articles added
    """
    logger.info(f"Starting RSS feed refresh for category: {category_slug}")
    
    try:
        from app.news.services import CategoryService
        from app.news.rss import refresh_category_feeds as do_refresh
        
        # Ensure categories exist
        CategoryService.ensure_categories_exist()
        
        # Refresh the specific category
        count = do_refresh(category_slug)
        
        logger.info(f"Category {category_slug} refresh complete. Added {count} articles.")
        return {"status": "success", "category": category_slug, "articles_added": count}
        
    except Exception as exc:
        logger.error(f"Category feed refresh failed for {category_slug}: {exc}")
        raise self.retry(exc=exc)

