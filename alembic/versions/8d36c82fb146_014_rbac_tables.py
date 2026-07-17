"""014_rbac_tables

Revision ID: 014_rbac_tables
Revises: 05b82dd6e543
Create Date: 2026-07-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8d36c82fb146'
down_revision: Union[str, Sequence[str], None] = '05b82dd6e543'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. role 表
    op.create_table('role',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=32), nullable=False, comment='角色代码: super_admin / staff / teacher'),
        sa.Column('name', sa.String(length=50), nullable=False, comment='角色名称'),
        sa.Column('description', sa.String(length=255), nullable=True, comment='角色描述'),
        sa.Column('is_system', sa.Boolean(), nullable=True, comment='系统内置不可删'),
        sa.Column('sort_order', sa.Integer(), nullable=True, comment='排序'),
        sa.Column('create_time', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.Column('update_time', sa.DateTime(), nullable=True, comment='更新时间'),
        sa.Column('is_deleted', sa.SmallInteger(), nullable=True, comment='软删除标记: 0=正常 1=已删除'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
    )

    # 2. permission 表
    op.create_table('permission',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False, comment='权限代码: group.action'),
        sa.Column('name', sa.String(length=50), nullable=False, comment='权限名称'),
        sa.Column('group_name', sa.String(length=32), nullable=False, comment='分组名称'),
        sa.Column('description', sa.String(length=255), nullable=True, comment='权限描述'),
        sa.Column('is_system', sa.Boolean(), nullable=True, comment='系统内置不可删'),
        sa.Column('sort_order', sa.Integer(), nullable=True, comment='排序'),
        sa.Column('create_time', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.Column('update_time', sa.DateTime(), nullable=True, comment='更新时间'),
        sa.Column('is_deleted', sa.SmallInteger(), nullable=True, comment='软删除标记: 0=正常 1=已删除'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
    )

    # 3. role_permission 表
    op.create_table('role_permission',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('role_id', sa.BigInteger(), sa.ForeignKey('role.id'), nullable=False, comment='角色ID'),
        sa.Column('permission_code', sa.String(length=64), nullable=False, comment='权限代码'),
        sa.Column('create_time', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.Column('update_time', sa.DateTime(), nullable=True, comment='更新时间'),
        sa.Column('is_deleted', sa.SmallInteger(), nullable=True, comment='软删除标记: 0=正常 1=已删除'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role_id', 'permission_code', name='uk_role_perm'),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
    )

    # 4. admin 表新增字段
    op.add_column('admin', sa.Column('admin_role_id', sa.BigInteger(), nullable=True, comment='RBAC角色ID (引用 role.id)'))
    op.add_column('admin', sa.Column('teacher_id', sa.BigInteger(), nullable=True, comment='关联教师ID (role=teacher时必填)'))

    # 5. system_message 表新增字段
    op.add_column('system_message', sa.Column('target_role_codes', sa.JSON(), nullable=True, comment='可见角色code列表, null=全部可见'))


def downgrade() -> None:
    op.drop_column('system_message', 'target_role_codes')
    op.drop_column('admin', 'teacher_id')
    op.drop_column('admin', 'admin_role_id')
    op.drop_table('role_permission')
    op.drop_table('permission')
    op.drop_table('role')
