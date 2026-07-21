"""027_base_col_comments

Fix missing comments on base columns (id/create_time/update_time/is_deleted)
in book_damage_report table — autogenerate blind spot for inherited BaseModel
columns.

Context: Migration 026 created the table without comments on these 4 columns
because SA's autogenerate doesn't always propagate comments from abstract
base model columns. All business columns had comments; only the 4 base
columns inherited from BaseModel/TimestampMixin were missed.

Lesson: After any autogenerate migration, manually inspect whether
id/create_time/update_time/is_deleted comments were carried over.

Revision ID: 027_base_col_comments
Revises: 026_create_book_damage_report
Create Date: 2026-07-21 11:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "027_base_col_comments"
down_revision: Union[str, Sequence[str], None] = "026_create_book_damage_report"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "book_damage_report",
        "id",
        existing_type=sa.BigInteger(),
        existing_nullable=False,
        nullable=False,
        comment="主键",
    )
    op.alter_column(
        "book_damage_report",
        "create_time",
        existing_type=sa.DateTime(),
        existing_nullable=True,
        nullable=True,
        comment="创建时间",
    )
    op.alter_column(
        "book_damage_report",
        "update_time",
        existing_type=sa.DateTime(),
        existing_nullable=True,
        nullable=True,
        comment="更新时间",
    )
    op.alter_column(
        "book_damage_report",
        "is_deleted",
        existing_type=sa.SmallInteger(),
        existing_nullable=True,
        nullable=True,
        comment="软删除标记: 0=正常 1=已删除",
    )


def downgrade() -> None:
    op.alter_column(
        "book_damage_report",
        "id",
        existing_type=sa.BigInteger(),
        existing_nullable=False,
        nullable=False,
        comment=None,
    )
    op.alter_column(
        "book_damage_report",
        "create_time",
        existing_type=sa.DateTime(),
        existing_nullable=True,
        nullable=True,
        comment=None,
    )
    op.alter_column(
        "book_damage_report",
        "update_time",
        existing_type=sa.DateTime(),
        existing_nullable=True,
        nullable=True,
        comment=None,
    )
    op.alter_column(
        "book_damage_report",
        "is_deleted",
        existing_type=sa.SmallInteger(),
        existing_nullable=True,
        nullable=True,
        comment=None,
    )
