"""
Revision ID: ad5aacb8ae1f
Revises: 0009_drop_article_cols
Create Date: 2026-01-20 12:36:44.251045
"""

from alembic import op
import sqlalchemy as sa



revision = 'ad5aacb8ae1f'
down_revision = '0009_drop_article_cols'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('articles', sa.Column('content_text', sa.Text(), nullable=True))
    op.add_column('articles', sa.Column('content_extracted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('articles', sa.Column('content_extractor', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('articles', 'content_extractor')
    op.drop_column('articles', 'content_extracted_at')
    op.drop_column('articles', 'content_text')

