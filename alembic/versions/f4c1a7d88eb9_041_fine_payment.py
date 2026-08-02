"""041_fine_payment

Revision ID: f4c1a7d88eb9
Revises: e3b8d4a66da8
Create Date: 2026-08-02 09:15:56.242986

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f4c1a7d88eb9"
down_revision: Union[str, Sequence[str], None] = "e3b8d4a66da8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """B12：fine_payment 罚款缴纳记录表"""
    op.create_table(
        "fine_payment",
        sa.Column(
            "id", sa.BigInteger(), primary_key=True, autoincrement=True, comment="主键"
        ),
        sa.Column(
            "child_id",
            sa.BigInteger(),
            sa.ForeignKey("child.id"),
            nullable=False,
            comment="孩子ID",
        ),
        sa.Column(
            "amount", sa.Numeric(10, 2), nullable=False, comment="缴纳金额（元）"
        ),
        sa.Column("status", sa.SmallInteger(), server_default="0", comment="支付状态"),
        sa.Column("pay_order_no", sa.String(32), nullable=True, comment="支付单号"),
        sa.Column("pay_time", sa.DateTime(), nullable=True, comment="支付时间"),
        sa.Column(
            "create_time",
            sa.DateTime(),
            server_default=sa.func.now(),
            comment="创建时间",
        ),
        sa.Column(
            "update_time",
            sa.DateTime(),
            server_default=sa.func.now(),
            comment="更新时间",
        ),
        sa.Column(
            "is_deleted",
            sa.SmallInteger(),
            server_default="0",
            comment="软删除标记: 0=正常 1=已删除",
        ),
    )
    op.create_index("ix_fine_payment_child_id", "fine_payment", ["child_id"])
    op.create_index(
        "ix_fine_payment_pay_order_no", "fine_payment", ["pay_order_no"], unique=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_fine_payment_pay_order_no", table_name="fine_payment")
    op.drop_index("ix_fine_payment_child_id", table_name="fine_payment")
    op.drop_table("fine_payment")
