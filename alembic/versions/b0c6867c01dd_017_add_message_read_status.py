"""017_add_message_read_status

Add MessageReadStatus table for per-user read tracking of shared messages.

Revision ID: b0c6867c01dd
Revises: df9d4a3f7a16
Create Date: 2026-07-08 19:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b0c6867c01dd"
down_revision: Union[str, None] = "df9d4a3f7a16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "message_read_status",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False, index=True, comment="消息ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, index=True, comment="用户ID"),
        sa.Column("create_time", sa.DateTime(), nullable=True),
        sa.Column("update_time", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.SmallInteger(), nullable=True),
        sa.ForeignKeyConstraint(["message_id"], ["system_message.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", "user_id", name="uq_message_read_mid_uid"),
    )


def downgrade() -> None:
    op.drop_table("message_read_status")
