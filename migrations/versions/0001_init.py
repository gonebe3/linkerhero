from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0001_init'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('plan', sa.String(length=50), nullable=False, server_default='free'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    op.create_table(
        'articles',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('source', sa.String(length=255), nullable=False),
        sa.Column('url', sa.String(length=2000), nullable=False),
        sa.Column('title', sa.String(length=1000), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('topics', sa.JSON(), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_articles_url', 'articles', ['url'], unique=True)

    op.create_table(
        'generations',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('article_id', sa.String(length=36), sa.ForeignKey('articles.id'), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('draft_text', sa.Text(), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('score_breakdown', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('generations')
    op.drop_index('ix_articles_url', table_name='articles')
    op.drop_table('articles')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')

