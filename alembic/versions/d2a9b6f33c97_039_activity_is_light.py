"""039_activity_is_light

Revision ID: d2a9b6f33c97
Revises: c1f8a3e55b86
Create Date: 2026-08-02 08:43:32.230217

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2a9b6f33c97'
down_revision: Union[str, Sequence[str], None] = 'c1f8a3e55b86'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """E4：activity.is_light 轻量模式"""
    op.add_column(
        "activity",
        sa.Column(
            "is_light",
            sa.SmallInteger(),
            server_default="0",
            nullable=True,
            comment="轻量模式: 0=正式 1=轻量（E4：报名自动通过+免签到）",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("activity", "is_light")
