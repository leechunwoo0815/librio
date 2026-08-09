"""056 audio active unique (F-119 DB 兜底)

Revision ID: e4f506172839
Revises: d3e4f5061728
Create Date: 2026-08-09

F-119：同书同页（或 page NULL=全文）音频唯一。应用层查重为主；
本迁移加生成列唯一索引兜底并发双插（NULL 不参与唯一，软删后释放）。
开发库存量 0 行，无重复需清理。
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e4f506172839"
down_revision = "d3e4f5061728"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audio_file",
        sa.Column(
            "active_audio_key",
            sa.BigInteger(),
            sa.Computed(
                "CASE WHEN is_deleted = 0 AND book_id IS NOT NULL "
                "THEN book_id * 10000 + COALESCE(page_number, -1) ELSE NULL END",
                persisted=True,
            ),
            nullable=True,
            comment="F-119：同书同页音频唯一键（未软删且已关联图书时非 NULL，DB 兜底防并发双插）",
        ),
    )
    op.create_index(
        "uq_audio_active_key",
        "audio_file",
        ["active_audio_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_audio_active_key", table_name="audio_file")
    op.drop_column("audio_file", "active_audio_key")
