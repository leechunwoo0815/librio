"""038_observation_report_d6

Revision ID: c1f8a3e55b86
Revises: b9e4c7d22f75
Create Date: 2026-08-02 00:59:34.936122

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1f8a3e55b86'
down_revision: Union[str, Sequence[str], None] = 'b9e4c7d22f75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """D6：观察期报告转化导向字段"""
    op.add_column(
        "observation_report",
        sa.Column("streak_days", sa.Integer(), server_default="0", nullable=True, comment="连续打卡天数（进步曲线）"),
    )
    op.add_column(
        "observation_report",
        sa.Column("new_vocab_count", sa.Integer(), server_default="0", nullable=True, comment="观察期新增生词数"),
    )
    op.add_column(
        "observation_report",
        sa.Column("peer_avg_books", sa.Numeric(5, 1), nullable=True, comment="同龄孩子平均读完本数"),
    )
    op.add_column(
        "observation_report",
        sa.Column("cta_text", sa.String(255), nullable=True, comment="续费引导文案（D6）"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("observation_report", "cta_text")
    op.drop_column("observation_report", "peer_avg_books")
    op.drop_column("observation_report", "new_vocab_count")
    op.drop_column("observation_report", "streak_days")
