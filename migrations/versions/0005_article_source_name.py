"""Add source_name to Article model

Revision ID: 0005_article_source_name
Revises: 0004_category_image
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0005_article_source_name'
down_revision = '0004_category_image'
branch_labels = None
depends_on = None


def upgrade():
    # Add source_name column to articles table
    op.add_column(
        'articles',
        sa.Column('source_name', sa.String(100), nullable=True)
    )
    
    # Create index for filtering by source
    op.create_index(
        'ix_articles_source_name',
        'articles',
        ['source_name'],
        unique=False
    )


def downgrade():
    op.drop_index('ix_articles_source_name', table_name='articles')
    op.drop_column('articles', 'source_name')



