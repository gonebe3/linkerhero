"""
Revision ID: 0286ee01ea54
Revises: 7e2679376dc4
Create Date: 2026-01-20 12:51:00.551217
"""

from alembic import op
import sqlalchemy as sa

revision = '0286ee01ea54'
down_revision = '7e2679376dc4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Repair migration: earlier revisions may have been generated empty in some environments.
    This ensures required columns exist without touching unrelated constraints/indexes.
    """
    bind = op.get_bind()
    insp = sa.inspect(bind)

    def has_col(table: str, col: str) -> bool:
        try:
            cols = insp.get_columns(table)
            return any((c.get("name") or "").lower() == col.lower() for c in cols)
        except Exception:
            return False

    # users profile fields
    if not has_col("users", "full_name"):
        op.add_column("users", sa.Column("full_name", sa.String(length=200), nullable=True))
    if not has_col("users", "profile_image_url"):
        op.add_column("users", sa.Column("profile_image_url", sa.String(length=2000), nullable=True))
    if not has_col("users", "profile_source"):
        op.add_column("users", sa.Column("profile_source", sa.String(length=20), nullable=True))

    # articles full content cache
    if not has_col("articles", "content_text"):
        op.add_column("articles", sa.Column("content_text", sa.Text(), nullable=True))
    if not has_col("articles", "content_extracted_at"):
        op.add_column("articles", sa.Column("content_extracted_at", sa.DateTime(timezone=True), nullable=True))
    if not has_col("articles", "content_extractor"):
        op.add_column("articles", sa.Column("content_extractor", sa.String(length=50), nullable=True))


def downgrade() -> None:
    # Best-effort rollback (only drop if present)
    bind = op.get_bind()
    insp = sa.inspect(bind)

    def has_col(table: str, col: str) -> bool:
        try:
            cols = insp.get_columns(table)
            return any((c.get("name") or "").lower() == col.lower() for c in cols)
        except Exception:
            return False

    if has_col("articles", "content_extractor"):
        op.drop_column("articles", "content_extractor")
    if has_col("articles", "content_extracted_at"):
        op.drop_column("articles", "content_extracted_at")
    if has_col("articles", "content_text"):
        op.drop_column("articles", "content_text")

    if has_col("users", "profile_source"):
        op.drop_column("users", "profile_source")
    if has_col("users", "profile_image_url"):
        op.drop_column("users", "profile_image_url")
    if has_col("users", "full_name"):
        op.drop_column("users", "full_name")

