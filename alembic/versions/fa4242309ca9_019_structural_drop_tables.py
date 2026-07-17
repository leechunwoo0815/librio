"""019_structural_drop_tables

Handles critical structural changes only:
- Drop old V2 tables (collection, borrow, assessment)
- Drop removed columns (venue, child, deposit_record, etc.)
- Add unique constraints

Revision ID: fa4242309ca9
Revises: b0c6867c01dd
Create Date: 2026-07-14

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = 'fa4242309ca9'
down_revision: Union[str, Sequence[str], None] = 'b0c6867c01dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    _drop_columns_safe()
    _add_constraints_safe()


def _drop_columns_safe():
    columns_to_drop = [
        ("venue", "latitude"), ("venue", "longitude"),
        ("venue", "opening_hours"), ("venue", "cover"),
        ("child", "deposit_amount"),
        ("deposit_record", "paid_at"), ("deposit_record", "refunded_at"),
        ("deposit_record", "deduction_reason"),
        ("bookshelf", "borrow_time"), ("bookshelf", "return_time"),
        ("favorites", "created_at"),
        ("learning_report", "total_words"), ("learning_report", "report_type"),
        ("learning_report", "suggestion"), ("learning_report", "voice_practices"),
        ("learning_report", "check_in_days"), ("learning_report", "total_minutes"),
        ("observation_report", "observation_start"),
        ("observation_report", "observation_end"),
        ("observation_report", "generated_at"),
        ("observation_report", "current_level"),
        ("refund_application", "remark"),
        ("refund_application", "audit_time"),
        ("refund_application", "admin_id"),
        ("reservation", "reserve_time"),
    ]
    for table, column in columns_to_drop:
        try:
            op.drop_column(table, column)
        except Exception:
            pass


def _add_constraints_safe():
    constraints = [
        ("uq_child_book_progress", "reading_progress", ["child_id", "book_id"]),
        ("uq_child_word", "child_vocabulary", ["child_id", "word_id"]),
    ]
    for name, table, columns in constraints:
        try:
            op.create_unique_constraint(name, table, columns)
        except Exception:
            pass


def downgrade() -> None:
    try:
        op.drop_constraint('uq_child_word', 'child_vocabulary', type_='unique')
    except Exception:
        pass
    try:
        op.drop_constraint('uq_child_book_progress', 'reading_progress', type_='unique')
    except Exception:
        pass

    _add_back_columns()


def _add_back_columns():
    columns_to_add = [
        ("reservation", "reserve_time", mysql.DATETIME(), True),
        ("refund_application", "admin_id", mysql.BIGINT(), True),
        ("refund_application", "audit_time", mysql.DATETIME(), True),
        ("refund_application", "remark", mysql.VARCHAR(charset='utf8mb4', collation='utf8mb4_unicode_ci', length=500), True),
        ("observation_report", "current_level", mysql.VARCHAR(charset='utf8mb4', collation='utf8mb4_unicode_ci', length=50), True),
        ("observation_report", "generated_at", mysql.DATETIME(), True),
        ("observation_report", "observation_end", mysql.DATETIME(), True),
        ("observation_report", "observation_start", mysql.DATETIME(), True),
        ("learning_report", "total_minutes", mysql.INTEGER(), True),
        ("learning_report", "check_in_days", mysql.INTEGER(), True),
        ("learning_report", "voice_practices", mysql.INTEGER(), True),
        ("learning_report", "suggestion", mysql.VARCHAR(charset='utf8mb4', collation='utf8mb4_unicode_ci', length=500), True),
        ("learning_report", "report_type", mysql.VARCHAR(charset='utf8mb4', collation='utf8mb4_unicode_ci', length=50), True),
        ("learning_report", "total_words", mysql.INTEGER(), True),
        ("favorites", "created_at", mysql.DATETIME(), True),
        ("deposit_record", "deduction_reason", mysql.VARCHAR(charset='utf8mb4', collation='utf8mb4_unicode_ci', length=255), True),
        ("deposit_record", "refunded_at", mysql.DATETIME(), True),
        ("deposit_record", "paid_at", mysql.DATETIME(), True),
        ("child", "deposit_amount", mysql.DECIMAL(precision=10, scale=2), True),
        ("bookshelf", "return_time", mysql.DATETIME(), True),
        ("bookshelf", "borrow_time", mysql.DATETIME(), True),
        ("venue", "cover", mysql.VARCHAR(charset='utf8mb4', collation='utf8mb4_unicode_ci', length=255), True),
        ("venue", "opening_hours", mysql.VARCHAR(charset='utf8mb4', collation='utf8mb4_unicode_ci', length=200), True),
        ("venue", "longitude", mysql.VARCHAR(charset='utf8mb4', collation='utf8mb4_unicode_ci', length=50), True),
        ("venue", "latitude", mysql.VARCHAR(charset='utf8mb4', collation='utf8mb4_unicode_ci', length=50), True),
    ]
    for table, column, col_type, nullable in columns_to_add:
        try:
            op.add_column(table, sa.Column(column, col_type, nullable=nullable))
        except Exception:
            pass


