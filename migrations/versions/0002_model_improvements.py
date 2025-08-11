from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0002_model_improvements'
down_revision = '0001_init'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    inspector = inspect(bind)
    user_cols = {c['name'] for c in inspector.get_columns('users')}
    # updated_at columns (guarded)
    if 'updated_at' not in user_cols:
        op.add_column('users', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True))
    if 'plan' not in user_cols:
        op.add_column('users', sa.Column('plan', sa.String(length=50), nullable=False, server_default='free'))
    article_cols = {c['name'] for c in inspector.get_columns('articles')}
    if 'updated_at' not in article_cols:
        op.add_column('articles', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True))
    gen_cols = {c['name'] for c in inspector.get_columns('generations')}
    if 'updated_at' not in gen_cols:
        op.add_column('generations', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True))
    op.create_index('ix_users_created_at', 'users', ['created_at'])
    op.create_index('ix_users_updated_at', 'users', ['updated_at'])
    op.create_index('ix_articles_created_at', 'articles', ['created_at'])
    op.create_index('ix_articles_updated_at', 'articles', ['updated_at'])
    op.create_index('ix_generations_created_at', 'generations', ['created_at'])
    op.create_index('ix_generations_updated_at', 'generations', ['updated_at'])


def downgrade() -> None:
    op.drop_index('ix_generations_updated_at', table_name='generations')
    op.drop_index('ix_generations_created_at', table_name='generations')
    op.drop_index('ix_articles_updated_at', table_name='articles')
    op.drop_index('ix_articles_created_at', table_name='articles')
    op.drop_index('ix_users_updated_at', table_name='users')
    op.drop_index('ix_users_created_at', table_name='users')
    op.drop_column('generations', 'updated_at')
    op.drop_column('articles', 'updated_at')
    # Only drop 'plan' if it exists; safe for sqlite/postgres
    bind = op.get_bind()
    inspector = inspect(bind)
    user_cols = {c['name'] for c in inspector.get_columns('users')}
    if 'plan' in user_cols:
        op.drop_column('users', 'plan')
    op.drop_column('users', 'updated_at')
    # No custom types to drop after simplifying plan to string

