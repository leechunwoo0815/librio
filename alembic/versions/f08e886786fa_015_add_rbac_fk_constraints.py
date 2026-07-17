"""015_add_rbac_fk_constraints

Add FK constraints for admin.admin_role_id → role.id and admin.teacher_id → teacher.id

Revision ID: f08e886786fa
Revises: 8d36c82fb146
Create Date: 2026-07-08 15:51:39.550321

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f08e886786fa'
down_revision: Union[str, Sequence[str], None] = '8d36c82fb146'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        'fk_admin_role', 'admin', 'role',
        ['admin_role_id'], ['id'],
    )
    op.create_foreign_key(
        'fk_admin_teacher', 'admin', 'teacher',
        ['teacher_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_admin_role', 'admin', type_='foreignkey')
    op.drop_constraint('fk_admin_teacher', 'admin', type_='foreignkey')
