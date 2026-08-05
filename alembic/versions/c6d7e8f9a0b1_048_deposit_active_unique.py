"""048 押金活跃唯一索引（F68 并发双单兜底）

Revision ID: c6d7e8f9a0b1
Revises: b4c5d6e7f8a9
Create Date: 2026-08-05

pay_deposit 的"先查后插"在无记录并发时无锁可谈（F68），需要 DB 唯一约束兜底。
MySQL 无部分索引，用生成列：status ∈ (PENDING=5, PAID=1, REFUNDING=4, REFUND_PENDING=6)
时为 child_id，否则 NULL——唯一索引下 NULL 不冲突，非活跃态可重复。
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c6d7e8f9a0b1"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 先处理存量重复活跃押金：同 child 多活跃记录保留最新，其余置 UNPAID（数据修复）
    op.execute(
        """
        UPDATE deposit_record d
        JOIN (
            SELECT child_id, MAX(id) AS keep_id
            FROM deposit_record
            WHERE status IN (5, 1, 4, 6) AND is_deleted = 0
            GROUP BY child_id
            HAVING COUNT(*) > 1
        ) dup ON d.child_id = dup.child_id AND d.id < dup.keep_id
        SET d.status = 0
        """
    )
    op.add_column(
        "deposit_record",
        sa.Column(
            "active_child_id",
            sa.BigInteger(),
            sa.Computed(
                "CASE WHEN status IN (5,1,4,6) THEN child_id ELSE NULL END",
                persisted=True,
            ),
            nullable=True,
            comment="F68：活跃押金唯一键（UNPAID 等非活跃态为 NULL，唯一索引防并发双单）",
        ),
    )
    op.create_index(
        "uq_deposit_active_child",
        "deposit_record",
        ["active_child_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_deposit_active_child", table_name="deposit_record")
    op.drop_column("deposit_record", "active_child_id")
