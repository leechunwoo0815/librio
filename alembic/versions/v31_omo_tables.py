"""V3.1 OMO 新增表：book_copy / borrow_record / deposit_record / reservation

Revision ID: v31_omo_tables
Revises: 010_obs_cert_cleanup
Create Date: 2026-06-11

V3.1 变更说明：
  1. 新增 book_copy 表 — 实体书副本，扫码入库
  2. 新增 borrow_record 表 — 线下借阅记录（OMO 核心）
  3. 新增 deposit_record 表 — 押金记录
  4. 新增 reservation 表 — 预约借书
  5. Book 表新增字段 — total_stock / available_stock / offline_available 等
  6. Child 表新增字段 — deposit_status / outstanding_fines / current_level_id
  7. 索引和约束补齐

数据迁移：
  现有 bookshelf 表中 STATUS_BORROWING 的记录需要迁移到 borrow_record 表
  （见 seed_v31_data_migration.py）
"""

from alembic import op
import sqlalchemy as sa

revision = "v31_omo_tables"
down_revision = "010_obs_cert_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================================
    # 1. 新增 book_copy 表
    # ============================================================
    op.create_table(
        "book_copy",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("book_id", sa.BigInteger(), nullable=False, comment="关联图书ID"),
        sa.Column("barcode", sa.String(50), nullable=False, comment="副本条码（唯一）"),
        sa.Column("status", sa.SmallInteger(), server_default="0", comment="副本状态: 0=可借 1=已借出 2=维修中 3=报废"),
        sa.Column("condition_note", sa.String(255), nullable=True, comment="入库时状况备注"),
        sa.Column("location", sa.String(50), nullable=True, comment="存放位置"),
        sa.Column("create_time", sa.DateTime(), server_default=sa.func.now(), comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), comment="更新时间"),
        sa.Column("is_deleted", sa.SmallInteger(), server_default="0", comment="软删除标记"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_book_copy_book_id", "book_copy", ["book_id"])
    op.create_index("ix_book_copy_barcode", "book_copy", ["barcode"], unique=True)

    # ============================================================
    # 2. 新增 borrow_record 表
    # ============================================================
    op.create_table(
        "borrow_record",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("child_id", sa.BigInteger(), nullable=False, comment="孩子ID"),
        sa.Column("book_id", sa.BigInteger(), nullable=False, comment="图书ID"),
        sa.Column("book_copy_id", sa.BigInteger(), nullable=True, comment="具体副本ID"),
        sa.Column("operator_id", sa.BigInteger(), nullable=True, comment="操作运营人员ID"),
        sa.Column("borrow_time", sa.DateTime(), nullable=False, comment="借出时间"),
        sa.Column("due_date", sa.DateTime(), nullable=False, comment="应还日期（借出+21天）"),
        sa.Column("return_time", sa.DateTime(), nullable=True, comment="实际归还时间"),
        sa.Column("status", sa.SmallInteger(), server_default="0", comment="借阅状态: 0=借阅中 1=已归还 2=已逾期 3=丢失"),
        sa.Column("overdue_days", sa.Integer(), server_default="0", comment="逾期天数"),
        sa.Column("fine_amount", sa.Numeric(10, 2), server_default="0", comment="逾期罚款"),
        sa.Column("quiz_passed", sa.SmallInteger(), server_default="0", comment="是否已通过测评: 0=否 1=是"),
        sa.Column("create_time", sa.DateTime(), server_default=sa.func.now(), comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), comment="更新时间"),
        sa.Column("is_deleted", sa.SmallInteger(), server_default="0", comment="软删除标记"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_borrow_child_id", "borrow_record", ["child_id"])
    op.create_index("ix_borrow_book_id", "borrow_record", ["book_id"])
    # 借阅列表常用查询：按 child + status 查借阅中的书
    op.create_index("ix_borrow_child_status", "borrow_record", ["child_id", "status"])

    # ============================================================
    # 3. 新增 deposit_record 表
    # ============================================================
    op.create_table(
        "deposit_record",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("child_id", sa.BigInteger(), nullable=False, comment="孩子ID"),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False, server_default="1200.00", comment="押金金额"),
        sa.Column("status", sa.SmallInteger(), server_default="0", comment="押金状态: 0=未支付 1=已支付 2=已退款 3=已扣除"),
        sa.Column("pay_time", sa.DateTime(), nullable=True, comment="支付时间"),
        sa.Column("pay_order_id", sa.BigInteger(), nullable=True, comment="支付订单ID"),
        sa.Column("refund_time", sa.DateTime(), nullable=True, comment="退款时间"),
        sa.Column("refund_amount", sa.Numeric(10, 2), nullable=True, comment="退款金额"),
        sa.Column("deduct_amount", sa.Numeric(10, 2), nullable=True, comment="扣除金额"),
        sa.Column("deduct_reason", sa.String(255), nullable=True, comment="扣除原因"),
        sa.Column("create_time", sa.DateTime(), server_default=sa.func.now(), comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), comment="更新时间"),
        sa.Column("is_deleted", sa.SmallInteger(), server_default="0", comment="软删除标记"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deposit_child_id", "deposit_record", ["child_id"])

    # ============================================================
    # 4. 新增 reservation 表
    # ============================================================
    op.create_table(
        "reservation",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("child_id", sa.BigInteger(), nullable=False, comment="孩子ID"),
        sa.Column("book_id", sa.BigInteger(), nullable=False, comment="图书ID"),
        sa.Column("venue_id", sa.BigInteger(), nullable=True, comment="预约取书场馆"),
        sa.Column("status", sa.SmallInteger(), server_default="0", comment="预约状态: 0=待取书 1=已取书 2=已过期 3=已取消"),
        sa.Column("expire_time", sa.DateTime(), nullable=False, comment="过期时间（创建+72小时）"),
        sa.Column("fulfilled_time", sa.DateTime(), nullable=True, comment="取书时间"),
        sa.Column("borrow_record_id", sa.BigInteger(), nullable=True, comment="取书后关联的借阅记录ID"),
        sa.Column("create_time", sa.DateTime(), server_default=sa.func.now(), comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), comment="更新时间"),
        sa.Column("is_deleted", sa.SmallInteger(), server_default="0", comment="软删除标记"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reservation_child_id", "reservation", ["child_id"])

    # ============================================================
    # 5. Book 表新增 V3.1 字段
    # ============================================================
    op.add_column("book", sa.Column("total_stock", sa.Integer(), server_default="0", comment="实体书库存总数"))
    op.add_column("book", sa.Column("available_stock", sa.Integer(), server_default="0", comment="实体书可借数量"))
    op.add_column("book", sa.Column("offline_available", sa.SmallInteger(), server_default="0", comment="是否支持线下借阅: 0=否 1=是"))
    op.add_column("book", sa.Column("audio_timeline", sa.Text(), nullable=True, comment="音频时间线JSON"))
    op.add_column("book", sa.Column("core_vocabulary", sa.Text(), nullable=True, comment="核心词汇JSON列表"))
    op.add_column("book", sa.Column("is_published", sa.SmallInteger(), server_default="1", comment="是否上架: 0=下架 1=上架"))

    # ============================================================
    # 6. Child 表新增 V3.1 字段
    # ============================================================
    op.add_column("child", sa.Column("deposit_status", sa.SmallInteger(), server_default="0", comment="押金状态: 0=未交 1=已交 2=已退 3=已扣"))
    op.add_column("child", sa.Column("outstanding_fines", sa.Numeric(10, 2), server_default="0", comment="未缴罚款"))
    op.add_column("child", sa.Column("current_level_id", sa.BigInteger(), nullable=True, comment="当前级别ID"))

    # ============================================================
    # 7. 索引补齐（现有表缺失的索引）
    # ============================================================
    # CheckIn：按 child + date 查打卡
    op.create_index("ix_checkin_child_date", "check_in", ["child_id", "check_date"])
    # ReadingSession：按 child + time 范围查
    op.create_index("ix_session_child_time", "reading_session", ["child_id", "start_time"])
    # UserVocabulary：按 child + status 查生词
    op.create_index("ix_vocab_child_status", "user_vocabulary", ["child_id", "status"])
    # Order：按 child + type + pay_status 防重复
    op.create_index("ix_order_child_type_pay", "order", ["child_id", "type", "pay_status"])

    # ============================================================
    # 8. 积分去重视图
    # ============================================================
    op.execute("""
        CREATE OR REPLACE VIEW v_word_score AS
        SELECT DISTINCT child_id, book_id, word_count
        FROM borrow_record
        WHERE quiz_passed = 1 AND is_deleted = 0
    """)


def downgrade() -> None:
    # 删除视图
    op.execute("DROP VIEW IF EXISTS v_word_score")

    # 删除新增索引
    op.drop_index("ix_order_child_type_pay", "order")
    op.drop_index("ix_vocab_child_status", "user_vocabulary")
    op.drop_index("ix_session_child_time", "reading_session")
    op.drop_index("ix_checkin_child_date", "check_in")

    # 删除 Child 新增字段
    op.drop_column("child", "current_level_id")
    op.drop_column("child", "outstanding_fines")
    op.drop_column("child", "deposit_status")

    # 删除 Book 新增字段
    op.drop_column("book", "is_published")
    op.drop_column("book", "core_vocabulary")
    op.drop_column("book", "audio_timeline")
    op.drop_column("book", "offline_available")
    op.drop_column("book", "available_stock")
    op.drop_column("book", "total_stock")

    # 删除新表
    op.drop_table("reservation")
    op.drop_table("deposit_record")
    op.drop_table("borrow_record")
    op.drop_table("book_copy")
