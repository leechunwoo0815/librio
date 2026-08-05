# backend/domain/reservation/service.py
"""预约域业务逻辑 — V3.1 预约借书

预约 → 锁定库存 → 72h内取书 → 转为借阅
过期 → 释放库存
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.common.events import (
    ReservationCancelledEvent,
    ReservationCreatedEvent,
    ReservationFulfilledEvent,
    ReservationExpiredEvent,
    event_bus,
)
from backend.common.exceptions import ConflictError, NotFoundError, ValidationError
from backend.common.types import ReservationStatus
from backend.domain.book.models import Book
from backend.domain.child.service import assert_no_pending_transfer
from backend.domain.reservation.models import Reservation
from backend.domain.reservation.repository import ReservationRepository
from backend.domain.reservation.schemas import (
    ReservationCreateRequest,
    ReservationFulfillRequest,
    ReservationResponse,
)

logger = logging.getLogger(__name__)

RESERVATION_HOURS = (
    72  # 默认值，通过 ConfigService.get_int(db, "reservation_expire_hours", 72) 读取
)


class ReservationService:
    """预约服务"""

    def __init__(self, db: Session):
        self.db = db
        self.reservation_repo = ReservationRepository(db)
        self.book_repo = BaseRepository(db, Book)

    def create_reservation(self, data: ReservationCreateRequest) -> ReservationResponse:
        """创建预约 — 锁定库存"""
        book = (
            self.db.query(Book)
            .filter(Book.id == data.book_id, Book.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if not book:
            raise NotFoundError("书不存在")
        if not book.offline_available:
            raise ValidationError("该书不支持线下借阅")
        if (book.available_stock or 0) <= 0:
            raise ValidationError("该书暂无库存")

        assert_no_pending_transfer(self.db, data.child_id)

        # 重复预约校验
        from backend.common.types import ReservationStatus

        existing = (
            self.db.query(Reservation)
            .filter(
                Reservation.child_id == data.child_id,
                Reservation.book_id == data.book_id,
                Reservation.status == ReservationStatus.PENDING,
                Reservation.is_deleted == 0,
            )
            .first()
        )
        if existing:
            raise ConflictError("该孩子已预约同一本书，请等待取书或取消后再预约")

        # F46：已有同书未还借阅 → 拦截（状态流转图 9.3；避免库存白锁最长 72h）
        from backend.domain.borrow.models import BorrowRecord
        from backend.common.types import BorrowStatus

        active_borrow = (
            self.db.query(BorrowRecord.id)
            .filter(
                BorrowRecord.child_id == data.child_id,
                BorrowRecord.book_id == data.book_id,
                BorrowRecord.status.in_([BorrowStatus.BORROWING, BorrowStatus.OVERDUE]),
                BorrowRecord.is_deleted == 0,
            )
            .first()
        )
        if active_borrow:
            raise ValidationError("该孩子已有同一本书的未还借阅，请先归还")

        # 从配置读取预约过期时间
        from backend.common.config_service import ConfigService

        expire_hours = ConfigService.get_int(
            self.db, "reservation_expire_hours", RESERVATION_HOURS
        )

        reservation = Reservation(
            child_id=data.child_id,
            book_id=data.book_id,
            venue_id=data.venue_id,
            status=ReservationStatus.PENDING,
            expire_time=datetime.now() + timedelta(hours=expire_hours),
        )
        created = self.reservation_repo.create(reservation)

        # F4：该孩子对此书的等候单标记成交（先到先得闭环）
        self._fulfill_waitlist(data.child_id, data.book_id)

        # 发布预约创建事件（book 域扣库存）
        event_bus.publish(
            ReservationCreatedEvent(
                child_id=data.child_id,
                book_id=data.book_id,
                reservation_id=created.id,
            ),
            db=self.db,
        )

        self.db.commit()
        return ReservationResponse.model_validate(created)

    def fulfill_reservation(
        self, data: ReservationFulfillRequest
    ) -> ReservationResponse:
        """取书 — 转为正式借阅（扫码枪条码驱动 或 手动预约ID 备用）"""
        from backend.domain.book.models import BookCopy
        from backend.common.types import BookCopyStatus
        from backend.domain.reservation.models import Reservation

        # B1a 条码先行：扫副本条码 → 定位图书与副本
        copy = None
        if data.barcode:
            copy = (
                self.db.query(BookCopy)
                .filter(BookCopy.barcode == data.barcode, BookCopy.is_deleted == 0)
                .first()
            )
            if not copy:
                raise NotFoundError(f"条码 {data.barcode} 不存在，请先扫描入库")
            if copy.status != BookCopyStatus.AVAILABLE:
                raise ConflictError("该副本状态异常，请联系工作人员")

        # 定位预约：显式 reservation_id 或按副本图书匹配最早待取预约
        if data.reservation_id:
            reservation = self.reservation_repo.get_by_id_or_raise(data.reservation_id)
        elif copy:
            reservation = (
                self.db.query(Reservation)
                .filter(
                    Reservation.book_id == copy.book_id,
                    Reservation.status == ReservationStatus.PENDING,
                    Reservation.is_deleted == 0,
                )
                .order_by(Reservation.create_time)
                .first()
            )
            if not reservation:
                raise NotFoundError("该书当前没有待取预约")
        else:
            raise ValidationError("请提供预约ID或扫描副本条码")

        if reservation.status != ReservationStatus.PENDING:
            raise ConflictError("预约状态不正确")

        if datetime.now() > reservation.expire_time:
            raise ValidationError("预约已过期")

        # B1a 扫码取书：校验副本并定位到本（P0：取书精确到具体副本）
        book_copy_id = None
        if copy:
            if copy.book_id != reservation.book_id:
                raise ValidationError("所扫副本与预约图书不符")
            book_copy_id = copy.id

        # 校验借阅上限
        from backend.domain.borrow.models import BorrowRecord
        from backend.common.types import BorrowStatus
        from backend.common.config_service import ConfigService

        max_borrow = ConfigService.get_int(self.db, "borrow_limit", 10)
        active_count = (
            self.db.query(BorrowRecord)
            .filter(
                BorrowRecord.child_id == reservation.child_id,
                BorrowRecord.status.in_([BorrowStatus.BORROWING, BorrowStatus.OVERDUE]),
                BorrowRecord.is_deleted == 0,
            )
            .count()
        )
        if active_count >= max_borrow:
            raise ValidationError("小书架满啦！先还一本，再借新的吧～")

        # F42：手动取书（无条码）强制绑定一本 AVAILABLE 副本，杜绝 book_copy_id=None 孤儿借阅
        if book_copy_id is None:
            copy = (
                self.db.query(BookCopy)
                .filter(
                    BookCopy.book_id == reservation.book_id,
                    BookCopy.status == BookCopyStatus.AVAILABLE,
                    BookCopy.is_deleted == 0,
                )
                .order_by(BookCopy.id)
                .first()
            )
            if not copy:
                raise ValidationError("该书暂无可用副本，请先扫码入库")
            book_copy_id = copy.id

        # F45：条件 UPDATE（WHERE id=? AND status=PENDING AND 未过期），按 affected rows 判定
        now = datetime.now()
        affected = (
            self.db.query(Reservation)
            .filter(
                Reservation.id == reservation.id,
                Reservation.status == ReservationStatus.PENDING,
                Reservation.expire_time > now,
                Reservation.is_deleted == 0,
            )
            .update(
                {
                    Reservation.status: ReservationStatus.FULFILLED,
                    Reservation.fulfilled_time: now,
                },
                synchronize_session=False,
            )
        )
        if affected != 1:
            fresh = (
                self.db.query(Reservation)
                .filter(Reservation.id == reservation.id)
                .first()
            )
            if fresh and fresh.status != ReservationStatus.PENDING:
                raise ConflictError("预约状态已变化，无法取书")
            raise ValidationError("预约已过期")
        self.db.refresh(
            reservation
        )  # 条件 UPDATE 后同步 ORM 状态（synchronize_session=False）

        # 发布取书事件（borrow 域创建借阅记录）
        event_bus.publish(
            ReservationFulfilledEvent(
                child_id=reservation.child_id,
                book_id=reservation.book_id,
                reservation_id=reservation.id,
                book_copy_id=book_copy_id,
            ),
            db=self.db,
        )

        self.db.commit()
        return ReservationResponse.model_validate(reservation)

    def expire_reservation(self, reservation_id: int) -> None:
        """过期预约 — 释放库存（定时任务调用，不自行 commit）

        F45：条件 UPDATE（WHERE id=? AND status=PENDING），按 affected rows 判定——
        与取书/取消同锁口径，杜绝并发下"已取书/已取消仍被过期释放库存"。
        """
        affected = (
            self.db.query(Reservation)
            .filter(
                Reservation.id == reservation_id,
                Reservation.status == ReservationStatus.PENDING,
                Reservation.is_deleted == 0,
            )
            .update(
                {Reservation.status: ReservationStatus.EXPIRED},
                synchronize_session=False,
            )
        )
        if affected != 1:
            return  # 已过期/已取书/已取消，不重复释放

        reservation = (
            self.db.query(Reservation).filter(Reservation.id == reservation_id).first()
        )
        if not reservation:
            return

        event_bus.publish(
            ReservationExpiredEvent(
                child_id=reservation.child_id,
                book_id=reservation.book_id,
                reservation_id=reservation.id,
            ),
            db=self.db,
        )

    def get_child_reservations(self, child_id: int) -> list[ReservationResponse]:
        """孩子的全部预约（含已结束），附带图书标题/封面"""
        from backend.domain.book.models import Book

        records = (
            self.db.query(Reservation)
            .filter(Reservation.child_id == child_id, Reservation.is_deleted == 0)
            .order_by(Reservation.create_time.desc())
            .limit(50)
            .all()
        )
        book_ids = {r.book_id for r in records}
        books = {}
        if book_ids:
            books = {
                b.id: b for b in self.db.query(Book).filter(Book.id.in_(book_ids)).all()
            }
        result = []
        for r in records:
            resp = ReservationResponse.model_validate(r)
            book = books.get(r.book_id)
            resp.book_title = book.title if book else None
            resp.book_cover = book.cover if book else None
            result.append(resp)
        return result

    # ==================== F4 等候名单 ====================

    def join_waitlist(self, child_id: int, book_id: int) -> dict:
        """加入等候名单 — 库存为 0 时的出路（F4）

        规则：有库存应直接预约；同一孩子同书仅一条活跃等候；已预约同书不可重复等候
        """
        book = (
            self.db.query(Book).filter(Book.id == book_id, Book.is_deleted == 0).first()
        )
        if not book:
            raise NotFoundError("书不存在")
        if not book.offline_available:
            raise ValidationError("该书不支持线下借阅")
        if (book.available_stock or 0) > 0:
            raise ValidationError("该书有库存，请直接预约")

        from backend.domain.reservation.models import BookWaitlist

        active_reservation = (
            self.db.query(Reservation)
            .filter(
                Reservation.child_id == child_id,
                Reservation.book_id == book_id,
                Reservation.status == ReservationStatus.PENDING,
                Reservation.is_deleted == 0,
            )
            .first()
        )
        if active_reservation:
            raise ConflictError("该孩子已预约本书，无需加入等候")

        existing = (
            self.db.query(BookWaitlist)
            .filter(
                BookWaitlist.child_id == child_id,
                BookWaitlist.book_id == book_id,
                BookWaitlist.status.in_(
                    [BookWaitlist.STATUS_WAITING, BookWaitlist.STATUS_NOTIFIED]
                ),
                BookWaitlist.is_deleted == 0,
            )
            .first()
        )
        if existing:
            raise ConflictError("已在等候名单中，请留意到货通知")

        entry = BookWaitlist(child_id=child_id, book_id=book_id)
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return {
            "success": True,
            "waitlist_id": entry.id,
            "message": "已加入等候名单，到货将第一时间通知您",
        }

    def cancel_waitlist(self, waitlist_id: int, user_id: int | None = None) -> dict:
        """取消等候"""
        from backend.common.exceptions import ForbiddenError
        from backend.domain.child.models import Child
        from backend.domain.reservation.models import BookWaitlist

        entry = (
            self.db.query(BookWaitlist)
            .filter(BookWaitlist.id == waitlist_id, BookWaitlist.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if not entry:
            raise NotFoundError("等候记录不存在")
        if entry.status not in (
            BookWaitlist.STATUS_WAITING,
            BookWaitlist.STATUS_NOTIFIED,
        ):
            raise ConflictError("该等候已结束")

        if user_id is not None:
            child = (
                self.db.query(Child)
                .filter(Child.id == entry.child_id, Child.is_deleted == 0)
                .first()
            )
            if not child or child.user_id != user_id:
                raise ForbiddenError("无权操作该等候")

        entry.status = BookWaitlist.STATUS_CANCELLED
        self.db.commit()
        return {"success": True, "message": "已取消等候"}

    def get_child_waitlist(self, child_id: int) -> list[dict]:
        """孩子的活跃等候名单（附图书标题/封面）"""
        from backend.domain.reservation.models import BookWaitlist

        records = (
            self.db.query(BookWaitlist)
            .filter(
                BookWaitlist.child_id == child_id,
                BookWaitlist.status.in_(
                    [BookWaitlist.STATUS_WAITING, BookWaitlist.STATUS_NOTIFIED]
                ),
                BookWaitlist.is_deleted == 0,
            )
            .order_by(BookWaitlist.create_time)
            .limit(50)
            .all()
        )
        book_ids = {r.book_id for r in records}
        books = {}
        if book_ids:
            books = {
                b.id: b for b in self.db.query(Book).filter(Book.id.in_(book_ids)).all()
            }
        return [
            {
                "id": r.id,
                "book_id": r.book_id,
                "book_title": books[r.book_id].title if r.book_id in books else None,
                "book_cover": books[r.book_id].cover if r.book_id in books else None,
                "status": r.status,
                "notify_time": r.notify_time.isoformat() if r.notify_time else None,
                "create_time": r.create_time.isoformat() if r.create_time else None,
            }
            for r in records
        ]

    def _fulfill_waitlist(self, child_id: int, book_id: int) -> None:
        """孩子成功预约 → 关闭其对此书的活跃等候（不自行 commit）"""
        from backend.domain.reservation.models import BookWaitlist

        self.db.query(BookWaitlist).filter(
            BookWaitlist.child_id == child_id,
            BookWaitlist.book_id == book_id,
            BookWaitlist.status.in_(
                [BookWaitlist.STATUS_WAITING, BookWaitlist.STATUS_NOTIFIED]
            ),
            BookWaitlist.is_deleted == 0,
        ).update({BookWaitlist.status: BookWaitlist.STATUS_FULFILLED})

    @staticmethod
    def notify_next_waiter(db: Session, book_id: int) -> bool:
        """F4：库存释放/到货时通知队首（先到先得，不自行 commit）

        仅在确有库存时通知；通知后家长可自行预约（预约即关闭等候）。
        """
        from backend.domain.reservation.models import BookWaitlist
        from backend.domain.message.models import SystemMessage

        book = db.query(Book).filter(Book.id == book_id, Book.is_deleted == 0).first()
        if not book or (book.available_stock or 0) <= 0:
            return False

        entry = (
            db.query(BookWaitlist)
            .filter(
                BookWaitlist.book_id == book_id,
                BookWaitlist.status == BookWaitlist.STATUS_WAITING,
                BookWaitlist.is_deleted == 0,
            )
            .order_by(BookWaitlist.create_time)
            .with_for_update()
            .first()
        )
        if not entry:
            return False

        from backend.domain.child.models import Child

        child = (
            db.query(Child)
            .filter(Child.id == entry.child_id, Child.is_deleted == 0)
            .first()
        )
        if not child:
            return False

        entry.status = BookWaitlist.STATUS_NOTIFIED
        entry.notify_time = datetime.now()
        db.add(
            SystemMessage(
                user_id=child.user_id,
                title="您等候的图书到货啦",
                content=f"您等候的《{book.title}》现在有库存了，先到先得，快来预约吧～",
                msg_type=3,  # 借阅通知
                priority=1,
            )
        )
        logger.info(
            f"WAITLIST_NOTIFIED: book={book_id}, child={entry.child_id}, entry={entry.id}"
        )
        return True

    def cancel_reservation(
        self, reservation_id: int, user_id: int | None = None
    ) -> dict:
        """取消预约"""
        from backend.common.exceptions import ForbiddenError, NotFoundError
        from backend.domain.child.models import Child

        record = (
            self.db.query(Reservation)
            .filter(Reservation.id == reservation_id, Reservation.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if not record:
            raise NotFoundError("预约不存在")
        if record.status != ReservationStatus.PENDING:
            # F40：仅 PENDING→CANCELLED——EXPIRED/FULFILLED 取消会致库存双重释放/幻影库存
            raise ConflictError(f"仅待取预约可取消（当前状态 {record.status}）")

        if user_id is not None:
            child = (
                self.db.query(Child)
                .filter(Child.id == record.child_id, Child.is_deleted == 0)
                .first()
            )
            if not child or child.user_id != user_id:
                raise ForbiddenError("无权操作该预约")

        affected = (
            self.db.query(Reservation)
            .filter(
                Reservation.id == reservation_id,
                Reservation.status == ReservationStatus.PENDING,
                Reservation.is_deleted == 0,
            )
            .update(
                {Reservation.status: ReservationStatus.CANCELLED},
                synchronize_session=False,
            )
        )
        if affected != 1:
            raise ConflictError("预约状态已变化，无法取消")

        event_bus.publish(
            ReservationCancelledEvent(
                child_id=record.child_id,
                book_id=record.book_id,
                reservation_id=record.id,
            ),
            db=self.db,
        )

        self.db.commit()
        return {"success": True, "message": "预约已取消"}
