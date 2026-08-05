"""046 P0 批次：罚款入账标记 + 退款单号持久化

Revision ID: f3a2b1c0d9e8
Revises: e9f8a7b6c5d4
Create Date: 2026-08-05

第二批审查 P0（F35/F36/F38）：
1. borrow_record.fine_in_outstanding — 已计入 child.outstanding_fines 的金额标记，
   逾期任务/还书按差额增量维护，不再覆写损坏/丢失罚款（F35/F36）。
2. refund_application.out_refund_no — 微信商户退款单号持久化，重试复用防重复退款（F38）。
3. deposit_record.out_refund_no — 同上，押金退款路径（F38）。
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f3a2b1c0d9e8"
down_revision = "e9f8a7b6c5d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "borrow_record",
        sa.Column(
            "fine_in_outstanding",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
            comment="已计入 child.outstanding_fines 的金额（F35/F36 差额增量防双计）",
        ),
    )
    op.add_column(
        "refund_application",
        sa.Column(
            "out_refund_no",
            sa.String(64),
            nullable=True,
            comment="微信商户退款单号（F38：申请时生成持久化，重试复用防重复退款）",
        ),
    )
    op.create_index(
        "ix_refund_application_out_refund_no",
        "refund_application",
        ["out_refund_no"],
    )
    op.add_column(
        "deposit_record",
        sa.Column(
            "out_refund_no",
            sa.String(64),
            nullable=True,
            comment="微信商户退款单号（F38：审核通过时生成持久化，重试复用防重复退款）",
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_refund_application_out_refund_no", table_name="refund_application"
    )
    op.drop_column("deposit_record", "out_refund_no")
    op.drop_column("refund_application", "out_refund_no")
    op.drop_column("borrow_record", "fine_in_outstanding")
