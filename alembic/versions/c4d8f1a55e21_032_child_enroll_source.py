"""032_child_enroll_source

Revision ID: c4d8f1a55e21
Revises: b7e9a2c44d10
Create Date: 2026-08-01 23:13:00.480824

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4d8f1a55e21"
down_revision: Union[str, Sequence[str], None] = "b7e9a2c44d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """child 增加 enroll_source 列（A1 双轨制报名来源标记）"""
    op.add_column(
        "child",
        sa.Column(
            "enroll_source",
            sa.SmallInteger(),
            server_default="0",
            nullable=True,
            comment="报名来源: 0=未知 1=亲子课转化 2=直接观察期（A1双轨制）",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("child", "enroll_source")
