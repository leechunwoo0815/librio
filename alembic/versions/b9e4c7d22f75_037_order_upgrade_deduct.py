"""037_order_upgrade_deduct

Revision ID: b9e4c7d22f75
Revises: a8d3f6c11e64
Create Date: 2026-08-02 00:39:24.426098

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9e4c7d22f75'
down_revision: Union[str, Sequence[str], None] = 'a8d3f6c11e64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """A6：order.upgrade_deduct 升级抵扣金额"""
    op.add_column(
        "order",
        sa.Column(
            "upgrade_deduct",
            sa.Numeric(10, 2),
            server_default="0",
            nullable=True,
            comment="升级抵扣金额（A6：观察期剩余价值冲抵会员费）",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("order", "upgrade_deduct")
