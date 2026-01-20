from __future__ import annotations

import os


def test_repair_article_categories_from_source_relinks_wrong_category():
    # Use in-memory SQLite for test isolation
    os.environ.setdefault("SECRET_KEY", "test")
    os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

    from app import create_app
    from app.db import db
    from app.models import Article, ArticleCategory, Category
    from app.news.rss import repair_article_categories_from_source

    app = create_app()
    with app.app_context():
        db.create_all()

        # Two categories (slugs must match feeds_config keys)
        tech = Category(
            name="Technology, AI & Software Engineering",
            slug="technology-ai-software",
            image_path="/static/images/categories/technology.jpg",
        )
        markets = Category(
            name="Markets, Investing & Fintech",
            slug="markets-investing-fintech",
            image_path="/static/images/categories/markets.jpg",
        )
        db.session.add_all([tech, markets])
        db.session.flush()

        # Article came from a Markets feed, but is incorrectly linked to Technology
        a = Article(
            source="https://finance.yahoo.com/news/rssindex",
            source_name="Yahoo Finance",
            url="https://example.com/finance-article",
            title="Finance headline",
            summary="Finance summary",
            topics={},
        )
        db.session.add(a)
        db.session.flush()

        db.session.add(ArticleCategory(article_id=a.id, category_id=tech.id))
        db.session.commit()

        res = repair_article_categories_from_source()
        assert res["repaired"] == 1

        # Now the article should be linked to Markets
        link = (
            db.session.query(ArticleCategory)
            .filter(ArticleCategory.article_id == a.id)
            .one()
        )
        assert link.category_id == markets.id

