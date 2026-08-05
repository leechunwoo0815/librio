"""049 等候名单活跃唯一 + 订单 trade_no 唯一（F71-⑥/F26）

Revision ID: d8e9f0a1b2c3
Revises: c6d7e8f9a0b1
Create Date: 2026-08-05

1. F71-⑥：book_waitlist 并发重复入队——生成列 child_id*1e6+book_id 仅在
   WAITING(0)/NOTIFIED(1) 非 NULL，唯一索引兜底（FULFILLED/CANCELLED 可重入）。
2. F26：order.trade_no 唯一（第三方流水号重复 = 同一笔支付被两次入账）。
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d8e9f0a1b2c3"
down_revision = "c6d7e8f9a0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "book_waitlist",
        sa.Column(
            "active_child_book",
            sa.BigInteger(),
            sa.Computed(
                "CASE WHEN status IN (0,1) THEN child_id * 1000000 + book_id ELSE NULL END",
                persisted=True,
            ),
            nullable=True,
            comment="F71-⑥：活跃等候唯一键（WAITING/NOTIFIED 时 child×book，防并发重复入队）",
        ),
    )
    op.create_index(
        "uq_book_waitlist_active",
        "book_waitlist",
        ["active_child_book"],
        unique=True,
    )
    op.create_index(
        "uq_order_trade_no",
        "order",
        ["trade_no"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_order_trade_no", table_name="order")
    op.drop_index("uq_book_waitlist_active", table_name="book_waitlist")
    op.drop_column("book_waitlist", "active_child_book")
