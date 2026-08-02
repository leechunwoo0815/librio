"""031_align_fine_amount_comment

Revision ID: b7e9a2c44d10
Revises: a3f5c8d91e02
Create Date: 2026-08-01 23:07:17.205245

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7e9a2c44d10"
down_revision: Union[str, Sequence[str], None] = "a3f5c8d91e02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """对齐 borrow_record.fine_amount 注释（B7 措辞：逾期服务费）"""
    op.alter_column(
        "borrow_record",
        "fine_amount",
        existing_type=sa.Numeric(10, 2),
        comment="逾期服务费（实际应收）",
        existing_nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "borrow_record",
        "fine_amount",
        existing_type=sa.Numeric(10, 2),
        comment="逾期罚款",
        existing_nullable=True,
    )
