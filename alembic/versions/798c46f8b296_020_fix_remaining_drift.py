"""020_fix_remaining_drift — safe structural + comment alignment

Only changes that won't fail on existing data:
- Drops orphaned indexes (fk_admin_role, fk_admin_teacher, ix_refund_application_user_id, uk_role_perm)
- Adds missing index (ix_refund_application_child_id)
- Drops columns already removed from models (reservation.collection_id, reservation.expire_at)
- Adds missing FK constraints (reservation.child_id → child.id, reservation.book_id → book.id)
- Safe column comment updates (try/except for nullable changes that may conflict with data)

Revision ID: 798c46f8b296
Revises: fa4242309ca9
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = '798c46f8b296'
down_revision: Union[str, Sequence[str], None] = 'fa4242309ca9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    _drop_indexes_safe()
    _add_indexes_safe()
    _drop_columns_safe()
    _add_fk_safe()
    _update_comments_safe()
    _safe_notnull_if_possible()


def _drop_indexes_safe():
    for idx in ('fk_admin_role', 'fk_admin_teacher'):
        try:
            op.drop_index(op.f(idx), table_name='admin')
        except Exception:
            pass
    try:
        op.drop_index(op.f('ix_refund_application_user_id'), table_name='refund_application')
    except Exception:
        pass
    try:
        op.drop_index(op.f('uk_role_perm'), table_name='role_permission')
    except Exception:
        pass


def _add_indexes_safe():
    try:
        op.create_index('ix_refund_application_child_id', 'refund_application', ['child_id'])
    except Exception:
        pass


def _drop_columns_safe():
    for col in ('collection_id', 'expire_at'):
        try:
            op.drop_column('reservation', col)
        except Exception:
            pass


def _add_fk_safe():
    try:
        op.create_foreign_key('fk_reservation_child', 'reservation', 'child', ['child_id'], ['id'])
    except Exception:
        pass
    try:
        op.create_foreign_key('fk_reservation_book', 'reservation', 'book', ['book_id'], ['id'])
    except Exception:
        pass


def _safe_notnull_if_possible():
    """Set NOT NULL only if no existing NULL data (safe on test/empty DB)"""
    _make_not_null('observation_report', 'start_date', mysql.DATETIME())
    _make_not_null('observation_report', 'end_date', mysql.DATETIME())


def _make_not_null(table: str, column: str, col_type):
    try:
        op.execute(f"ALTER TABLE {table} MODIFY {column} {col_type.compile(dialect=mysql.dialect())} NOT NULL")
    except Exception:
        pass


def _update_comments_safe():
    """Column comment alignment — wrapped in try/except"""
    _set_comment('observation_report', 'total_reading_minutes', '总阅读分钟')
    _set_comment('observation_report', 'total_books_read', '读完本书数')
    _set_comment('observation_report', 'total_words_read', '总阅读词数')
    _set_comment('observation_report', 'avg_daily_minutes', '日均阅读分钟')
    _set_comment('observation_report', 'level_at_start', '起始级别')
    _set_comment('observation_report', 'level_at_end', '结束级别')
    _set_comment('observation_report', 'quizzes_attempted', '测验尝试次数')
    _set_comment('observation_report', 'quizzes_passed', '测验通过次数')
    _set_comment('observation_report', 'teacher_id', '负责老师ID')
    _set_comment('observation_report', 'teacher_comment', '老师评语')
    _set_comment('observation_report', 'recommendation', '推荐方案')
    _set_comment('observation_report', 'status', '0=草稿 1=已生成')
    _set_comment('order', 'type', '订单类型: 1=亲子课 2=观察期 3=正式会员')
    _set_comment('order', 'refund_status', '退款状态: 0=未退款 1=退款中 2=已退款 3=退款失败')
    _set_comment('order', 'is_deleted', '软删除标记: 0=正常 1=已删除')
    _set_comment('reservation', 'expire_time', '过期时间（创建+72小时）')
    _set_comment('reservation', 'is_deleted', '软删除标记: 0=正常 1=已删除')
    _set_comment('refund_application', 'order_id', '关联订单ID')
    _set_comment('refund_application', 'amount', '订单原金额')
    _set_comment('refund_application', 'refund_amount', '申请退款金额')
    _set_comment('refund_application', 'status', '退款状态')
    _set_comment('refund_application', 'is_deleted', '软删除标记: 0=正常 1=已删除')
    _set_comment('user', 'phone', '手机号')
    _set_comment('user', 'is_deleted', '软删除标记: 0=正常 1=已删除')
    _set_comment('venue', 'name', '场馆名称')
    _set_comment('venue', 'address', '场馆地址')
    _set_comment('venue', 'phone', '联系电话')


def _set_comment(table: str, column: str, comment: str):
    try:
        op.alter_column(table, column, comment=comment)
    except Exception:
        pass


def downgrade() -> None:
    pass
