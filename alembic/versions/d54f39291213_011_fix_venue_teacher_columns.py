"""011_fix_venue_teacher_columns

Revision ID: d54f39291213
Revises: v31_omo_tables
Create Date: 2026-07-07 12:35:14.728195

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d54f39291213"
down_revision: Union[str, Sequence[str], None] = "v31_omo_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """补齐 venue/teacher 表缺失字段，与 SQLAlchemy Model 保持一致。"""
    # venue 表
    op.add_column(
        "venue",
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=True,
            server_default="active",
            comment="运营状态: active=运营中 maintenance=维护中 inactive=已关闭",
        ),
    )
    op.add_column(
        "venue",
        sa.Column(
            "capacity",
            sa.BigInteger(),
            nullable=True,
            server_default="0",
            comment="容量/工位数",
        ),
    )

    # teacher 表
    op.add_column(
        "teacher",
        sa.Column(
            "english_name", sa.String(length=50), nullable=True, comment="英文名"
        ),
    )
    op.add_column(
        "teacher",
        sa.Column("title", sa.String(length=50), nullable=True, comment="职称"),
    )
    op.add_column(
        "teacher",
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=True,
            server_default="online",
            comment="在线状态: online=在线 offline=离线 leave=休假中",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("teacher", "status")
    op.drop_column("teacher", "title")
    op.drop_column("teacher", "english_name")
    op.drop_column("venue", "capacity")
    op.drop_column("venue", "status")
