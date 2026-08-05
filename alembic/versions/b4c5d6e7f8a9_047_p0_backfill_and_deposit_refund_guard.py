"""047 P0 补批：存量回填 + 押金退款单号分列/原额快照

Revision ID: b4c5d6e7f8a9
Revises: f3a2b1c0d9e8
Create Date: 2026-08-05

1. F77 存量回填：迁移 046 新增 fine_in_outstanding 后，老 OVERDUE 记录的罚款已由旧
   任务整体覆写进 child.outstanding_fines，但标记列=0 —— 不回填将导致首跑双计。
   回填 marker = fine_amount（仅 status=OVERDUE，is_deleted=0）。
2. F54：deposit_record.original_amount 原支付单金额快照（600 奖励退款扣减 amount 后，
   全额退款 total 仍用原额）。存量回填：partial_refunded=1 的按 amount+600 还原。
3. F76：deposit_record.partial_refund_no —— 600 奖励退款独立单号，与全额退款
   out_refund_no 分列，避免同一单号被两笔不同退款复用（微信幂等冲突）。
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b4c5d6e7f8a9"
down_revision = "f3a2b1c0d9e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # F77：老 OVERDUE 记录的罚款已被旧任务计入 outstanding，补标记防双计
    op.execute(
        """
        UPDATE borrow_record
        SET fine_in_outstanding = fine_amount
        WHERE status = 2
          AND fine_in_outstanding = 0
          AND is_deleted = 0
        """
    )
    # F54：原支付单金额快照（600 奖励退款默认退 600 元，A2 决策）
    op.add_column(
        "deposit_record",
        sa.Column(
            "original_amount",
            sa.Numeric(10, 2),
            nullable=True,
            comment="原支付单金额快照（F54：600 奖励退款后 amount 被扣减，退款 total 一律用原额）",
        ),
    )
    op.execute(
        """
        UPDATE deposit_record
        SET original_amount = CASE
            WHEN partial_refunded = 1 THEN amount + 600
            ELSE amount
        END
        WHERE original_amount IS NULL
        """
    )
    # F76：600 奖励退款独立单号
    op.add_column(
        "deposit_record",
        sa.Column(
            "partial_refund_no",
            sa.String(64),
            nullable=True,
            comment="600 奖励退款单号（F76：与全额退款 out_refund_no 分列，避免微信幂等键冲突）",
        ),
    )


def downgrade() -> None:
    op.drop_column("deposit_record", "partial_refund_no")
    op.drop_column("deposit_record", "original_amount")
