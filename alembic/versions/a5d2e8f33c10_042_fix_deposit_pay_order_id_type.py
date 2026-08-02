"""042_fix_deposit_pay_order_id_type

Revision ID: a5d2e8f33c10
Revises: f4c1a7d88eb9
Create Date: 2026-08-02 22:43:13.891023

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a5d2e8f33c10"
down_revision: Union[str, Sequence[str], None] = "f4c1a7d88eb9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """审查 P0-1：deposit_record.pay_order_id BigInteger → String(64)

    历史遗留 bug：单号为 "DP"+24hex 字符串却定义在 BIGINT 列，
    MySQL 严格模式写入直接 DataError（HTTP 500）；非严格模式强转 0 导致回调失配。
    存量脏数据（被强转为 0 的行）置 NULL。
    """
    # 存量强转脏数据清零（0 不可能是合法单号）
    op.execute("UPDATE deposit_record SET pay_order_id = NULL WHERE pay_order_id = 0")
    op.alter_column(
        "deposit_record",
        "pay_order_id",
        existing_type=sa.BigInteger(),
        type_=sa.String(64),
        existing_nullable=True,
        comment="支付单号（DP前缀字符串，审查 P0-1 修正列类型）",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "deposit_record",
        "pay_order_id",
        existing_type=sa.String(64),
        type_=sa.BigInteger(),
        existing_nullable=True,
        comment="支付订单ID",
    )
