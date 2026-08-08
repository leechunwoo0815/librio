"""054 提醒去重标记三列（F-085/F-098/F-110）

参照 R132 pickup_reminded 正确范本（B4"提醒一次"语义）：
  - reading_submission.pending_reminded：待审超时提醒已发送标记（F-085）
  - borrow_record.overdue_reminded：逾期提醒已发送标记（F-098）
  - refund_application.stale_alerted：退款超时告警已发送标记（F-110）
存量默认 0=未提醒，无需回填（上线后首次任务/手动触发即按未提醒处理）。

Revision ID: c2d3e4f50617
Revises: b1c2d3e4f506
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c2d3e4f50617"
down_revision = "b1c2d3e4f506"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reading_submission",
        sa.Column(
            "pending_reminded",
            sa.SmallInteger(),
            nullable=False,
            server_default="0",
            comment="F-085：待审超时提醒已发送标记（0=未提醒 1=已提醒，去重防轰炸）",
        ),
    )
    op.add_column(
        "borrow_record",
        sa.Column(
            "overdue_reminded",
            sa.SmallInteger(),
            nullable=False,
            server_default="0",
            comment="F-098：逾期提醒已发送标记（0=未提醒 1=已提醒）",
        ),
    )
    op.add_column(
        "refund_application",
        sa.Column(
            "stale_alerted",
            sa.SmallInteger(),
            nullable=False,
            server_default="0",
            comment="F-110：退款超时告警已发送标记（0=未告警 1=已告警，去重防轰炸）",
        ),
    )


def downgrade() -> None:
    op.drop_column("refund_application", "stale_alerted")
    op.drop_column("borrow_record", "overdue_reminded")
    op.drop_column("reading_submission", "pending_reminded")
