from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta


def test_as_of_excludes_newer_articles_in_category():
    os.environ.setdefault("SECRET_KEY", "test")
    os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

    from app import create_app
    from app.db import db
    from app.models import Article, ArticleCategory, Category
    from app.news.services import ArticleService

    app = create_app()
    with app.app_context():
        db.create_all()

        cat = Category(
            name="Technology, AI & Software Engineering",
            slug="technology-ai-software",
            image_path="/static/images/categories/technology.jpg",
        )
        db.session.add(cat)
        db.session.flush()

        t0 = datetime.now(timezone.utc) - timedelta(days=1)
        t1 = datetime.now(timezone.utc)

        a_old = Article(
            source="feed",
            source_name="X",
            url="https://example.com/old",
            title="Old",
            summary="Old",
            topics={},
            created_at=t0,
        )
        a_new = Article(
            source="feed",
            source_name="X",
            url="https://example.com/new",
            title="New",
            summary="New",
            topics={},
            created_at=t1,
        )
        db.session.add_all([a_old, a_new])
        db.session.flush()
        db.session.add_all(
            [
                ArticleCategory(article_id=a_old.id, category_id=cat.id),
                ArticleCategory(article_id=a_new.id, category_id=cat.id),
            ]
        )
        db.session.commit()

        as_of = t0 + timedelta(seconds=1)
        articles, total, pages = ArticleService.get_articles_for_category(
            category_slug="technology-ai-software",
            page=1,
            page_size=20,
            as_of=as_of,
        )
        assert total == 1
        assert pages == 1
        assert [a.url for a in articles] == ["https://example.com/old"]

