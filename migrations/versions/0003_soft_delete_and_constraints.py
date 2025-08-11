from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0003_soft_delete_and_constraints'
down_revision = '0002_model_improvements'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # users.deleted_at
    user_cols = {c['name'] for c in inspector.get_columns('users')}
    if 'deleted_at' not in user_cols:
        op.add_column('users', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
        op.create_index('ix_users_deleted_at', 'users', ['deleted_at'])

    # articles.deleted_at
    art_cols = {c['name'] for c in inspector.get_columns('articles')}
    if 'deleted_at' not in art_cols:
        op.add_column('articles', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
        op.create_index('ix_articles_deleted_at', 'articles', ['deleted_at'])

    # generations.deleted_at
    gen_cols = {c['name'] for c in inspector.get_columns('generations')}
    if 'deleted_at' not in gen_cols:
        op.add_column('generations', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
        op.create_index('ix_generations_deleted_at', 'generations', ['deleted_at'])

    # score check constraint (skip on sqlite which has limited alter table)
    if bind.dialect.name == 'postgresql':
        op.create_check_constraint(
            'ck_generations_score_range', 'generations', 'score >= 0 AND score <= 100'
        )


def downgrade() -> None:
    bind = op.get_bind()
    # drop check constraint if postgres
    if bind.dialect.name == 'postgresql':
        op.drop_constraint('ck_generations_score_range', 'generations')

    # drop indexes and columns
    op.drop_index('ix_generations_deleted_at', table_name='generations')
    op.drop_column('generations', 'deleted_at')

    op.drop_index('ix_articles_deleted_at', table_name='articles')
    op.drop_column('articles', 'deleted_at')

    op.drop_index('ix_users_deleted_at', table_name='users')
    op.drop_column('users', 'deleted_at')

