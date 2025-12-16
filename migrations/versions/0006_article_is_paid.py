"""Add is_paid column to Article model

Revision ID: 0006_article_is_paid
Revises: 0005_article_source_name
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0006_article_is_paid'
down_revision = '0005_article_source_name'
branch_labels = None
depends_on = None


def upgrade():
    # Add is_paid column to articles table with default False
    op.add_column(
        'articles',
        sa.Column('is_paid', sa.Boolean(), nullable=False, server_default='false')
    )
    
    # Create index for filtering by is_paid
    op.create_index(
        'ix_articles_is_paid',
        'articles',
        ['is_paid'],
        unique=False
    )


def downgrade():
    op.drop_index('ix_articles_is_paid', table_name='articles')
    op.drop_column('articles', 'is_paid')

