"""052 child.total_words_read 排行榜索引（F-064）

Revision ID: a7b8c9d0e1f2
Revises: a6b7c8d9e0f1
Create Date: 2026-08-08

排行榜按 total_words_read 排序，缺索引导致全表排序。
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "a7b8c9d0e1f2"
down_revision = "a6b7c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_child_total_words_read",
        "child",
        ["total_words_read"],
    )


def downgrade() -> None:
    op.drop_index("ix_child_total_words_read", table_name="child")
