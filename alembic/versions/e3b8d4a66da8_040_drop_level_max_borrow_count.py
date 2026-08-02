"""040_drop_level_max_borrow_count

Revision ID: e3b8d4a66da8
Revises: d2a9b6f33c97
Create Date: 2026-08-02 09:00:32.553058

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e3b8d4a66da8"
down_revision: Union[str, Sequence[str], None] = "d2a9b6f33c97"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """H2：level.max_borrow_count 移除（借阅上限统一走全局 borrow_limit 配置）"""
    op.drop_column("level", "max_borrow_count")
    op.alter_column(
        "level",
        "max_ar_level",
        existing_type=sa.Numeric(3, 1),
        comment="最大可读AR等级（H2：超限标'挑战'徽标）",
        existing_nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "level",
        sa.Column(
            "max_borrow_count",
            sa.Integer(),
            server_default="1",
            nullable=True,
            comment="最大同时借阅数",
        ),
    )
