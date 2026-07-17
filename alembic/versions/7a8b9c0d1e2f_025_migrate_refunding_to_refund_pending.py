"""025_migrate_refunding_to_refund_pending

Revision ID: 7a8b9c0d1e2f
Revises: 96f200b6ed5a
Create Date: 2026-07-15 23:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '7a8b9c0d1e2f'
down_revision: Union[str, Sequence[str], None] = '96f200b6ed5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """迁移旧 REFUNDING(4) 记录到 REFUND_PENDING(6) — 新增审核环节前的数据对齐"""

    # deposit_record: REFUNDING(4) → REFUND_PENDING(6)
    op.execute(
        "UPDATE deposit_record SET status = 6 WHERE status = 4 AND is_deleted = 0"
    )
    # child.deposit_status: REFUNDING(4) → REFUND_PENDING(6)
    op.execute(
        "UPDATE child SET deposit_status = 6 WHERE deposit_status = 4 AND is_deleted = 0"
    )


def downgrade() -> None:
    """回退：REFUND_PENDING(6) → REFUNDING(4)"""
    op.execute(
        "UPDATE deposit_record SET status = 4 WHERE status = 6 AND is_deleted = 0"
    )
    op.execute(
        "UPDATE child SET deposit_status = 4 WHERE deposit_status = 6 AND is_deleted = 0"
    )
