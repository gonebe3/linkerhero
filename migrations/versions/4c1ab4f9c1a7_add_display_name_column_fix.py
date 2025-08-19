"""
Revision ID: 4c1ab4f9c1a7
Revises: 3e4f99477fd5
Create Date: 2025-08-19 15:02:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '4c1ab4f9c1a7'
down_revision = '3e4f99477fd5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('display_name', sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'display_name')


