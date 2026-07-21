"""T3.6a 图书损坏定责 — 管理端服务"""

import logging
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from backend.common.exceptions import NotFoundError, ValidationError
from backend.common.types import BookCopyStatus, BorrowStatus
from backend.domain.book.damage_model import BookDamageReport
from backend.domain.book.models import Book, BookCopy
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.models import Child

logger = logging.getLogger(__name__)


class DamageAdminService:
    """图书损坏定责管理"""

    # 三级定级倍率
    LEVEL_MULTIPLIERS = {
        1: Decimal("0"),  # 轻度 — 免费
        2: Decimal("0.5"),  # 重度 — 0.5×定价
        3: Decimal("1.5"),  # 丢失 — 1.5×定价
    }
    # 丢失定级对应 BookCopy 状态
    LEVEL_COPY_STATUS = {
        3: BookCopyStatus.LOST,
    }

    def __init__(self, db: Session):
        self.db = db

    def create_report(
        self,
        borrow_record_id: int,
        damage_level: int,
        photo_url: str | None = None,
        description: str | None = None,
        admin_id: int = 0,
    ) -> BookDamageReport:
        """创建损坏报告 — 三级定级 + 罚款计算 + D05 联动"""
        record = (
            self.db.query(BorrowRecord)
            .filter(BorrowRecord.id == borrow_record_id, BorrowRecord.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if not record:
            raise NotFoundError("借阅记录不存在")
        if record.status not in (BorrowStatus.BORROWING, BorrowStatus.OVERDUE):
            raise ValidationError(f"当前状态({record.status})不允许登记损坏")

        book = self.db.query(Book).filter(Book.id == record.book_id).first()
        if not book:
            raise NotFoundError("图书不存在")
        book_price = book.price or Decimal("0")
        multiplier = self.LEVEL_MULTIPLIERS.get(damage_level, Decimal("0"))
        fine_amount = (book_price * multiplier).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # 写入 child.outstanding_fines
        child = (
            self.db.query(Child)
            .filter(Child.id == record.child_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if child:
            child.outstanding_fines = (child.outstanding_fines or 0) + fine_amount

        if damage_level == 3:
            # D05 联动：丢失定级 → BookCopy.status = LOST
            if record.book_copy_id:
                copy = (
                    self.db.query(BookCopy)
                    .filter(BookCopy.id == record.book_copy_id)
                    .with_for_update()
                    .first()
                )
                if copy:
                    copy.status = BookCopyStatus.LOST

            # Book 库存扣减
            new_total = max((book.total_stock or 0) - 1, 0)
            new_avail = max((book.available_stock or 0) - 1, 0)
            book.total_stock = new_total
            book.available_stock = new_avail

            # 更新借阅状态为 LOST
            record.status = BorrowStatus.LOST
            record.fine_amount = fine_amount
        else:
            # 非丢失定级，标记借阅为损坏状态（保留借阅记录）
            record.fine_amount = (record.fine_amount or 0) + fine_amount

        report = BookDamageReport(
            borrow_record_id=borrow_record_id,
            book_copy_id=record.book_copy_id,
            child_id=record.child_id,
            damage_level=damage_level,
            photo_url=photo_url,
            description=description,
            fine_amount=fine_amount,
            status=BookDamageReport.STATUS_PENDING,
            admin_id=admin_id,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        self._send_damage_notification(report, child, fine_amount)
        self._log_operation(
            admin_id,
            "damage.create",
            f"定级:{damage_level} 罚款:{fine_amount} 借阅:{borrow_record_id}",
        )
        return report

    def get_list(
        self,
        status: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """查询损坏报告列表"""
        query = self.db.query(BookDamageReport).filter(BookDamageReport.is_deleted == 0)
        if status is not None:
            query = query.filter(BookDamageReport.status == status)
        total = query.count()
        items = (
            query.order_by(BookDamageReport.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {"total": total, "items": items, "page": page, "page_size": page_size}

    def appeal(self, report_id: int, reason: str) -> BookDamageReport:
        """家长申诉（7天申诉期）"""
        report = self._get_report_or_raise(report_id)
        if report.status != BookDamageReport.STATUS_PENDING:
            raise ValidationError("当前状态不允许申诉")
        days_since = (datetime.now().date() - report.create_time.date()).days
        if days_since > 7:
            raise ValidationError(f"已超过7天申诉期（{days_since}天），无法申诉")

        report.status = BookDamageReport.STATUS_DISPUTED
        report.appeal_reason = reason
        self.db.commit()
        self.db.refresh(report)
        return report

    def review(
        self,
        report_id: int,
        action: str,
        override_level: int | None = None,
        override_fine: Decimal | None = None,
        review_remark: str = "",
        admin_id: int = 0,
    ) -> BookDamageReport:
        """管理员审核申诉 — approve（确认）/ override（冲正改判）"""
        report = self._get_report_or_raise(report_id)
        if report.status != BookDamageReport.STATUS_DISPUTED:
            raise ValidationError("只有申诉中的报告可以审核")

        report.appeal_result = review_remark
        report.review_admin_id = admin_id
        report.reviewed_at = datetime.now().isoformat()

        if action == "override":
            if override_level is None and override_fine is None:
                raise ValidationError("冲正必须指定 override_level 或 override_fine")
            if override_fine is None and override_level is not None:
                override_fine = Decimal("0")
            original_level = report.damage_level
            report.override_level = override_level
            report.override_fine = override_fine
            report.status = BookDamageReport.STATUS_OVERRIDDEN

            # 冲正后调整 outstanding_fines：差值回滚
            child = (
                self.db.query(Child)
                .filter(Child.id == report.child_id, Child.is_deleted == 0)
                .with_for_update()
                .first()
            )
            if child:
                old_fine = report.fine_amount or Decimal("0")
                new_fine_actual = override_fine or Decimal("0")
                diff = new_fine_actual - old_fine
                updated = (child.outstanding_fines or 0) + diff
                child.outstanding_fines = updated if updated > 0 else Decimal("0")

            # 同步 record.fine_amount
            record = (
                self.db.query(BorrowRecord)
                .filter(BorrowRecord.id == report.borrow_record_id)
                .with_for_update()
                .first()
            )
            if record:
                record.fine_amount = override_fine

            # P0: 原丢失定级→override 改判→逆向联动 BookCopy/库存/record
            if (
                original_level == 3
                and override_level is not None
                and override_level != 3
            ):
                copy = (
                    self.db.query(BookCopy)
                    .filter(BookCopy.id == report.book_copy_id)
                    .with_for_update()
                    .first()
                )
                if copy:
                    # 恢复 BookCopy.status：1→AVAILABLE 2→DAMAGED
                    copy.status = (
                        BookCopyStatus.AVAILABLE
                        if override_level == 1
                        else BookCopyStatus.DAMAGED
                    )
                # 恢复库存
                book = (
                    self.db.query(Book).filter(Book.id == record.book_id).first()
                    if record
                    else None
                )
                if book:
                    book.total_stock = (book.total_stock or 0) + 1
                    book.available_stock = (book.available_stock or 0) + 1
                # 恢复借阅状态
                if record:
                    now = datetime.now()
                    record.status = (
                        BorrowStatus.OVERDUE
                        if record.due_date and record.due_date < now
                        else BorrowStatus.BORROWING
                    )
        else:  # approve
            report.status = BookDamageReport.STATUS_CONFIRMED

        self.db.commit()
        self.db.refresh(report)
        self._log_operation(
            admin_id, "damage.review", f"报告:{report_id} 操作:{action}"
        )
        return report

    def confirm_expired(self, report_id: int) -> BookDamageReport:
        """申诉期过期自动确认"""
        report = self._get_report_or_raise(report_id)
        if report.status != BookDamageReport.STATUS_PENDING:
            raise ValidationError("当前状态不允许自动确认")
        days_since = (datetime.now().date() - report.create_time.date()).days
        if days_since <= 7:
            raise ValidationError(f"申诉期未过（{days_since}天），不能自动确认")
        report.status = BookDamageReport.STATUS_CONFIRMED
        self.db.commit()
        self.db.refresh(report)
        return report

    def batch_confirm_expired(self) -> int:
        """批量确认过期申诉期报告（status=PENDING AND create_time < now-7d）"""
        cutoff = datetime.now().date()
        expired = (
            self.db.query(BookDamageReport)
            .filter(
                BookDamageReport.is_deleted == 0,
                BookDamageReport.status == BookDamageReport.STATUS_PENDING,
            )
            .all()
        )
        count = 0
        for report in expired:
            days_since = (cutoff - report.create_time.date()).days
            if days_since > 7:
                report.status = BookDamageReport.STATUS_CONFIRMED
                count += 1
        if count:
            self.db.commit()
            logger.info("batch_confirm_expired: 已确认 %d 条过期损坏报告", count)
        return count

    def _get_report_or_raise(self, report_id: int) -> BookDamageReport:
        report = (
            self.db.query(BookDamageReport)
            .filter(BookDamageReport.id == report_id, BookDamageReport.is_deleted == 0)
            .first()
        )
        if not report:
            raise NotFoundError("损坏报告不存在")
        return report

    def _send_damage_notification(
        self, report: BookDamageReport, child, fine_amount: Decimal
    ):
        """创建损坏通知 — 推送给家长"""
        level_names = {1: "轻度（免费）", 2: "重度（0.5×定价）", 3: "丢失（1.5×定价）"}
        level_name = level_names.get(report.damage_level, "未知")
        fine_text = (
            f"罚款¥{fine_amount}" if fine_amount and fine_amount > 0 else "无需罚款"
        )
        from backend.domain.message.models import SystemMessage

        msg = SystemMessage(
            user_id=child.user_id,
            title="图书损坏通知",
            content=f"您的孩子「{child.name}」有图书被定为「{level_name}」，{fine_text}。如有异议请在7天内联系管理员申诉。",
            msg_type=1,
            priority=1,
        )
        self.db.add(msg)
        self.db.flush()

    def _log_operation(self, admin_id: int, action: str, detail: str):
        """记录操作日志"""
        from backend.domain.admin.models import OperationLog

        log = OperationLog(
            admin_id=admin_id,
            module="book_damage",
            operation=action,
            content=detail,
        )
        self.db.add(log)
        self.db.flush()
