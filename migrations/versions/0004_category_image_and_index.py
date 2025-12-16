"""Add image_path to Category and create index for article_categories

Revision ID: 0004_category_image
Revises: 59fbc915d473
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004_category_image'
down_revision = '59fbc915d473'
branch_labels = None
depends_on = None


def upgrade():
    # Add image_path column to categories table
    op.add_column(
        'categories',
        sa.Column('image_path', sa.String(500), nullable=True)
    )
    
    # Create composite index for faster category article queries
    # This speeds up: SELECT articles WHERE category_id = X ORDER BY created_at DESC
    op.create_index(
        'ix_article_categories_category_created',
        'article_categories',
        ['category_id'],
        unique=False
    )


def downgrade():
    op.drop_index('ix_article_categories_category_created', table_name='article_categories')
    op.drop_column('categories', 'image_path')

