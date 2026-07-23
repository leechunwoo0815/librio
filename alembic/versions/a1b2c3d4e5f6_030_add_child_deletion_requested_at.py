"""030_add_child_deletion_requested_at

Revision ID: a1b2c3d4e5f6
Revises: f1e2d3c4b5a6
Create Date: 2026-07-23

P0-3 数据删除权：child 表加删除请求冷静期标记
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f1e2d3c4b5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "child",
        sa.Column(
            "deletion_requested_at",
            sa.DateTime(),
            nullable=True,
            comment="数据删除请求时间（24h冷静期，NULL=无进行中请求）",
        ),
    )


def downgrade() -> None:
    op.drop_column("child", "deletion_requested_at")
