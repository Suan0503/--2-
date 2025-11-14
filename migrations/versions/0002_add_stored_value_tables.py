"""add stored value wallet and transactions

Revision ID: 0002_add_stored_value
Revises: 0001_add_tempverify_line_user_id
Create Date: 2025-11-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002_add_stored_value'
down_revision = '0001_add_tempverify_line_user_id'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'stored_value_wallet',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('whitelist_id', sa.Integer(), nullable=True, index=True),
        sa.Column('phone', sa.String(length=20), nullable=True, index=True),
        sa.Column('balance', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'stored_value_txn',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('wallet_id', sa.Integer(), nullable=False, index=True),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('remark', sa.Text(), nullable=True),
        sa.Column('coupon_500_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('coupon_300_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table('stored_value_txn')
    op.drop_table('stored_value_wallet')
