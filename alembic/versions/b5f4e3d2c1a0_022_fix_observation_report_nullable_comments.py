"""022_fix_observation_report_nullable_comments

Fixes remaining drift in observation_report:
- Fills NULL start_date/end_date with create_time
- Applies NOT NULL constraint (uses existing_type from DB reflect)
- Syncs column comments (uses existing_type from DB reflect)

Revision ID: b5f4e3d2c1a0
Revises: a4b8c7d6e5f4
"""

import logging
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import MetaData

logger = logging.getLogger("alembic.migration")

revision: str = "b5f4e3d2c1a0"
down_revision: Union[str, Sequence[str], None] = "a4b8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col_type(table: str, column: str):
    """Reflect column type from live DB — avoids manual type listing"""
    bind = op.get_bind()
    meta = MetaData()
    meta.reflect(bind=bind, only=[table])
    return meta.tables[table].columns[column].type


def upgrade() -> None:
    _fix_observation_report_nulls()
    _fix_observation_report_nullable()
    _sync_all_column_comments()


def _fix_observation_report_nulls():
    """Fill NULL start_date/end_date before applying NOT NULL"""
    for col in ("start_date", "end_date"):
        op.execute(
            f"UPDATE observation_report SET {col} = create_time "
            f"WHERE {col} IS NULL AND create_time IS NOT NULL"
        )
        op.execute(f"UPDATE observation_report SET {col} = NOW() WHERE {col} IS NULL")


def _fix_observation_report_nullable():
    """Set NOT NULL on observation_report date columns"""
    op.alter_column(
        "observation_report",
        "start_date",
        nullable=False,
        existing_type=_col_type("observation_report", "start_date"),
    )
    op.alter_column(
        "observation_report",
        "end_date",
        nullable=False,
        existing_type=_col_type("observation_report", "end_date"),
    )


def _sync_all_column_comments():
    """Sync all column comments — existing_type from DB reflect"""
    for table, column, comment in _ALL_COMMENTS:
        try:
            op.alter_column(
                table,
                column,
                comment=comment,
                existing_type=_col_type(table, column),
            )
        except Exception as e:
            logger.warning(
                "Comment sync failed: %s.%s = %s (%s)", table, column, comment, e
            )


_ALL_COMMENTS: list[tuple[str, str, str]] = [
    # observation_report
    ("observation_report", "start_date", "观察期开始日期"),
    ("observation_report", "end_date", "观察期结束日期"),
    ("observation_report", "total_reading_minutes", "总阅读分钟"),
    ("observation_report", "total_books_read", "读完本书数"),
    ("observation_report", "total_words_read", "总阅读词数"),
    ("observation_report", "avg_daily_minutes", "日均阅读分钟"),
    ("observation_report", "level_at_start", "起始级别"),
    ("observation_report", "level_at_end", "结束级别"),
    ("observation_report", "quizzes_attempted", "测验尝试次数"),
    ("observation_report", "quizzes_passed", "测验通过次数"),
    ("observation_report", "teacher_id", "负责老师ID"),
    ("observation_report", "teacher_comment", "老师评语"),
    ("observation_report", "recommendation", "推荐方案"),
    ("observation_report", "status", "0=草稿 1=已生成"),
    ("observation_report", "id", "主键"),
    ("observation_report", "create_time", "创建时间"),
    ("observation_report", "update_time", "更新时间"),
    ("observation_report", "is_deleted", "软删除标记: 0=正常 1=已删除"),
    # operation_log
    ("operation_log", "admin_id", "操作管理员ID"),
    ("operation_log", "ip", "IP地址"),
    ("operation_log", "id", "主键"),
    ("operation_log", "create_time", "创建时间"),
    ("operation_log", "update_time", "更新时间"),
    ("operation_log", "is_deleted", "软删除标记: 0=正常 1=已删除"),
    # order
    ("order", "type", "订单类型: 1=亲子课 2=观察期 3=正式会员"),
    ("order", "refund_status", "退款状态: 0=未退款 1=退款中 2=已退款 3=退款失败"),
    ("order", "is_deleted", "软删除标记: 0=正常 1=已删除"),
    # parent_course_time
    ("parent_course_time", "venue_id", "场馆ID"),
    ("parent_course_time", "id", "主键"),
    ("parent_course_time", "create_time", "创建时间"),
    ("parent_course_time", "update_time", "更新时间"),
    ("parent_course_time", "is_deleted", "软删除标记: 0=正常 1=已删除"),
    # permission
    ("permission", "id", "主键"),
    # question_bank
    ("question_bank", "book_id", "图书ID"),
    ("question_bank", "id", "主键"),
    ("question_bank", "create_time", "创建时间"),
    ("question_bank", "update_time", "更新时间"),
    ("question_bank", "is_deleted", "软删除标记: 0=正常 1=已删除"),
    # quiz
    ("quiz", "child_id", "孩子ID"),
    ("quiz", "book_id", "图书ID"),
    ("quiz", "submission_id", "关联提交ID"),
    ("quiz", "status", "测验状态"),
    ("quiz", "id", "主键"),
    ("quiz", "create_time", "创建时间"),
    ("quiz", "update_time", "更新时间"),
    ("quiz", "is_deleted", "软删除标记: 0=正常 1=已删除"),
    # quiz_answer
    ("quiz_answer", "quiz_id", "测验ID"),
    ("quiz_answer", "question_id", "题目ID"),
    ("quiz_answer", "selected_answer", "选择的答案(A/B/C/D)"),
    ("quiz_answer", "id", "主键"),
    ("quiz_answer", "create_time", "创建时间"),
    ("quiz_answer", "update_time", "更新时间"),
    ("quiz_answer", "is_deleted", "软删除标记: 0=正常 1=已删除"),
    # quiz_question
    ("quiz_question", "quiz_id", "测验ID"),
    ("quiz_question", "question_id", "题目ID"),
    ("quiz_question", "id", "主键"),
    ("quiz_question", "create_time", "创建时间"),
    ("quiz_question", "update_time", "更新时间"),
    ("quiz_question", "is_deleted", "软删除标记: 0=正常 1=已删除"),
    # reading_progress
    ("reading_progress", "child_id", "孩子ID"),
    ("reading_progress", "book_id", "图书ID"),
    ("reading_progress", "current_page", "当前页码"),
    ("reading_progress", "total_pages", "总页数"),
    ("reading_progress", "progress_pct", "进度百分比"),
    ("reading_progress", "last_read_time", "最后阅读时间"),
    ("reading_progress", "is_finished", "是否读完: 0=否 1=是"),
    ("reading_progress", "finish_time", "读完时间"),
    ("reading_progress", "id", "主键"),
    ("reading_progress", "create_time", "创建时间"),
    ("reading_progress", "update_time", "更新时间"),
    ("reading_progress", "is_deleted", "软删除标记: 0=正常 1=已删除"),
    # reading_session
    ("reading_session", "child_id", "孩子ID"),
    ("reading_session", "book_id", "图书ID"),
    ("reading_session", "start_time", "开始时间"),
    ("reading_session", "end_time", "结束时间"),
    ("reading_session", "pages_read", "本次阅读页数"),
    ("reading_session", "words_read", "本次阅读词数"),
    ("reading_session", "id", "主键"),
    ("reading_session", "create_time", "创建时间"),
    ("reading_session", "update_time", "更新时间"),
    ("reading_session", "is_deleted", "软删除标记: 0=正常 1=已删除"),
    # reading_submission
    ("reading_submission", "child_id", "孩子ID"),
    ("reading_submission", "book_id", "图书ID"),
    ("reading_submission", "id", "主键"),
    ("reading_submission", "create_time", "创建时间"),
    ("reading_submission", "update_time", "更新时间"),
    ("reading_submission", "is_deleted", "软删除标记: 0=正常 1=已删除"),
    # refund_application
    ("refund_application", "order_id", "关联订单ID"),
    ("refund_application", "amount", "订单原金额"),
    ("refund_application", "refund_amount", "申请退款金额"),
    ("refund_application", "status", "退款状态"),
    ("refund_application", "reviewer_id", "审核人ID"),
    ("refund_application", "review_time", "审核时间"),
    ("refund_application", "review_comment", "审核意见"),
    ("refund_application", "actual_refund_amount", "实际退款金额"),
    ("refund_application", "refund_time", "退款完成时间"),
    ("refund_application", "is_deleted", "软删除标记: 0=正常 1=已删除"),
    # reservation
    ("reservation", "venue_id", "预约取书场馆"),
    ("reservation", "expire_time", "过期时间（创建+72小时）"),
    ("reservation", "fulfilled_time", "取书时间"),
    ("reservation", "borrow_record_id", "取书后关联的借阅记录ID"),
    ("reservation", "is_deleted", "软删除标记: 0=正常 1=已删除"),
    # role
    ("role", "id", "主键"),
    # role_permission
    ("role_permission", "id", "主键"),
    # system_config
    ("system_config", "id", "主键"),
    ("system_config", "create_time", "创建时间"),
    ("system_config", "update_time", "更新时间"),
    ("system_config", "is_deleted", "软删除标记: 0=正常 1=已删除"),
    # system_message
    ("system_message", "user_id", "用户ID(null=角色群发)"),
    ("system_message", "title", "标题"),
    ("system_message", "content", "内容"),
    ("system_message", "id", "主键"),
    ("system_message", "create_time", "创建时间"),
    ("system_message", "is_deleted", "软删除标记: 0=正常 1=已删除"),
    # teacher
    ("teacher", "id", "主键"),
    ("teacher", "create_time", "创建时间"),
    ("teacher", "update_time", "更新时间"),
    ("teacher", "is_deleted", "软删除标记: 0=正常 1=已删除"),
    # teacher_schedule
    ("teacher_schedule", "teacher_id", "老师ID"),
    ("teacher_schedule", "id", "主键"),
    ("teacher_schedule", "create_time", "创建时间"),
    ("teacher_schedule", "update_time", "更新时间"),
    ("teacher_schedule", "is_deleted", "软删除标记: 0=正常 1=已删除"),
    # user
    ("user", "phone", "手机号"),
    ("user", "is_deleted", "软删除标记: 0=正常 1=已删除"),
    # user_vocabulary
    ("user_vocabulary", "child_id", "孩子ID"),
    ("user_vocabulary", "word_id", "词典词条ID"),
    ("user_vocabulary", "last_review_time", "最后复习时间"),
    ("user_vocabulary", "id", "主键"),
    ("user_vocabulary", "create_time", "创建时间"),
    ("user_vocabulary", "update_time", "更新时间"),
    ("user_vocabulary", "is_deleted", "软删除标记: 0=正常 1=已删除"),
    # venue
    ("venue", "name", "场馆名称"),
    ("venue", "address", "场馆地址"),
    ("venue", "phone", "联系电话"),
    ("venue", "id", "主键"),
    ("venue", "create_time", "创建时间"),
    ("venue", "update_time", "更新时间"),
    ("venue", "is_deleted", "软删除标记: 0=正常 1=已删除"),
    # voice_recording
    ("voice_recording", "child_id", "孩子ID"),
    ("voice_recording", "book_id", "图书ID"),
    ("voice_recording", "id", "主键"),
    ("voice_recording", "create_time", "创建时间"),
    ("voice_recording", "update_time", "更新时间"),
    ("voice_recording", "is_deleted", "软删除标记: 0=正常 1=已删除"),
]


def downgrade() -> None:
    pass
