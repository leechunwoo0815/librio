"""035_book_waitlist_pickup_remind

Revision ID: f2c7e5b99d53
Revises: e6b1d4a88c42
Create Date: 2026-08-01 23:51:22.051494

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2c7e5b99d53'
down_revision: Union[str, Sequence[str], None] = 'e6b1d4a88c42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """F4 等候名单表 + B4 预约取书提醒标记"""
    op.create_table(
        "book_waitlist",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, comment="主键"),
        sa.Column("child_id", sa.BigInteger(), sa.ForeignKey("child.id"), nullable=False, comment="孩子ID"),
        sa.Column("book_id", sa.BigInteger(), sa.ForeignKey("book.id"), nullable=False, comment="图书ID"),
        sa.Column("status", sa.SmallInteger(), server_default="0", comment="等候状态"),
        sa.Column("notify_time", sa.DateTime(), nullable=True, comment="到货通知时间"),
        sa.Column("create_time", sa.DateTime(), server_default=sa.func.now(), comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), server_default=sa.func.now(), comment="更新时间"),
        sa.Column("is_deleted", sa.SmallInteger(), server_default="0", comment="软删除标记: 0=正常 1=已删除"),
    )
    op.create_index("ix_book_waitlist_child_id", "book_waitlist", ["child_id"])
    op.create_index("ix_book_waitlist_book_id", "book_waitlist", ["book_id"])
    op.add_column(
        "reservation",
        sa.Column(
            "pickup_reminded",
            sa.SmallInteger(),
            server_default="0",
            nullable=True,
            comment="取书提醒已发: 0=否 1=是（B4：到期前24h提醒）",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("reservation", "pickup_reminded")
    op.drop_index("ix_book_waitlist_book_id", table_name="book_waitlist")
    op.drop_index("ix_book_waitlist_child_id", table_name="book_waitlist")
    op.drop_table("book_waitlist")
