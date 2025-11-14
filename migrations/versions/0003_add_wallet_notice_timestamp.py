"""add last_coupon_notice_at to wallet

Revision ID: 0003_add_wallet_notice
Revises: 0002_add_stored_value
Create Date: 2025-11-14 00:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003_add_wallet_notice'
down_revision = '0002_add_stored_value'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('stored_value_wallet') as batch_op:
        batch_op.add_column(sa.Column('last_coupon_notice_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('stored_value_wallet') as batch_op:
        batch_op.drop_column('last_coupon_notice_at')
