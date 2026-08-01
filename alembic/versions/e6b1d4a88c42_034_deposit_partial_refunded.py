"""034_deposit_partial_refunded

Revision ID: e6b1d4a88c42
Revises: d5a9c3e77f31
Create Date: 2026-08-01 23:31:02.725424

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6b1d4a88c42'
down_revision: Union[str, Sequence[str], None] = 'd5a9c3e77f31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """deposit_record.partial_refunded（A2 押金减半退还标记）"""
    op.add_column(
        "deposit_record",
        sa.Column(
            "partial_refunded",
            sa.SmallInteger(),
            server_default="0",
            nullable=True,
            comment="已减半退还: 0=否 1=是（A2：借满N本无逾期可退一半）",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("deposit_record", "partial_refunded")
