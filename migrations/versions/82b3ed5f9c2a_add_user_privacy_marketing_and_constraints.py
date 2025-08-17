"""
Add marketing/privacy fields and useful constraints

Revision ID: 82b3ed5f9c2a
Revises: b40d92fc26ca
Create Date: 2025-08-14 15:25:00
"""

from alembic import op
import sqlalchemy as sa


revision = '82b3ed5f9c2a'
down_revision = 'b40d92fc26ca'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users: add columns if not present
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('marketing_opt_in', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('privacy_accepted_at', sa.DateTime(timezone=True), nullable=True))
        # Unique constraints (safe with NULLs on Postgres)
        batch_op.create_unique_constraint('uq_users_stripe_customer_id', ['stripe_customer_id'])
        batch_op.create_unique_constraint('uq_user_oauth_identity', ['oauth_provider', 'oauth_sub'])

    # Sessions: helpful composite index
    op.create_index('ix_sessions_user_created', 'sessions', ['user_id', 'created_at'], unique=False)


def downgrade() -> None:
    # Sessions index
    op.drop_index('ix_sessions_user_created', table_name='sessions')

    with op.batch_alter_table('users') as batch_op:
        # Drop constraints if they exist
        try:
            batch_op.drop_constraint('uq_user_oauth_identity', type_='unique')
        except Exception:
            pass
        try:
            batch_op.drop_constraint('uq_users_stripe_customer_id', type_='unique')
        except Exception:
            pass
        # Drop columns
        try:
            batch_op.drop_column('privacy_accepted_at')
        except Exception:
            pass
        try:
            batch_op.drop_column('marketing_opt_in')
        except Exception:
            pass


