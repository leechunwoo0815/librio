"""033_refund_fine_deducted_order_nullable

Revision ID: d5a9c3e77f31
Revises: c4d8f1a55e21
Create Date: 2026-08-01 23:23:10.282367

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5a9c3e77f31'
down_revision: Union[str, Sequence[str], None] = 'c4d8f1a55e21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """refund_application: fine_deducted 列（E7）+ order_id 可空（E5 活动退款）"""
    op.add_column(
        "refund_application",
        sa.Column(
            "fine_deducted",
            sa.Numeric(10, 2),
            server_default="0",
            nullable=True,
            comment="退款中抵扣的未缴罚款（E7/B11：先扣罚款再退余额）",
        ),
    )
    op.alter_column(
        "refund_application",
        "order_id",
        existing_type=sa.BigInteger(),
        nullable=True,
        comment="关联订单ID（活动取消退款无订单，E5）",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "refund_application",
        "order_id",
        existing_type=sa.BigInteger(),
        nullable=False,
        comment="关联订单ID",
    )
    op.drop_column("refund_application", "fine_deducted")
