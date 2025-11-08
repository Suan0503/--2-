"""add line_user_id to temp_verify

Revision ID: 0001_add_tempverify_line_user_id
Revises: 
Create Date: 2025-11-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '0001_add_tempverify_line_user_id'
down_revision = None
branch_labels = None
depends_on = None


def _has_column(bind, table_name, column_name):
    insp = inspect(bind)
    try:
        cols = [c['name'] for c in insp.get_columns(table_name)]
        return column_name in cols
    except Exception:
        return False


def upgrade():
    bind = op.get_bind()
    if not _has_column(bind, 'temp_verify', 'line_user_id'):
        op.add_column('temp_verify', sa.Column('line_user_id', sa.String(length=255)))


def downgrade():
    bind = op.get_bind()
    if _has_column(bind, 'temp_verify', 'line_user_id'):
        try:
            op.drop_column('temp_verify', 'line_user_id')
        except Exception:
            # some dialects may require separate handling; ignore failure to keep downgrade safe
            pass
