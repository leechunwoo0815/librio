"""013_add_level_code

Revision ID: 05b82dd6e543
Revises: 2bf1809a4077
Create Date: 2026-07-07 12:44:11.071752

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '05b82dd6e543'
down_revision: Union[str, Sequence[str], None] = '2bf1809a4077'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为 level 表增加 code 字段，并从现有 name 中回填 A-Z 级别代码。"""
    op.add_column('level', sa.Column('code', sa.String(length=10), nullable=True, comment='级别代码（如 A-Z）'))
    op.create_index(op.f('ix_level_code'), 'level', ['code'], unique=False)

    # 回填：name 为单个大写字母时，code = name
    op.execute("""
        UPDATE level
        SET code = name
        WHERE name REGEXP '^[A-Z]$' AND is_deleted = 0
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_level_code'), table_name='level')
    op.drop_column('level', 'code')
