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
        """创建损坏报告 — 三级定级 + B9 双人复核 + B10 丢失寻找期

        - 轻度(1)：免费，即时生效（无争议风险）
        - 重度(2)/丢失(3)：物理效应（副本/库存/借阅状态）即时，
          财务效应（outstanding_fines）延迟到第二管理员复核（damage_dual_review）
        - 丢失(3)：写入 lost_search_deadline（7 天寻找期，B10）
        """
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

        # F-001/004：库存读-改-写必须行锁（并发报损双扣/丢更新）
        book = (
            self.db.query(Book)
            .filter(Book.id == record.book_id)
            .with_for_update()
            .first()
        )
        if not book:
            raise NotFoundError("图书不存在")
        book_price = book.price or Decimal("0")
        # F59：同一借阅存在未终结报告时禁止重复登记（此前可重复计费）
        active_report = (
            self.db.query(BookDamageReport)
            .filter(
                BookDamageReport.borrow_record_id == borrow_record_id,
                BookDamageReport.status.in_(
                    [
                        BookDamageReport.STATUS_PENDING,
                        BookDamageReport.STATUS_PENDING_REVIEW,
                        BookDamageReport.STATUS_DISPUTED,
                    ]
                ),
                BookDamageReport.is_deleted == 0,
            )
            .first()
        )
        if active_report:
            raise ValidationError("该借阅已有未终结的损坏报告，请先处理")

        multiplier = self.LEVEL_MULTIPLIERS.get(damage_level, Decimal("0"))
        fine_amount = (book_price * multiplier).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        from backend.common.config_service import ConfigService

        dual_review = ConfigService.get_bool(self.db, "damage_dual_review", True)
        needs_review = dual_review and damage_level in (2, 3) and fine_amount > 0

        child = (
            self.db.query(Child)
            .filter(Child.id == record.child_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if child and not needs_review:
            # 无需复核（轻度 或 复核开关关闭）→ 即时计入未缴罚款
            # F61 交互：丢失（level 3）覆盖已入账逾期费——只补差额并同步标记
            if damage_level == 3:
                prior_marker = record.fine_in_outstanding or Decimal("0")
                delta = fine_amount - prior_marker
                child.outstanding_fines = (child.outstanding_fines or 0) + delta
                record.fine_in_outstanding = fine_amount
            else:
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

            # 更新借阅状态为 LOST + B10 寻找期
            record.status = BorrowStatus.LOST
            record.fine_amount = fine_amount
            search_days = ConfigService.get_int(self.db, "lost_search_days", 7)
            from datetime import timedelta

            record.lost_search_deadline = datetime.now() + timedelta(days=search_days)
        else:
            # 非丢失定级，标记借阅为损坏状态（保留借阅记录）
            record.fine_amount = (record.fine_amount or 0) + fine_amount
            if damage_level == 2 and record.book_copy_id:
                # F50：重度损坏（level 2）同步标记副本 DAMAGED（此前三级定级名存实亡）
                copy = (
                    self.db.query(BookCopy)
                    .filter(BookCopy.id == record.book_copy_id)
                    .with_for_update()
                    .first()
                )
                if copy:
                    copy.status = BookCopyStatus.DAMAGED

        report = BookDamageReport(
            borrow_record_id=borrow_record_id,
            book_copy_id=record.book_copy_id,
            child_id=record.child_id,
            damage_level=damage_level,
            photo_url=photo_url,
            description=description,
            fine_amount=fine_amount,
            status=BookDamageReport.STATUS_PENDING_REVIEW
            if needs_review
            else BookDamageReport.STATUS_PENDING,
            admin_id=admin_id,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        if needs_review:
            self._send_review_pending_notification(report, child, fine_amount)
        else:
            self._send_damage_notification(report, child, fine_amount)
        self._log_operation(
            admin_id,
            "damage.create",
            f"定级:{damage_level} 罚款:{fine_amount} 借阅:{borrow_record_id}"
            f"{'（待复核）' if needs_review else ''}",
        )
        return report

    def confirm_report(self, report_id: int, admin_id: int) -> BookDamageReport:
        """B9 双人复核：第二管理员确认定责 → 财务效应生效（计入未缴罚款）"""
        report = self._get_report_or_raise(report_id)
        if report.status != BookDamageReport.STATUS_PENDING_REVIEW:
            raise ValidationError("仅待复核状态的报告可确认")
        if report.admin_id and report.admin_id == admin_id:
            raise ValidationError("复核人不能是登记人本人（双人复核）")

        child = (
            self.db.query(Child)
            .filter(Child.id == report.child_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )
        fine = report.fine_amount or Decimal("0")
        if child:
            child.outstanding_fines = (child.outstanding_fines or 0) + fine

        report.status = BookDamageReport.STATUS_PENDING  # 进入 7 天申诉期
        report.review_admin_id = admin_id
        report.reviewed_at = datetime.now()
        self.db.commit()
        self.db.refresh(report)
        if child:
            self._send_damage_notification(report, child, fine)
        self._log_operation(admin_id, "damage.confirm", f"复核确认 报告:{report_id}")
        return report

    def reject_report(
        self, report_id: int, admin_id: int, reason: str = ""
    ) -> BookDamageReport:
        """B9 双人复核：第二管理员驳回定责 → 物理效应回滚（丢失定级）"""
        report = self._get_report_or_raise(report_id)
        if report.status != BookDamageReport.STATUS_PENDING_REVIEW:
            raise ValidationError("仅待复核状态的报告可驳回")
        if report.admin_id and report.admin_id == admin_id:
            raise ValidationError("复核人不能是登记人本人（双人复核）")

        if report.damage_level == 3:
            self._rollback_lost_physical(report)

        report.status = BookDamageReport.STATUS_CANCELLED
        report.review_admin_id = admin_id
        report.reviewed_at = datetime.now()
        report.appeal_result = reason or "复核驳回：定责不成立"
        self.db.commit()
        self.db.refresh(report)
        self._log_operation(
            admin_id, "damage.reject", f"复核驳回 报告:{report_id} 原因:{reason}"
        )
        return report

    def mark_book_found(self, borrow_record_id: int, admin_id: int) -> dict:
        """B10 找回回滚：已按丢失处理的图书找回

        - 寻找期内找回：全额免赔（fine 冲正为 0）
        - 超过寻找期：同样冲正未缴罚款（已缴部分需线下协商，此处只冲正 outstanding）
        """
        record = (
            self.db.query(BorrowRecord)
            .filter(BorrowRecord.id == borrow_record_id, BorrowRecord.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if not record:
            raise NotFoundError("借阅记录不存在")
        if record.status != BorrowStatus.LOST:
            raise ValidationError("该记录不是丢失状态，无需找回")

        within_window = bool(
            record.lost_search_deadline
            and datetime.now() <= record.lost_search_deadline
        )

        # 物理回滚：副本/库存
        copy = None
        if record.book_copy_id:
            copy = (
                self.db.query(BookCopy)
                .filter(BookCopy.id == record.book_copy_id)
                .with_for_update()
                .first()
            )
            if copy and copy.status == BookCopyStatus.LOST:
                copy.status = BookCopyStatus.AVAILABLE

        book = (
            self.db.query(Book)
            .filter(Book.id == record.book_id)
            .with_for_update()
            .first()
        )
        if book:
            book.total_stock = (book.total_stock or 0) + 1
            book.available_stock = (book.available_stock or 0) + 1

        report = (
            self.db.query(BookDamageReport)
            .filter(
                BookDamageReport.borrow_record_id == borrow_record_id,
                BookDamageReport.damage_level == 3,
                BookDamageReport.status.in_(
                    [
                        BookDamageReport.STATUS_PENDING,
                        BookDamageReport.STATUS_PENDING_REVIEW,
                        BookDamageReport.STATUS_CONFIRMED,
                    ]
                ),
                BookDamageReport.is_deleted == 0,
            )
            .first()
        )

        # 财务回滚：冲正丢失罚款（含关联损坏报告）
        fine = record.fine_amount or Decimal("0")
        child = (
            self.db.query(Child)
            .filter(Child.id == record.child_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )
        waived = Decimal("0")
        # 无报告（mark_book_lost 路径直接计费）→ 应冲正；仅 PENDING_REVIEW（未入账）跳过
        charged = report is None or report.status != (
            BookDamageReport.STATUS_PENDING_REVIEW
        )
        # F48：待复核报告从未入账（confirm 才计 outstanding）——找回不得冲销孩子其他合法罚款
        if child and fine > 0 and charged:
            waived = min(fine, child.outstanding_fines or Decimal("0"))
            child.outstanding_fines = (child.outstanding_fines or 0) - waived

        if report:
            report.override_fine = Decimal("0")
            report.status = BookDamageReport.STATUS_OVERRIDDEN
            report.review_admin_id = admin_id
            report.reviewed_at = datetime.now()
            report.appeal_result = (
                "寻找期内找回，全额免赔" if within_window else "逾期找回，冲正未缴罚款"
            )

        record.status = BorrowStatus.RETURNED
        record.return_time = datetime.now()
        record.fine_amount = Decimal("0")
        record.fine_in_outstanding = Decimal(
            "0"
        )  # 找回后本记录无已入账罚款（F48-F50 交互）
        record.lost_search_deadline = None

        self.db.commit()
        self._log_operation(
            admin_id,
            "damage.found",
            f"丢失找回 借阅:{borrow_record_id} 免赔:{waived} 期内:{within_window}",
        )
        return {
            "success": True,
            "borrow_record_id": borrow_record_id,
            "waived_amount": str(waived),
            "within_search_window": within_window,
        }

    def replace_with_new_copy(
        self, borrow_record_id: int, barcode: str, admin_id: int
    ) -> dict:
        """B10 买同 ISBN 新书归还替代赔偿：登记新副本 + 全额免赔"""
        record = (
            self.db.query(BorrowRecord)
            .filter(BorrowRecord.id == borrow_record_id, BorrowRecord.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if not record:
            raise NotFoundError("借阅记录不存在")
        if record.status != BorrowStatus.LOST:
            raise ValidationError("该记录不是丢失状态，无法用新书替代")

        existing = (
            self.db.query(BookCopy)
            .filter(BookCopy.barcode == barcode, BookCopy.is_deleted == 0)
            .first()
        )
        if existing:
            raise ValidationError(f"条码 {barcode} 已存在，请换一个新条码")

        # 新副本入库
        new_copy = BookCopy(
            book_id=record.book_id,
            barcode=barcode,
            status=BookCopyStatus.AVAILABLE,
        )
        self.db.add(new_copy)

        book = (
            self.db.query(Book)
            .filter(Book.id == record.book_id)
            .with_for_update()
            .first()
        )
        if book:
            book.total_stock = (book.total_stock or 0) + 1
            book.available_stock = (book.available_stock or 0) + 1

        report = (
            self.db.query(BookDamageReport)
            .filter(
                BookDamageReport.borrow_record_id == borrow_record_id,
                BookDamageReport.damage_level == 3,
                BookDamageReport.status.in_(
                    [
                        BookDamageReport.STATUS_PENDING,
                        BookDamageReport.STATUS_PENDING_REVIEW,
                        BookDamageReport.STATUS_CONFIRMED,
                    ]
                ),
                BookDamageReport.is_deleted == 0,
            )
            .first()
        )

        # 全额免赔
        fine = record.fine_amount or Decimal("0")
        child = (
            self.db.query(Child)
            .filter(Child.id == record.child_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )
        waived = Decimal("0")
        charged = report is None or report.status != (
            BookDamageReport.STATUS_PENDING_REVIEW
        )
        # F48：同 mark_book_found——待复核报告不得冲销其他罚款
        if child and fine > 0 and charged:
            waived = min(fine, child.outstanding_fines or Decimal("0"))
            child.outstanding_fines = (child.outstanding_fines or 0) - waived

        if report:
            report.override_fine = Decimal("0")
            report.status = BookDamageReport.STATUS_OVERRIDDEN
            report.review_admin_id = admin_id
            report.reviewed_at = datetime.now()
            report.appeal_result = f"购同ISBN新书归还替代赔偿（新条码:{barcode}）"

        record.status = BorrowStatus.RETURNED
        record.return_time = datetime.now()
        record.fine_amount = Decimal("0")
        record.fine_in_outstanding = Decimal("0")  # 替代赔偿后本记录无已入账罚款
        record.lost_search_deadline = None

        self.db.commit()
        self.db.refresh(new_copy)
        self._log_operation(
            admin_id,
            "damage.replace_new",
            f"新书替代 借阅:{borrow_record_id} 新副本:{new_copy.id} 免赔:{waived}",
        )
        return {
            "success": True,
            "borrow_record_id": borrow_record_id,
            "new_copy_id": new_copy.id,
            "waived_amount": str(waived),
        }

    def _rollback_lost_physical(self, report: BookDamageReport) -> None:
        """丢失定级的物理效应回滚（复核驳回用，不自行 commit）"""
        if report.book_copy_id:
            copy = (
                self.db.query(BookCopy)
                .filter(BookCopy.id == report.book_copy_id)
                .with_for_update()
                .first()
            )
            if copy and copy.status == BookCopyStatus.LOST:
                copy.status = BookCopyStatus.AVAILABLE

        record = (
            self.db.query(BorrowRecord)
            .filter(BorrowRecord.id == report.borrow_record_id)
            .with_for_update()
            .first()
        )
        if record:
            book = (
                self.db.query(Book)
                .filter(Book.id == record.book_id)
                .with_for_update()
                .first()
            )
            if book:
                book.total_stock = (book.total_stock or 0) + 1
                book.available_stock = (book.available_stock or 0) + 1
            now = datetime.now()
            record.status = (
                BorrowStatus.OVERDUE
                if record.due_date and record.due_date < now
                else BorrowStatus.BORROWING
            )
            record.fine_amount = Decimal("0")
            record.lost_search_deadline = None

    def get_list(
        self,
        status: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """查询损坏报告列表"""
        from backend.domain.book.damage_schemas import DamageReportResponse

        query = self.db.query(BookDamageReport).filter(BookDamageReport.is_deleted == 0)
        if status is not None:
            query = query.filter(BookDamageReport.status == status)
        total = query.count()
        reports = (
            query.order_by(BookDamageReport.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        # F-089：ORM 对象无法经 AdminActionResponse 序列化（PydanticSerializationError 500），
        # 转 JSON dict（Decimal→str、datetime→ISO）
        items = [
            DamageReportResponse.model_validate(r).model_dump(mode="json")
            for r in reports
        ]
        return {"total": total, "items": items, "page": page, "page_size": page_size}

    def appeal(self, report_id: int, reason: str) -> BookDamageReport:
        """家长申诉（7天申诉期）"""
        report = self._get_report_or_raise(report_id)
        if report.status != BookDamageReport.STATUS_PENDING:
            raise ValidationError("当前状态不允许申诉")
        # F62：申诉期从进入 PENDING（双人复核通过 reviewed_at）起算，而非报告创建日——
        # 与 confirm_expired/batch_confirm_expired 同口径（复核通过前家长无法申诉）
        baseline = report.reviewed_at or report.create_time
        days_since = (datetime.now().date() - baseline.date()).days
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
        report.reviewed_at = datetime.now()

        if action == "override":
            if override_level is None and override_fine is None:
                raise ValidationError("冲正必须指定 override_level 或 override_fine")
            if override_fine is None and override_level is not None:
                if override_level == 2:
                    # F49：改判重度未填金额 → 按 0.5×定价计算默认值（此前直接清零）
                    record_price = None
                    if report.book_copy_id:
                        copy = (
                            self.db.query(BookCopy)
                            .filter(BookCopy.id == report.book_copy_id)
                            .first()
                        )
                        if copy:
                            book = (
                                self.db.query(Book)
                                .filter(Book.id == copy.book_id)
                                .first()
                            )
                            record_price = book.price if book else None
                    if record_price is None:
                        br = (
                            self.db.query(BorrowRecord)
                            .filter(BorrowRecord.id == report.borrow_record_id)
                            .first()
                        )
                        if br:
                            book = (
                                self.db.query(Book)
                                .filter(Book.id == br.book_id)
                                .first()
                            )
                            record_price = book.price if book else None
                    override_fine = (
                        (record_price or Decimal("0")) * self.LEVEL_MULTIPLIERS[2]
                    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                else:
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
                    self.db.query(Book)
                    .filter(Book.id == record.book_id)
                    .with_for_update()
                    .first()
                    if record
                    else None
                )
                if book:
                    book.total_stock = (book.total_stock or 0) + 1
                    # F49：改判→重度（DAMAGED）不可借，available 不得 +1（附录 D 口径）
                    if override_level == 1:
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
        # F62：申诉期从进入 PENDING（双人复核通过 reviewed_at）起算，而非报告创建日
        baseline = report.reviewed_at or report.create_time
        days_since = (datetime.now().date() - baseline.date()).days
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
            baseline = report.reviewed_at or report.create_time
            days_since = (cutoff - baseline.date()).days
            if days_since > 7:
                report.status = BookDamageReport.STATUS_CONFIRMED
                count += 1
        if count:
            self.db.commit()
            logger.info("batch_confirm_expired: 已确认 %d 条过期损坏报告", count)
        return count

    def _get_report_or_raise(self, report_id: int) -> BookDamageReport:
        # F-080：行锁串行化 confirm/reject/review/appeal/confirm_expired——
        # 并发双确认双计罚款的根因（report 状态层无锁）
        report = (
            self.db.query(BookDamageReport)
            .filter(BookDamageReport.id == report_id, BookDamageReport.is_deleted == 0)
            .with_for_update()
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
            f"服务费¥{fine_amount}" if fine_amount and fine_amount > 0 else "无需费用"
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

    def _send_review_pending_notification(
        self, report: BookDamageReport, child, fine_amount: Decimal
    ):
        """B9 待复核通知 — 财务效应生效前告知家长（复核中）"""
        from backend.domain.message.models import SystemMessage

        msg = SystemMessage(
            user_id=child.user_id,
            title="图书损坏定责复核中",
            content=(
                f"您的孩子「{child.name}」有图书损坏定责正在复核，"
                f"复核通过后将产生服务费¥{fine_amount}。如有异议请提前联系管理员。"
            ),
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
