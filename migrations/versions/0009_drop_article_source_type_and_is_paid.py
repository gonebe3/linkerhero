"""Drop source_type and is_paid from articles

Revision ID: 0009_drop_article_cols
Revises: 0008_article_source_type
Create Date: 2026-01-13
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "0009_drop_article_cols"
down_revision = "0008_article_source_type"
branch_labels = None
depends_on = None


def upgrade():
    # Drop indexes first (if they exist)
    try:
        op.drop_index("ix_articles_source_type", table_name="articles")
    except Exception:
        pass
    try:
        op.drop_index("ix_articles_is_paid", table_name="articles")
    except Exception:
        pass

    # Drop columns
    try:
        op.drop_column("articles", "source_type")
    except Exception:
        pass
    try:
        op.drop_column("articles", "is_paid")
    except Exception:
        pass


def downgrade():
    # Intentionally not restoring these columns automatically; the project removed them.
    raise RuntimeError("Downgrade not supported for dropping articles.source_type/is_paid")

