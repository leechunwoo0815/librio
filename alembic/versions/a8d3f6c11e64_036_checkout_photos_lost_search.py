"""036_checkout_photos_lost_search

Revision ID: a8d3f6c11e64
Revises: f2c7e5b99d53
Create Date: 2026-08-02 00:12:31.454109

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a8d3f6c11e64"
down_revision: Union[str, Sequence[str], None] = "f2c7e5b99d53"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """B9/B10：borrow_record 借出拍照 + 丢失寻找期；损坏报告状态注释对齐"""
    op.add_column(
        "borrow_record",
        sa.Column(
            "checkout_photos",
            sa.String(500),
            nullable=True,
            comment="借出时拍照存档（JSON数组：封面/封底/书脊，B9）",
        ),
    )
    op.add_column(
        "borrow_record",
        sa.Column(
            "lost_search_deadline",
            sa.DateTime(),
            nullable=True,
            comment="丢失寻找期截止（登记+7天，B10：期内找回免赔）",
        ),
    )
    op.alter_column(
        "book_damage_report",
        "status",
        existing_type=sa.SmallInteger(),
        comment="状态: 0=待申诉 1=已确认 2=申诉中 3=已冲正 4=待复核 5=复核驳回",
        existing_nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "book_damage_report",
        "status",
        existing_type=sa.SmallInteger(),
        comment="状态: 0=待申诉 1=已确认 2=申诉中 3=已冲正",
        existing_nullable=True,
    )
    op.drop_column("borrow_record", "lost_search_deadline")
    op.drop_column("borrow_record", "checkout_photos")
