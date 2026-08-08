"""051 fine_payment 活跃缴款唯一（F-066）

Revision ID: a6b7c8d9e0f1
Revises: a5b6c7d8e9f0
Create Date: 2026-08-08

F-066：pay_fines 并发双单——应用层 child 行锁串行化为主，本迁移加 DB 兜底：
active_fine 生成列（status=0 且未软删时 child_id×1e6+amount 分），唯一索引
拦截同孩子同金额并发双 PENDING 单（amount 变化或终态可重入）。
开发库存量 0 行，无重复需清理。
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a6b7c8d9e0f1"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fine_payment",
        sa.Column(
            "active_fine",
            sa.BigInteger(),
            sa.Computed(
                "CASE WHEN status = 0 AND is_deleted = 0 "
                "THEN child_id * 1000000 + CAST(amount * 100 AS SIGNED) ELSE NULL END",
                persisted=True,
            ),
            nullable=True,
            comment="F-066：活跃缴款唯一键（PENDING 且未软删时 child×金额分，防并发双单）",
        ),
    )
    op.create_index(
        "uq_fine_payment_active",
        "fine_payment",
        ["active_fine"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_fine_payment_active", table_name="fine_payment")
    op.drop_column("fine_payment", "active_fine")
