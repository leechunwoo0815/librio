"""043_checkin_unique_constraint

Revision ID: c4e5f6a7b8c9
Revises: a5d2e8f33c10
Create Date: 2026-08-03 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "a5d2e8f33c10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """审查 P0-1：check_in 加唯一约束 uq_checkin_child_date_type

    代码层"先查后插"存在 TOCTOU 竞态，并发下可插入重复打卡。
    DB 层唯一约束兜底（child_id + check_date + check_type 每日每类型最多 1 条）。
    先清理历史重复数据（每组保留最小 id），再建约束。
    """
    # 历史重复清理：同 child+date+type 保留最小 id（派生表兼容 MySQL）
    op.execute(
        """
        DELETE FROM check_in WHERE id NOT IN (
            SELECT min_id FROM (
                SELECT MIN(id) AS min_id FROM check_in
                GROUP BY child_id, check_date, check_type
            ) t
        )
        """
    )
    # batch 模式兼容 SQLite（ALTER TABLE 不支持 ADD CONSTRAINT）
    with op.batch_alter_table("check_in") as batch_op:
        batch_op.create_unique_constraint(
            "uq_checkin_child_date_type",
            ["child_id", "check_date", "check_type"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("check_in") as batch_op:
        batch_op.drop_constraint("uq_checkin_child_date_type", type_="unique")
