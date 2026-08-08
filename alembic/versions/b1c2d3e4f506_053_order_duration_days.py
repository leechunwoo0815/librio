"""053 order.duration_days 会员时长快照（F-050）

F-050：会员激活时长此前在支付回调时实时读配置（member_days/observation_days），
而订单金额在下单时冻结——配置变更窗口（尤其迟到支付 CLOSED→PAID）会导致
"按旧价付款却按新配置得时长"。新增时长快照列，下单时与金额同冻结。

存量订单为 NULL：handler/退款计算以快照优先、配置兜底（行为与上线前一致）。

Revision ID: b1c2d3e4f506
Revises: a7b8c9d0e1f2
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b1c2d3e4f506"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "order",
        sa.Column(
            "duration_days",
            sa.SmallInteger(),
            nullable=True,
            comment="F-050 会员时长快照（下单时冻结：观察期/年费/季度/半年总天数，与金额同冻结时点）",
        ),
    )


def downgrade() -> None:
    op.drop_column("order", "duration_days")
