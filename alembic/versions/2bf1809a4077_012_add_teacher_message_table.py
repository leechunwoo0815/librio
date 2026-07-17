"""012_add_teacher_message_table

Revision ID: 2bf1809a4077
Revises: d54f39291213
Create Date: 2026-07-07 12:40:52.947553

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2bf1809a4077"
down_revision: Union[str, Sequence[str], None] = "d54f39291213"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 teacher_message 表，与管理端消息发送功能保持一致。"""
    op.create_table(
        "teacher_message",
        sa.Column(
            "id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"
        ),
        sa.Column("teacher_id", sa.BigInteger(), nullable=False, comment="老师ID"),
        sa.Column("title", sa.String(length=100), nullable=False, comment="标题"),
        sa.Column("content", sa.Text(), nullable=False, comment="内容"),
        sa.Column(
            "msg_type",
            sa.SmallInteger(),
            nullable=True,
            comment="1=系统通知 2=活动通知 3=借阅通知 4=老师消息 5=阅读提醒",
        ),
        sa.Column(
            "priority", sa.SmallInteger(), nullable=True, comment="0=低 1=中 2=高"
        ),
        sa.Column("is_read", sa.SmallInteger(), nullable=True, comment="0=未读 1=已读"),
        sa.Column("create_time", sa.DateTime(), nullable=True, comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=True, comment="更新时间"),
        sa.Column(
            "is_deleted",
            sa.SmallInteger(),
            nullable=True,
            comment="软删除标记: 0=正常 1=已删除",
        ),
        sa.ForeignKeyConstraint(
            ["teacher_id"],
            ["teacher.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_comment="老师消息通知表",
    )
    op.create_index(
        op.f("ix_teacher_message_teacher_id"),
        "teacher_message",
        ["teacher_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_teacher_message_teacher_id"), table_name="teacher_message")
    op.drop_table("teacher_message")
