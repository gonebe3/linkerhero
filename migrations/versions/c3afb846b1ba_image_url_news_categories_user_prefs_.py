"""
Revision ID: c3afb846b1ba
Revises: f8c45298c948
Create Date: 2025-08-12 17:40:17.076547
"""

from alembic import op
import sqlalchemy as sa



revision = 'c3afb846b1ba'
down_revision = 'f8c45298c948'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users.default_language
    op.add_column('users', sa.Column('default_language', sa.String(length=10), nullable=True))

    # articles.image_url
    op.add_column('articles', sa.Column('image_url', sa.String(length=2000), nullable=True))

    # categories
    op.create_table(
        'categories',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=120), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('name', name='uq_categories_name'),
        sa.UniqueConstraint('slug', name='uq_categories_slug'),
    )
    op.create_index('ix_categories_name', 'categories', ['name'], unique=False)
    op.create_index('ix_categories_slug', 'categories', ['slug'], unique=False)

    # article_categories
    op.create_table(
        'article_categories',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('article_id', sa.String(length=36), nullable=False),
        sa.Column('category_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id']),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id']),
        sa.UniqueConstraint('article_id', 'category_id', name='uq_article_category'),
    )
    op.create_index('ix_article_categories_article_id', 'article_categories', ['article_id'], unique=False)
    op.create_index('ix_article_categories_category_id', 'article_categories', ['category_id'], unique=False)

    # user_news_preferences
    op.create_table(
        'user_news_preferences',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('categories', sa.JSON(), nullable=False),
        sa.Column('show_only_my_categories', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.UniqueConstraint('user_id', name='uq_user_news_pref_user'),
    )
    op.create_index('ix_user_news_preferences_user_id', 'user_news_preferences', ['user_id'], unique=False)


def downgrade() -> None:
    # Drop user_news_preferences
    op.drop_index('ix_user_news_preferences_user_id', table_name='user_news_preferences')
    op.drop_table('user_news_preferences')

    # Drop article_categories
    op.drop_index('ix_article_categories_category_id', table_name='article_categories')
    op.drop_index('ix_article_categories_article_id', table_name='article_categories')
    op.drop_table('article_categories')

    # Drop categories
    op.drop_index('ix_categories_slug', table_name='categories')
    op.drop_index('ix_categories_name', table_name='categories')
    op.drop_table('categories')

    # Drop added columns
    op.drop_column('articles', 'image_url')
    op.drop_column('users', 'default_language')

