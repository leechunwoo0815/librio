"""050 child 毕业提醒独立留痕年份（F23）

Revision ID: a5b6c7d8e9f0
Revises: d8e9f0a1b2c3
Create Date: 2026-08-07

F23：14 岁毕业提醒的"每年最多 1 条"防重原先依赖近 365 天消息，而 purge 的消息类
清理（data_retention_message_years=1 年）会对所有用户物理删除旧消息——防重证据被
抹掉后，静态 age 下提醒会反复发送。改为 child.grad_remind_year 独立留痕（自然年
去重），不受消息保留期影响。存量数据无需回填（NULL = 未留痕，首次运行按当年提醒）。
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a5b6c7d8e9f0"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "child",
        sa.Column(
            "grad_remind_year",
            sa.Integer(),
            nullable=True,
            comment="F23：14岁毕业提醒最近发送年份（自然年去重，独立于消息保留期）",
        ),
    )


def downgrade() -> None:
    op.drop_column("child", "grad_remind_year")
