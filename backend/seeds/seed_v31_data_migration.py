# backend/seeds/seed_v31_data_migration.py
"""
V3.1 数据迁移脚本：从 V2.0 到 V3.1 OMO

迁移内容：
  1. 将 bookshelf 中 STATUS_BORROWING 的记录迁移到 borrow_record
  2. 为现有图书创建 BookCopy（每个 Book 至少 1 个副本）
  3. 初始化 Child 的 deposit_status / current_level_id

使用方式：
  python -m backend.seeds.seed_v31_data_migration

约束：
  - 幂等：可重复执行，不会产生重复数据
  - 安全：先查询再插入，不删除任何现有数据
"""

import logging
import sys
from datetime import datetime, timedelta

from sqlalchemy import text

from backend.database import get_session

logger = logging.getLogger(__name__)


def migrate_bookshelf_to_borrow():
    """将 bookshelf 中 STATUS_BORROWING 的记录迁移到 borrow_record"""
    db = get_session()()
    try:
        # 查询 bookshelf 中借阅中的记录
        result = db.execute(
            text("""
            SELECT id, child_id, book_id, borrow_time, create_time
            FROM bookshelf
            WHERE status = 0 AND is_deleted = 0
        """)
        )
        rows = result.fetchall()

        if not rows:
            logger.info("No borrowing records in bookshelf to migrate")
            return

        migrated = 0
        for row in rows:
            shelf_id, child_id, book_id, borrow_time, create_time = row

            # 检查是否已迁移（幂等）
            existing = db.execute(
                text("""
                SELECT id FROM borrow_record
                WHERE child_id = :child_id AND book_id = :book_id AND is_deleted = 0
            """),
                {"child_id": child_id, "book_id": book_id},
            ).fetchone()

            if existing:
                continue

            # 计算应还日期（借出+21天）
            bt = borrow_time or create_time or datetime.now()
            due_date = bt + timedelta(days=21)

            # 插入 borrow_record
            db.execute(
                text("""
                INSERT INTO borrow_record (child_id, book_id, borrow_time, due_date, status, create_time, update_time, is_deleted)
                VALUES (:child_id, :book_id, :borrow_time, :due_date, 0, :create_time, NOW(), 0)
            """),
                {
                    "child_id": child_id,
                    "book_id": book_id,
                    "borrow_time": bt,
                    "due_date": due_date,
                    "create_time": create_time or datetime.now(),
                },
            )
            migrated += 1

        db.commit()
        logger.info(
            f"Migrated {migrated} borrowing records from bookshelf to borrow_record"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Migration failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


def create_book_copies():
    """为现有图书创建 BookCopy（每个 Book 至少 1 个副本，基于库存）"""
    db = get_session()()
    try:
        # 查询所有有库存的图书
        result = db.execute(
            text("""
            SELECT id, total_stock FROM book
            WHERE is_deleted = 0 AND (total_stock IS NULL OR total_stock > 0)
        """)
        )
        rows = result.fetchall()

        if not rows:
            logger.info("No books to create copies for")
            return

        created = 0
        for row in rows:
            book_id, total_stock = row
            stock = total_stock or 1

            # 检查是否已有副本（幂等）
            existing = db.execute(
                text("""
                SELECT COUNT(*) FROM book_copy WHERE book_id = :book_id AND is_deleted = 0
            """),
                {"book_id": book_id},
            ).scalar()

            if existing >= stock:
                continue

            # 为缺失的副本数创建
            for i in range(existing + 1, stock + 1):
                barcode = f"BC{book_id:06d}{i:03d}"
                db.execute(
                    text("""
                    INSERT INTO book_copy (book_id, barcode, status, create_time, update_time, is_deleted)
                    VALUES (:book_id, :barcode, 0, NOW(), NOW(), 0)
                """),
                    {"book_id": book_id, "barcode": barcode},
                )
                created += 1

        db.commit()
        logger.info(f"Created {created} book copies")
    except Exception as e:
        db.rollback()
        logger.error(f"BookCopy creation failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


def init_child_v31_fields():
    """初始化 Child 的 V3.1 字段"""
    db = get_session()()
    try:
        # 初始化 deposit_status（未交押金的为 0，已经是默认值，无需更新）
        # 初始化 current_level_id（从 child_level 表获取当前级别）
        db.execute(
            text("""
            UPDATE child c
            LEFT JOIN child_level cl ON c.id = cl.child_id AND cl.is_current = 1
            SET c.current_level_id = cl.level_id
            WHERE c.current_level_id IS NULL AND cl.id IS NOT NULL
        """)
        )

        # 更新 Book 的库存字段（从 book_copy 统计）
        db.execute(
            text("""
            UPDATE book b
            SET total_stock = (
                SELECT COUNT(*) FROM book_copy bc WHERE bc.book_id = b.id AND bc.is_deleted = 0
            ),
            available_stock = (
                SELECT COUNT(*) FROM book_copy bc WHERE bc.book_id = b.id AND bc.status = 0 AND bc.is_deleted = 0
            )
            WHERE b.is_deleted = 0
        """)
        )

        db.commit()
        logger.info("Child V3.1 fields initialized")
    except Exception as e:
        db.rollback()
        logger.error(f"Child V3.1 init failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


def main():
    """执行完整迁移"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    logger.info("Starting V3.1 data migration...")

    try:
        migrate_bookshelf_to_borrow()
        create_book_copies()
        init_child_v31_fields()
        logger.info("V3.1 data migration completed successfully!")
    except Exception:
        logger.error("V3.1 data migration FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
