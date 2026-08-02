"""030_add_fine_waiver_columns

Revision ID: a3f5c8d91e02
Revises: 18d299533269
Create Date: 2026-08-01 22:48:09.313460

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a3f5c8d91e02"
down_revision: Union[str, Sequence[str], None] = "18d299533269"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """borrow_record 增加首次免罚相关列（B7 决策）"""
    op.add_column(
        "borrow_record",
        sa.Column(
            "fine_original",
            sa.Numeric(10, 2),
            nullable=True,
            comment="免罚前计算金额（B7审计用）",
        ),
    )
    op.add_column(
        "borrow_record",
        sa.Column(
            "fine_waived",
            sa.SmallInteger(),
            server_default="0",
            nullable=True,
            comment="首次逾期免罚: 0=否 1=是（B7）",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("borrow_record", "fine_waived")
    op.drop_column("borrow_record", "fine_original")
