"""Add source_type column to Article model

Revision ID: 0008_article_source_type
Revises: 0007_article_generation_count
Create Date: 2025-01-16 00:00:00.000000

This migration adds a source_type column to differentiate between:
- 'free': Fully accessible content, no paywall
- 'freemium': Some free articles, limited access  
- 'paid': Requires subscription, most content blocked

The existing is_paid column is kept for backward compatibility but deprecated.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0008_article_source_type'
down_revision = '0007_article_generation_count'
branch_labels = None
depends_on = None


def upgrade():
    # Add source_type column to articles table with default 'free'
    op.add_column(
        'articles',
        sa.Column('source_type', sa.String(20), nullable=False, server_default='free')
    )
    
    # Create index for filtering by source_type
    op.create_index(
        'ix_articles_source_type',
        'articles',
        ['source_type'],
        unique=False
    )
    
    # Migrate existing is_paid data to source_type
    # is_paid=True -> source_type='paid'
    # is_paid=False -> source_type='free' (default, already set)
    op.execute("""
        UPDATE articles 
        SET source_type = 'paid' 
        WHERE is_paid = true
    """)


def downgrade():
    op.drop_index('ix_articles_source_type', table_name='articles')
    op.drop_column('articles', 'source_type')









