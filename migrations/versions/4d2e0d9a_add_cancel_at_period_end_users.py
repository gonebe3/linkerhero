"""
Add cancel_at_period_end to users

Revision ID: 4d2e0d9a
Revises: f8c45298c948
Create Date: 2025-08-21
"""

from alembic import op
import sqlalchemy as sa


revision = '4d2e0d9a'
down_revision = '4c1ab4f9c1a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute('ALTER TABLE users ALTER COLUMN cancel_at_period_end DROP DEFAULT')


def downgrade() -> None:
    op.drop_column('users', 'cancel_at_period_end')


