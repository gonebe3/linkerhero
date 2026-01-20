"""
Revision ID: 7e2679376dc4
Revises: ad5aacb8ae1f
Create Date: 2026-01-20 12:38:32.759019
"""

from alembic import op
import sqlalchemy as sa



revision = '7e2679376dc4'
down_revision = 'ad5aacb8ae1f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('full_name', sa.String(length=200), nullable=True))
    op.add_column('users', sa.Column('profile_image_url', sa.String(length=2000), nullable=True))
    op.add_column('users', sa.Column('profile_source', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'profile_source')
    op.drop_column('users', 'profile_image_url')
    op.drop_column('users', 'full_name')

