"""
News service layer - business logic for categories and articles.

Follows Single Responsibility Principle:
- CategoryService: handles category-related operations
- ArticleService: handles article-related operations
"""
from __future__ import annotations

from typing import Tuple
from sqlalchemy import select, func

from ..db import db_session
from ..models import Article, Category, ArticleCategory
from .feeds_config import CATEGORIES, CategoryConfig


class CategoryService:
    """Service for category-related operations."""
    
    @staticmethod
    def get_all_categories() -> list[dict]:
        """
        Return all categories with metadata.
        
        Combines config data with database statistics.
        
        Returns:
            List of category dictionaries with name, slug, image, and article_count
        """
        # Get article counts per category from database
        article_counts: dict[str, int] = {}
        try:
            with db_session() as s:
                # Get counts of articles per category
                count_query = (
                    select(Category.slug, func.count(ArticleCategory.article_id))
                    .join(ArticleCategory, Category.id == ArticleCategory.category_id)
                    .join(Article, ArticleCategory.article_id == Article.id)
                    .where(Article.deleted_at.is_(None))
                    .group_by(Category.slug)
                )
                results = s.execute(count_query).all()
                article_counts = {slug: count for slug, count in results}
        except Exception:
            pass  # If DB fails, return categories without counts
        
        # Combine config with counts
        categories = []
        for slug, config in CATEGORIES.items():
            categories.append({
                "name": config["name"],
                "slug": config["slug"],
                "image": config["image"],
                "article_count": article_counts.get(slug, 0),
            })
        
        return categories
    
    @staticmethod
    def get_category_by_slug(slug: str) -> dict | None:
        """
        Fetch single category by slug.
        
        Args:
            slug: The category slug
            
        Returns:
            Category dict or None if not found
        """
        config = CATEGORIES.get(slug)
        if not config:
            return None
        
        # Get article count
        article_count = 0
        try:
            with db_session() as s:
                db_cat = s.execute(
                    select(Category).where(Category.slug == slug)
                ).scalar_one_or_none()
                
                if db_cat:
                    count_query = (
                        select(func.count(ArticleCategory.article_id))
                        .join(Article, ArticleCategory.article_id == Article.id)
                        .where(ArticleCategory.category_id == db_cat.id)
                        .where(Article.deleted_at.is_(None))
                    )
                    article_count = s.execute(count_query).scalar() or 0
        except Exception:
            pass
        
        return {
            "name": config["name"],
            "slug": config["slug"],
            "image": config["image"],
            "article_count": article_count,
        }
    
    @staticmethod
    def ensure_categories_exist() -> None:
        """
        Ensure all categories from config exist in the database.
        Creates missing categories.
        """
        with db_session() as s:
            existing = {
                c.slug: c for c in 
                s.execute(select(Category)).scalars().all()
            }
            
            for slug, config in CATEGORIES.items():
                if slug not in existing:
                    cat = Category(
                        name=config["name"],
                        slug=slug,
                        image_path=config["image"],
                    )
                    s.add(cat)
            
            # Commit happens automatically


class ArticleService:
    """Service for article-related operations."""
    
    @staticmethod
    def get_sources_for_category(category_slug: str, show_paid: bool = True) -> list[dict]:
        """
        Get all unique sources for articles in a category.
        
        Args:
            category_slug: The category slug
            show_paid: Whether to include paid sources
            
        Returns:
            List of dicts with source_name, article_count, and is_paid
        """
        with db_session() as s:
            # Get category ID
            category = s.execute(
                select(Category).where(Category.slug == category_slug)
            ).scalar_one_or_none()
            
            if not category:
                return []
            
            # Get distinct sources with counts and paid status
            source_query = (
                select(
                    Article.source_name,
                    func.count(Article.id).label("count"),
                    func.bool_or(Article.is_paid).label("is_paid")
                )
                .join(ArticleCategory, Article.id == ArticleCategory.article_id)
                .where(ArticleCategory.category_id == category.id)
                .where(Article.deleted_at.is_(None))
                .where(Article.source_name.isnot(None))
            )
            
            # Filter by free/paid if needed
            if not show_paid:
                source_query = source_query.where(Article.is_paid == False)
            
            source_query = source_query.group_by(Article.source_name).order_by(func.count(Article.id).desc())
            
            results = s.execute(source_query).all()
            
            return [
                {"name": name, "count": count, "is_paid": is_paid or False}
                for name, count, is_paid in results
                if name  # Filter out None/empty names
            ]
    
    @staticmethod
    def get_paid_free_counts(category_slug: str) -> dict:
        """
        Get counts of free vs paid articles in a category.
        
        Args:
            category_slug: The category slug
            
        Returns:
            Dict with 'free' and 'paid' counts
        """
        with db_session() as s:
            category = s.execute(
                select(Category).where(Category.slug == category_slug)
            ).scalar_one_or_none()
            
            if not category:
                return {"free": 0, "paid": 0}
            
            # Count free articles
            free_count = s.execute(
                select(func.count(Article.id))
                .join(ArticleCategory, Article.id == ArticleCategory.article_id)
                .where(ArticleCategory.category_id == category.id)
                .where(Article.deleted_at.is_(None))
                .where(Article.is_paid == False)
            ).scalar() or 0
            
            # Count paid articles
            paid_count = s.execute(
                select(func.count(Article.id))
                .join(ArticleCategory, Article.id == ArticleCategory.article_id)
                .where(ArticleCategory.category_id == category.id)
                .where(Article.deleted_at.is_(None))
                .where(Article.is_paid == True)
            ).scalar() or 0
            
            return {"free": free_count, "paid": paid_count}
    
    @staticmethod
    def get_articles_for_category(
        category_slug: str,
        page: int = 1,
        page_size: int = 20,
        source_filter: str | None = None,
        show_paid: bool = True,
    ) -> Tuple[list[Article], int, int]:
        """
        Return paginated articles for a category.
        
        Args:
            category_slug: The category slug to filter by
            page: Page number (1-indexed)
            page_size: Number of articles per page
            source_filter: Optional source name to filter by
            show_paid: Whether to include paid sources (default True)
            
        Returns:
            Tuple of (articles, total_count, total_pages)
        """
        page = max(1, page)
        offset = (page - 1) * page_size
        
        with db_session() as s:
            # Get category ID
            category = s.execute(
                select(Category).where(Category.slug == category_slug)
            ).scalar_one_or_none()
            
            if not category:
                return [], 0, 0
            
            # Build base query for articles in this category
            base_query = (
                select(Article)
                .join(ArticleCategory, Article.id == ArticleCategory.article_id)
                .where(ArticleCategory.category_id == category.id)
                .where(Article.deleted_at.is_(None))
            )
            
            # Apply source filter if specified
            if source_filter:
                base_query = base_query.where(Article.source_name == source_filter)
            
            # Filter by free/paid if needed
            if not show_paid:
                base_query = base_query.where(Article.is_paid == False)
            
            # Get total count
            count_query = select(func.count()).select_from(base_query.subquery())
            total_count = s.execute(count_query).scalar() or 0
            
            # Get paginated articles
            articles_query = (
                base_query
                .order_by(Article.created_at.desc())
                .offset(offset)
                .limit(page_size)
            )
            articles = list(s.execute(articles_query).scalars().all())
            
            # Calculate total pages
            total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
            
            return articles, total_count, total_pages
    
    @staticmethod
    def search_articles_in_category(
        category_slug: str,
        query: str,
        page: int = 1,
        page_size: int = 20,
        source_filter: str | None = None,
        show_paid: bool = True,
    ) -> Tuple[list[Article], int, int]:
        """
        Search articles within a category.
        
        Args:
            category_slug: The category slug to search in
            query: Search query string
            page: Page number (1-indexed)
            page_size: Number of articles per page
            source_filter: Optional source name to filter by
            show_paid: Whether to include paid sources (default True)
            
        Returns:
            Tuple of (articles, total_count, total_pages)
        """
        page = max(1, page)
        offset = (page - 1) * page_size
        search_pattern = f"%{query}%"
        
        with db_session() as s:
            # Get category ID
            category = s.execute(
                select(Category).where(Category.slug == category_slug)
            ).scalar_one_or_none()
            
            if not category:
                return [], 0, 0
            
            # Build base query with search
            from sqlalchemy import or_
            base_query = (
                select(Article)
                .join(ArticleCategory, Article.id == ArticleCategory.article_id)
                .where(ArticleCategory.category_id == category.id)
                .where(Article.deleted_at.is_(None))
                .where(
                    or_(
                        Article.title.ilike(search_pattern),
                        Article.summary.ilike(search_pattern)
                    )
                )
            )
            
            # Apply source filter if specified
            if source_filter:
                base_query = base_query.where(Article.source_name == source_filter)
            
            # Filter by free/paid if needed
            if not show_paid:
                base_query = base_query.where(Article.is_paid == False)
            
            # Get total count
            count_query = select(func.count()).select_from(base_query.subquery())
            total_count = s.execute(count_query).scalar() or 0
            
            # Get paginated articles
            articles_query = (
                base_query
                .order_by(Article.created_at.desc())
                .offset(offset)
                .limit(page_size)
            )
            articles = list(s.execute(articles_query).scalars().all())
            
            # Calculate total pages
            total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
            
            return articles, total_count, total_pages
    
    @staticmethod
    def get_article_by_id(article_id: str) -> Article | None:
        """Get a single article by ID."""
        with db_session() as s:
            return s.execute(
                select(Article)
                .where(Article.id == article_id)
                .where(Article.deleted_at.is_(None))
            ).scalar_one_or_none()
    
    @staticmethod
    def get_total_article_count() -> int:
        """Return the total count of all non-deleted articles."""
        try:
            with db_session() as s:
                return s.execute(
                    select(func.count(Article.id)).where(Article.deleted_at.is_(None))
                ).scalar_one() or 0
        except Exception:
            return 0
    
    @staticmethod
    def get_most_generated_articles(category_slug: str, limit: int = 5) -> list[Article]:
        """
        Get most generated articles for a category.
        Returns articles with highest generation_count that were created in last 30 days.
        """
        from datetime import datetime, timedelta
        
        with db_session() as s:
            category = s.execute(
                select(Category).where(Category.slug == category_slug)
            ).scalar_one_or_none()
            
            if not category:
                return []
            
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            articles_query = (
                select(Article)
                .join(ArticleCategory, Article.id == ArticleCategory.article_id)
                .where(ArticleCategory.category_id == category.id)
                .where(Article.deleted_at.is_(None))
                .where(Article.generation_count > 0)
                .where(Article.created_at >= thirty_days_ago)
                .order_by(Article.generation_count.desc(), Article.created_at.desc())
                .limit(limit)
            )
            
            return list(s.execute(articles_query).scalars().all())

