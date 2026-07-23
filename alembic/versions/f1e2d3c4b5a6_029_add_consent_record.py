"""029_add_consent_record

Revision ID: f1e2d3c4b5a6
Revises: 5a5e91684fe9
Create Date: 2026-07-23 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1e2d3c4b5a6"
down_revision: Union[str, Sequence[str], None] = "5a5e91684fe9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "consent_record",
        sa.Column(
            "id", sa.BigInteger(), primary_key=True, autoincrement=True, comment="主键"
        ),
        sa.Column(
            "user_id", sa.BigInteger(), nullable=False, index=True, comment="用户ID"
        ),
        sa.Column(
            "consent_type",
            sa.String(50),
            nullable=False,
            comment="同意类型: privacy_policy/child_data/voice_recording",
        ),
        sa.Column(
            "consent_text_hash",
            sa.String(64),
            nullable=False,
            comment="同意文案SHA-256哈希，追溯当时版本",
        ),
        sa.Column(
            "consent_version", sa.String(20), nullable=False, comment="隐私政策版本号"
        ),
        sa.Column("ip_address", sa.String(45), nullable=True, comment="IP地址"),
        sa.Column("user_agent", sa.String(500), nullable=True, comment="User-Agent"),
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
            onupdate=sa.func.now(),
            comment="更新时间",
        ),
        sa.Column(
            "is_deleted",
            sa.SmallInteger(),
            server_default="0",
            comment="软删除标记: 0=正常 1=已删除",
        ),
        sa.Column(
            "withdrawn_at", sa.DateTime(), nullable=True, comment="撤回时间，NULL=有效"
        ),
        sa.Index("idx_consent_user_type", "user_id", "consent_type"),
        sa.Index("idx_consent_created", "create_time"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("consent_record")
