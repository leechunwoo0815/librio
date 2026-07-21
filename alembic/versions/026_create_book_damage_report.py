"""026_create_book_damage_report

Create book_damage_report table for T3.6a damage assessment workflow.

Revision ID: 026_create_book_damage_report
Revises: f7ad15b0e774
Create Date: 2026-07-21 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "026_create_book_damage_report"
down_revision: Union[str, Sequence[str], None] = "f7ad15b0e774"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "book_damage_report",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "borrow_record_id",
            sa.BigInteger(),
            nullable=False,
            index=True,
            comment="关联借阅记录ID",
        ),
        sa.Column(
            "book_copy_id",
            sa.BigInteger(),
            nullable=True,
            index=True,
            comment="关联副本ID",
        ),
        sa.Column(
            "child_id", sa.BigInteger(), nullable=False, index=True, comment="孩子ID"
        ),
        sa.Column(
            "damage_level",
            sa.SmallInteger(),
            nullable=False,
            comment="定级: 1=轻度免费 2=重度0.5×定价 3=丢失1.5×定价",
        ),
        sa.Column("photo_url", sa.String(500), nullable=True, comment="损坏照片URL"),
        sa.Column("description", sa.Text(), nullable=True, comment="定责说明"),
        sa.Column(
            "fine_amount", sa.Numeric(10, 2), nullable=True, comment="罚款金额（元）"
        ),
        sa.Column(
            "status",
            sa.SmallInteger(),
            nullable=True,
            comment="状态: 0=待申诉 1=已确认 2=申诉中 3=已冲正",
        ),
        sa.Column("admin_id", sa.BigInteger(), nullable=True, comment="登记管理员ID"),
        sa.Column("appeal_reason", sa.Text(), nullable=True, comment="申诉理由"),
        sa.Column("appeal_result", sa.Text(), nullable=True, comment="申诉处理结果"),
        sa.Column(
            "override_level", sa.SmallInteger(), nullable=True, comment="冲正后定级"
        ),
        sa.Column(
            "override_fine", sa.Numeric(10, 2), nullable=True, comment="冲正后罚款金额"
        ),
        sa.Column(
            "review_admin_id",
            sa.BigInteger(),
            nullable=True,
            comment="申诉/冲正审核管理员ID",
        ),
        sa.Column("reviewed_at", sa.String(30), nullable=True, comment="审核时间"),
        sa.Column("create_time", sa.DateTime(), nullable=True),
        sa.Column("update_time", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.SmallInteger(), nullable=True),
        sa.ForeignKeyConstraint(["borrow_record_id"], ["borrow_record.id"]),
        sa.ForeignKeyConstraint(["book_copy_id"], ["book_copy.id"]),
        sa.ForeignKeyConstraint(["child_id"], ["child.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("book_damage_report")
