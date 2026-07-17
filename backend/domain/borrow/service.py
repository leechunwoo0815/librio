# backend/domain/borrow/service.py
"""借阅域业务逻辑 — V3.1 OMO 线下借阅

借阅上限 20 本，借期 21 天，逾期罚款。
与 Bookshelf（想读清单）完全分离。
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.common.events import BookBorrowedEvent, BookReturnedEvent, event_bus
from backend.common.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from backend.common.types import BorrowStatus, DepositStatus, MemberStatus
from backend.domain.book.models import Book, BookCopy
from backend.domain.borrow.models import BorrowRecord
from backend.domain.borrow.repository import BorrowRecordRepository
from backend.domain.borrow.schemas import (
    BorrowBookRequest,
    ReturnBookRequest,
    BorrowRecordResponse,
)
from backend.domain.child.models import Child

logger = logging.getLogger(__name__)

MAX_BORROW = 20  # 默认值，通过 ConfigService.get_int(db, "borrow_limit", 20) 读取
BORROW_DAYS = (
    21  # 默认值，通过 ConfigService.get_int(db, "borrow_period_days", 21) 读取
)


class BorrowService:
    """借阅服务"""

    def __init__(self, db: Session):
        self.db = db
        self.borrow_repo = BorrowRecordRepository(db)
        self.book_repo = BaseRepository(db, Book)
        self.copy_repo = BaseRepository(db, BookCopy)

    def borrow_book(self, data: BorrowBookRequest) -> BorrowRecordResponse:
        """借书 — 校验权限 + 上限 + 创建记录 + 发布事件"""
        try:
            # 校验会员状态 + 押金
            child = (
                self.db.query(Child)
                .filter(Child.id == data.child_id, Child.is_deleted == 0)
                .first()
            )
            if not child:
                raise ValidationError("孩子不存在")
            if child.status not in (MemberStatus.OBSERVATION, MemberStatus.OFFICIAL):
                raise ForbiddenError("该孩子无借书权限（非观察期/正式会员）")
            if child.deposit_status not in (
                DepositStatus.PAID,
                DepositStatus.REFUNDING,
                DepositStatus.REFUND_PENDING,
            ):
                raise ForbiddenError("请先缴纳押金")

            # 校验上限 — 从配置读取
            from backend.common.config_service import ConfigService

            max_borrow = ConfigService.get_int(self.db, "borrow_limit", MAX_BORROW)
            active_records = (
                self.db.query(BorrowRecord)
                .filter(
                    BorrowRecord.child_id == data.child_id,
                    BorrowRecord.status.in_(
                        [BorrowStatus.BORROWING, BorrowStatus.OVERDUE]
                    ),
                    BorrowRecord.is_deleted == 0,
                )
                .with_for_update()
                .all()
            )
            active_count = len(active_records)
            if active_count >= max_borrow:
                raise ValidationError(f"借阅上限 {max_borrow} 本，请先归还")

            # 先查重复（BORROWING 和 OVERDUE 都算未还）
            existing = self.borrow_repo.get_by_child_and_book(
                data.child_id, data.book_id, BorrowStatus.BORROWING
            )
            if not existing:
                existing = self.borrow_repo.get_by_child_and_book(
                    data.child_id, data.book_id, BorrowStatus.OVERDUE
                )
            if existing:
                raise ConflictError("该书已借阅，请先归还")

            # 后扣库存 — 使用 SQL 原子更新避免并发超卖
            updated = (
                self.db.query(Book)
                .filter(
                    Book.id == data.book_id,
                    Book.available_stock > 0,
                    Book.is_deleted == 0,
                )
                .update({Book.available_stock: Book.available_stock - 1})
            )
            if not updated:
                raise ValidationError("库存不足，无法借出")

            borrow_days = ConfigService.get_int(
                self.db, "borrow_period_days", BORROW_DAYS
            )
            now = datetime.now()
            record = BorrowRecord(
                child_id=data.child_id,
                book_id=data.book_id,
                book_copy_id=data.book_copy_id,
                operator_id=data.operator_id,
                borrow_time=now,
                due_date=now + timedelta(days=borrow_days),
                status=BorrowStatus.BORROWING,
            )
            created = self.borrow_repo.create(record)

            # 发布借书事件
            event_bus.publish(
                BookBorrowedEvent(
                    child_id=data.child_id,
                    book_id=data.book_id,
                    book_copy_id=data.book_copy_id,
                    borrow_record_id=created.id,
                ),
                db=self.db,
            )

            self.db.commit()
            logger.info(f"Book borrowed: child={data.child_id}, book={data.book_id}")
            return BorrowRecordResponse.model_validate(created)
        except SQLAlchemyError:
            self.db.rollback()
            raise

    def scan_and_return(self, barcode: str) -> BorrowRecordResponse:
        """扫码还书 — 通过条码找到活跃借阅记录并还书"""
        copy = (
            self.db.query(BookCopy)
            .filter(BookCopy.barcode == barcode, BookCopy.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if not copy:
            raise NotFoundError(f"条码 {barcode} 不存在")

        record = (
            self.db.query(BorrowRecord)
            .filter(
                BorrowRecord.book_copy_id == copy.id,
                BorrowRecord.status.in_([BorrowStatus.BORROWING, BorrowStatus.OVERDUE]),
                BorrowRecord.is_deleted == 0,
            )
            .with_for_update()
            .first()
        )
        if not record:
            raise NotFoundError(f"条码 {barcode} 无活跃借阅记录")

        return self.return_book(ReturnBookRequest(borrow_record_id=record.id))

    def return_book(self, data: ReturnBookRequest) -> BorrowRecordResponse:
        """还书 — 更新记录 + 发布事件"""
        record = (
            self.db.query(BorrowRecord)
            .filter(
                BorrowRecord.id == data.borrow_record_id, BorrowRecord.is_deleted == 0
            )
            .with_for_update()
            .first()
        )
        if not record:
            raise NotFoundError("借阅记录不存在")
        if record.status not in (BorrowStatus.BORROWING, BorrowStatus.OVERDUE):
            raise ConflictError("该记录不在借阅中")

        now = datetime.now()
        record.return_time = now
        record.status = BorrowStatus.RETURNED

        # 计算逾期
        if now > record.due_date:
            # 到期日当天不罚款，从第二天开始算
            overdue_days = max(0, (now - record.due_date).days - 1)
            record.overdue_days = overdue_days
            if overdue_days > 0:
                from backend.common.config_service import ConfigService

                daily_fine = ConfigService.get_decimal(
                    self.db, "overdue_fine_per_day", Decimal("1")
                )
                record.fine_amount = Decimal(str(overdue_days)) * daily_fine

        self.borrow_repo.update(record)

        # 发布还书事件
        event_bus.publish(
            BookReturnedEvent(
                child_id=record.child_id,
                book_id=record.book_id,
                borrow_record_id=record.id,
                reason="manual",
            ),
            db=self.db,
        )

        self.db.commit()
        return BorrowRecordResponse.model_validate(record)

    def mark_quiz_passed(self, child_id: int, book_id: int) -> None:
        """标记借阅记录的测评通过标记（事件处理器调用）"""
        record = self.borrow_repo.get_by_child_and_book(
            child_id, book_id, BorrowStatus.BORROWING
        )
        if record:
            record.quiz_passed = 1
            self.borrow_repo.update(record)

    def scan_and_borrow(
        self,
        child_id: int,
        barcode: str,
        operator_id: int | None = None,
        title: str | None = None,
        isbn: str | None = None,
        ar_value: float | None = None,
        age_min: int | None = None,
        age_max: int | None = None,
        word_count: int | None = None,
    ) -> BorrowRecordResponse:
        """扫码借书 — 条码存在则直接借阅，不存在则自动创建图书+副本后借阅"""
        # 1. 查找 BookCopy
        copy = (
            self.db.query(BookCopy)
            .filter(BookCopy.barcode == barcode, BookCopy.is_deleted == 0)
            .first()
        )

        if copy:
            # 条码已存在，直接借阅
            book_id = copy.book_id
            book_copy_id = copy.id
        else:
            # 条码不存在，需创建 Book + BookCopy
            if not all([title, isbn, ar_value, age_min, age_max]):
                raise ValidationError(
                    "新书条码，需提供 title/isbn/ar_value/age_min/age_max"
                )

            # 查找是否已有同 ISBN 的 Book
            book = (
                self.db.query(Book)
                .filter(Book.isbn == isbn, Book.is_deleted == 0)
                .first()
            )
            if not book:
                book = Book(
                    isbn=isbn,
                    title=title,
                    ar_value=ar_value,
                    age_min=age_min,
                    age_max=age_max,
                    word_count=word_count or 0,
                    total_stock=0,
                    available_stock=0,
                )
                self.db.add(book)
                self.db.flush()  # 获取 book.id

            # 创建 BookCopy
            copy = BookCopy(
                book_id=book.id,
                barcode=barcode,
                status=0,  # 在馆
            )
            self.db.add(copy)
            self.db.flush()

            # 递增库存（SQL 原子更新，与 decrease_available_stock 风格一致）
            self.db.query(Book).filter(Book.id == book.id).update(
                {
                    Book.total_stock: Book.total_stock + 1,
                    Book.available_stock: Book.available_stock + 1,
                },
                synchronize_session="fetch",
            )

            book_id = book.id
            book_copy_id = copy.id

        # 2. 调用已有的 borrow_book 逻辑
        from backend.domain.borrow.schemas import BorrowBookRequest

        data = BorrowBookRequest(
            child_id=child_id,
            book_id=book_id,
            book_copy_id=book_copy_id,
            operator_id=operator_id,
        )
        return self.borrow_book(data)

    def borrow_from_reservation(
        self, child_id: int, book_id: int, reservation_id: int | None = None
    ) -> None:
        """预约取书 → 创建借阅记录（事件处理器调用）"""
        # 校验预约存在性
        if reservation_id:
            from backend.domain.reservation.models import Reservation
            from backend.common.types import ReservationStatus

            reservation = (
                self.db.query(Reservation)
                .filter(Reservation.id == reservation_id, Reservation.is_deleted == 0)
                .first()
            )
            if not reservation:
                raise NotFoundError("预约记录不存在")
            if reservation.child_id != child_id:
                raise ForbiddenError("预约不属于该孩子")
            if reservation.status not in (
                ReservationStatus.PENDING,
                ReservationStatus.FULFILLED,
            ):
                raise ConflictError(f"预约状态({reservation.status})不允许取书")

        # 校验无重复借阅
        existing = (
            self.db.query(BorrowRecord)
            .filter(
                BorrowRecord.child_id == child_id,
                BorrowRecord.book_id == book_id,
                BorrowRecord.status.in_([BorrowStatus.BORROWING, BorrowStatus.OVERDUE]),
                BorrowRecord.is_deleted == 0,
            )
            .first()
        )
        if existing:
            raise ConflictError("该孩子已有同一本书的未还借阅记录")

        # 校验会员状态 + 押金（与 borrow_book 相同）
        child = (
            self.db.query(Child)
            .filter(Child.id == child_id, Child.is_deleted == 0)
            .first()
        )
        if not child:
            raise ValidationError("孩子不存在")
        if child.status not in (MemberStatus.OBSERVATION, MemberStatus.OFFICIAL):
            raise ForbiddenError("该孩子无借书权限（非观察期/正式会员）")
        if child.deposit_status not in (
            DepositStatus.PAID,
            DepositStatus.REFUNDING,
            DepositStatus.REFUND_PENDING,
        ):
            raise ForbiddenError("请先缴纳押金")

        # 校验借阅上限
        from backend.common.config_service import ConfigService

        max_borrow = ConfigService.get_int(self.db, "borrow_limit", MAX_BORROW)
        active_records = (
            self.db.query(BorrowRecord)
            .filter(
                BorrowRecord.child_id == child_id,
                BorrowRecord.status.in_([BorrowStatus.BORROWING, BorrowStatus.OVERDUE]),
                BorrowRecord.is_deleted == 0,
            )
            .with_for_update()
            .all()
        )
        active_count = len(active_records)
        if active_count >= max_borrow:
            raise ValidationError(f"借阅上限 {max_borrow} 本，请先归还")

        # 防御性库存检查（仅非预约借书时检查，预约已锁定库存）
        if not reservation_id:
            book = (
                self.db.query(Book)
                .filter(Book.id == book_id, Book.is_deleted == 0)
                .first()
            )
            if book and (book.available_stock or 0) <= 0:
                raise ValidationError("库存不足，无法借阅")

        borrow_days = ConfigService.get_int(self.db, "borrow_period_days", BORROW_DAYS)
        now = datetime.now()
        record = BorrowRecord(
            child_id=child_id,
            book_id=book_id,
            borrow_time=now,
            due_date=now + timedelta(days=borrow_days),
            status=BorrowStatus.BORROWING,
        )
        created = self.borrow_repo.create(record)

        # 标记预约为已取书 + 链接借阅记录
        if reservation_id:
            from backend.domain.reservation.models import Reservation
            from backend.common.types import ReservationStatus

            reservation = (
                self.db.query(Reservation)
                .filter(Reservation.id == reservation_id)
                .first()
            )
            if reservation:
                reservation.status = ReservationStatus.FULFILLED
                reservation.borrow_record_id = created.id

        # 发布借书事件
        event_bus.publish(
            BookBorrowedEvent(
                child_id=child_id,
                book_id=book_id,
                borrow_record_id=created.id,
            ),
            db=self.db,
        )

        self.db.commit()

    def get_child_borrows(
        self,
        child_id: int,
        status: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[BorrowRecordResponse], int]:
        """获取孩子借阅列表 — 返回 (records, total)"""
        if status == BorrowStatus.BORROWING:
            records = self.borrow_repo.get_active_by_child(child_id)
            total = len(records)
        else:
            total = self.borrow_repo.count(child_id=child_id)
            offset = (page - 1) * page_size
            records = self.borrow_repo.list_all(
                limit=page_size, offset=offset, child_id=child_id
            )
        return [BorrowRecordResponse.model_validate(r) for r in records], total
