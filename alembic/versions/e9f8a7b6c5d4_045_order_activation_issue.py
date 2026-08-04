"""045_order_activation_issue

Revision ID: e9f8a7b6c5d4
Revises: d5e6f7a8b9c0
Create Date: 2026-08-04 20:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e9f8a7b6c5d4"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """F7：order.activation_issue — 支付成功但会员未激活的对账标记"""
    with op.batch_alter_table("order") as batch_op:
        batch_op.add_column(
            sa.Column(
                "activation_issue",
                sa.SmallInteger(),
                nullable=False,
                server_default="0",
                comment="支付成功但会员未激活标记: 0=正常 1=待人工处理（F7 对账任务扫描）",
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("order") as batch_op:
        batch_op.drop_column("activation_issue")
