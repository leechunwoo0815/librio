"""044_child_exited_at_user_paid_member_ever

Revision ID: d5e6f7a8b9c0
Revises: c4e5f6a7b8c9
Create Date: 2026-08-03 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """终审 P1-2/P1-3：child.exited_at + user.paid_member_ever

    - exited_at：H5 数据保留计时基准（EXITED 迁移写入、复活清空），
      替代 child.update_time 代理（onupdate 会被后续字段更新刷新，导致 2 年计时永不触发）。
      存量 EXITED 行用 update_time 回填。
    - paid_member_ever：F5 多孩资格快照（会员类订单支付成功置 1），
      财务 purge 删除历史订单后资格仍有效。存量按已支付会员订单回填。
    """
    with op.batch_alter_table("child") as batch_op:
        batch_op.add_column(
            sa.Column(
                "exited_at",
                sa.DateTime(),
                nullable=True,
                comment="退出时间（H5 数据保留计时基准，EXITED 迁移时写入，复活清空）",
            )
        )
    # 存量 EXITED 行回填（用 update_time 作最佳近似）
    op.execute(
        "UPDATE child SET exited_at = update_time WHERE status = 4 AND exited_at IS NULL"
    )

    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(
            sa.Column(
                "paid_member_ever",
                sa.SmallInteger(),
                nullable=False,
                server_default="0",
                comment="是否曾有已支付会员订单（F5 多孩资格快照，财务 purge 后仍有效）",
            )
        )
    # 存量回填：有已支付会员类订单（type 2观察期/3正式/4季度/5半年，pay_status=1）的用户
    op.execute(
        """
        UPDATE `user` SET paid_member_ever = 1 WHERE id IN (
            SELECT uid FROM (
                SELECT DISTINCT user_id AS uid FROM `order`
                WHERE type IN (2, 3, 4, 5) AND pay_status = 1 AND is_deleted = 0
            ) t
        )
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("paid_member_ever")
    with op.batch_alter_table("child") as batch_op:
        batch_op.drop_column("exited_at")
