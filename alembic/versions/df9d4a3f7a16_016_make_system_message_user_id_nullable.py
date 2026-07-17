"""016_make_system_message_user_id_nullable

Make SystemMessage.user_id nullable for role-based shared messages.
Backfill target_role_codes = ["trial","observation","member"] on existing "all-user" messages.

Revision ID: df9d4a3f7a16
Revises: f08e886786fa
Create Date: 2026-07-08 19:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "df9d4a3f7a16"
down_revision: Union[str, None] = "f08e886786fa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make user_id nullable
    with op.batch_alter_table("system_message") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.BigInteger(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("system_message") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.BigInteger(), nullable=False)
