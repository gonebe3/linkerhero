"""Add generation_count column to Article model

Revision ID: 0007_article_generation_count
Revises: 0006_article_is_paid
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0007_article_generation_count'
down_revision = '0006_article_is_paid'
branch_labels = None
depends_on = None


def upgrade():
    # Add generation_count column to articles table with default 0
    op.add_column(
        'articles',
        sa.Column('generation_count', sa.Integer(), nullable=False, server_default='0')
    )
    
    # Create index for sorting by generation_count
    op.create_index(
        'ix_articles_generation_count',
        'articles',
        ['generation_count'],
        unique=False
    )


def downgrade():
    op.drop_index('ix_articles_generation_count', table_name='articles')
    op.drop_column('articles', 'generation_count')

