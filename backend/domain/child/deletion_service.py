# backend/domain/child/deletion_service.py
"""儿童数据删除权级联删除服务 — P0-3 隐私合规

流程（对齐 专家意见/children_privacy_compliance_20260721.md §4.2/§4.3）：
  1. 家长发起删除请求 → 前置校验（无活跃借阅/无在持押金/无进行中退款）
  2. 软删除 child + 标记 deletion_requested_at（24h 冷静期，期间可取消）
  3. 每日定时任务扫描到期请求 → 备份 CSV → 物理删除非财务数据 → 删除语音文件
  4. 财务数据法定保留（order/deposit_record/refund_application/borrow_record/
     book_damage_report/benefit_transfer_application），由既有 purge 机制按保留期清理
  5. 记录 operation_log + SystemMessage 通知监护人
"""

import csv
import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from backend.common.exceptions import NotFoundError, ValidationError
from backend.common.types import BorrowStatus, DepositStatus
from backend.database import Base

logger = logging.getLogger(__name__)

# 物理删除：child_id 直接关联的非财务表（对应文档 §4.2 清单）
# 勘误说明（对 专家意见/children_privacy_compliance_20260721.md §4.2）：
#   - parent_course_time 是场馆排期表（venue_id 关联），无 child_id，不属于儿童数据，已移除
#   - quiz 表有 child_id，文档遗漏，已补入
#   - quiz_answer 无 child_id，经 quiz_id 特殊级联删除（见 DELETE_TABLES_VIA_QUIZ）
DELETE_TABLES_BY_CHILD = [
    "reading_session",
    "reading_progress",
    "check_in",
    "voice_recording",
    "user_vocabulary",
    "quiz",
    "reading_submission",
    "child_level",
    "child_achievement",
    "level_certificate",
    "bookshelf",
    "favorites",
    "activity_enrollment",
    "reservation",
    "observation_report",
    "learning_report",
    "ar_evaluation",
    "observation_evaluation",
    "guidance_record",
]

# 经 quiz_id 间接关联的表（quiz_answer.quiz_id → quiz.child_id）
DELETE_TABLES_VIA_QUIZ = ["quiz_answer"]

# 物理删除：user_id 关联
DELETE_TABLES_BY_USER = ["message_read_status"]

# 法定保留（仅声明，本服务不触碰）
RETAINED_TABLES = [
    "borrow_record",
    "deposit_record",
    "order",
    "refund_application",
    "book_damage_report",
    "benefit_transfer_application",
]

GRACE_HOURS = 24
PROJECT_ROOT = Path(__file__).resolve().parents[3]
UPLOADS_DIR = PROJECT_ROOT / "uploads"


class ChildDeletionService:
    def __init__(self, db: Session):
        self.db = db

    # ── 前置校验 ──

    def check_deletion_blockers(self, child_id: int) -> list[str]:
        """返回阻塞原因列表，空列表=可删除"""
        from backend.domain.borrow.models import BorrowRecord
        from backend.domain.child.models import Child
        from backend.domain.refund.models import RefundApplication

        blockers: list[str] = []

        active_borrows = (
            self.db.query(BorrowRecord)
            .filter(
                BorrowRecord.child_id == child_id,
                BorrowRecord.status.in_([BorrowStatus.BORROWING, BorrowStatus.OVERDUE]),
                BorrowRecord.is_deleted == 0,
            )
            .count()
        )
        if active_borrows:
            blockers.append(f"有 {active_borrows} 本图书未归还，请先归还")

        child = (
            self.db.query(Child)
            .filter(Child.id == child_id, Child.is_deleted == 0)
            .first()
        )
        if child and child.deposit_status in (
            DepositStatus.PAID,
            DepositStatus.PENDING,
            DepositStatus.REFUNDING,
        ):
            blockers.append("押金尚未结清，请先申请押金退款")

        pending_refunds = (
            self.db.query(RefundApplication)
            .filter(
                RefundApplication.child_id == child_id,
                RefundApplication.status == RefundApplication.STATUS_PENDING,
                RefundApplication.is_deleted == 0,
            )
            .count()
        )
        if pending_refunds:
            blockers.append(f"有 {pending_refunds} 笔退款正在审核，请等待处理完成")

        return blockers

    # ── 删除请求（24h 冷静期）──

    def request_deletion(self, user_id: int, child_id: int) -> dict:
        """发起删除请求：前置校验 → 软删除 + 标记冷静期"""
        from backend.domain.child.models import Child

        child = (
            self.db.query(Child)
            .filter(
                Child.id == child_id, Child.user_id == user_id, Child.is_deleted == 0
            )
            .first()
        )
        if not child:
            raise NotFoundError("孩子不存在或已删除")

        blockers = self.check_deletion_blockers(child_id)
        if blockers:
            raise ValidationError("；".join(blockers))

        now = datetime.now()
        child.is_deleted = 1
        child.deletion_requested_at = now
        self._write_log(
            user_id,
            child_id,
            "deletion_request",
            f"发起删除请求，{GRACE_HOURS}小时冷静期",
        )
        self.db.commit()

        execute_after = now + timedelta(hours=GRACE_HOURS)
        logger.info(f"Child deletion requested: child={child_id} by user={user_id}")
        return {
            "success": True,
            "message": f"删除请求已提交，{GRACE_HOURS}小时内可取消",
            "execute_after": execute_after.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def cancel_deletion(self, user_id: int, child_id: int) -> dict:
        """冷静期内取消删除请求"""
        from backend.domain.child.models import Child

        child = (
            self.db.query(Child)
            .filter(Child.id == child_id, Child.user_id == user_id)
            .first()
        )
        if not child or child.is_deleted != 1 or child.deletion_requested_at is None:
            raise NotFoundError("没有进行中的删除请求")

        child.is_deleted = 0
        child.deletion_requested_at = None
        self._write_log(user_id, child_id, "deletion_cancel", "冷静期内取消删除请求")
        self.db.commit()
        logger.info(f"Child deletion cancelled: child={child_id} by user={user_id}")
        return {"success": True, "message": "删除请求已取消"}

    # ── 定时执行（scheduler 每日扫描）──

    def execute_due_deletions(self) -> dict:
        """执行所有冷静期已过的删除请求，返回处理统计"""
        from backend.domain.child.models import Child

        cutoff = datetime.now() - timedelta(hours=GRACE_HOURS)
        due_children = (
            self.db.query(Child)
            .filter(
                Child.is_deleted == 1,
                Child.deletion_requested_at.isnot(None),
                Child.deletion_requested_at <= cutoff,
            )
            .all()
        )

        executed = 0
        for child in due_children:
            try:
                self._execute_one(child)
                executed += 1
            except Exception:
                self.db.rollback()
                logger.exception(f"Child deletion execution failed: child={child.id}")
        return {"due": len(due_children), "executed": executed}

    def _execute_one(self, child) -> None:
        """单个孩子的级联删除执行体（备份→删行→提交→删文件→通知）"""
        child_id = child.id
        user_id = child.user_id

        # 1. 删除前备份（与 purge_soft_deleted 同一模式）
        backup_dir = self._backup_child_rows(child_id, user_id)

        # 2. 先收集语音文件路径（删行后再查就查不到了）
        voice_files = self._collect_voice_files(child_id)

        # 3. 物理删除非财务数据（先特殊级联，再常规 child_id/user_id 删除）
        deleted_counts: dict[str, int] = {}
        deleted_counts.update(self._delete_via_quiz(child_id))
        for table_name in DELETE_TABLES_BY_CHILD:
            deleted_counts[table_name] = self._delete_by_column(
                table_name, "child_id", child_id
            )
        for table_name in DELETE_TABLES_BY_USER:
            deleted_counts[table_name] = self._delete_by_column(
                table_name, "user_id", user_id
            )

        # 4. 清除冷静期标记（child 行保留软删除，由 purge 机制按保留期物理清理）
        child.deletion_requested_at = None
        self._write_log(
            user_id,
            child_id,
            "deletion_executed",
            f"级联删除完成: {deleted_counts}; 备份: {backup_dir}",
        )
        self.db.commit()

        # 5. 提交后删除语音文件（顺序不可颠倒：collect→删行→commit→删文件）
        files_removed = self._delete_voice_files(voice_files)

        # 6. 通知监护人
        self._notify_user(user_id, child.name or "", files_removed)
        self.db.commit()
        logger.info(
            f"Child deletion executed: child={child_id}, "
            f"rows={sum(deleted_counts.values())}, files={files_removed}"
        )

    # ── 内部工具 ──

    def _delete_via_quiz(self, child_id: int) -> dict[str, int]:
        """特殊级联：quiz_answer 经 quiz_id → quiz.child_id 删除"""
        quiz_tbl = Base.metadata.tables.get("quiz")
        counts: dict[str, int] = {}
        if quiz_tbl is None:
            return counts
        quiz_ids = [
            r[0]
            for r in self.db.execute(
                quiz_tbl.select()
                .with_only_columns(quiz_tbl.c.id)
                .where(quiz_tbl.c.child_id == child_id)
            ).all()
        ]
        for table_name in DELETE_TABLES_VIA_QUIZ:
            table = Base.metadata.tables.get(table_name)
            if table is None or not quiz_ids:
                counts[table_name] = 0
                continue
            result = self.db.execute(
                table.delete().where(table.c.quiz_id.in_(quiz_ids))
            )
            counts[table_name] = result.rowcount or 0
        return counts

    def _delete_by_column(self, table_name: str, column: str, value: int) -> int:
        table = Base.metadata.tables.get(table_name)
        if table is None:
            logger.warning(f"Deletion skip: table {table_name} not in metadata")
            return 0
        result = self.db.execute(table.delete().where(table.c[column] == value))
        return result.rowcount or 0

    def _backup_child_rows(self, child_id: int, user_id: int) -> str:
        backup_dir = (
            PROJECT_ROOT
            / "backups"
            / f"child_deletion_{datetime.now():%Y%m%d}"
            / f"child_{child_id}"
        )
        backup_dir.mkdir(parents=True, exist_ok=True)
        for table_name in DELETE_TABLES_BY_CHILD:
            self._dump_table(table_name, "child_id", child_id, backup_dir)
        for table_name in DELETE_TABLES_BY_USER:
            self._dump_table(table_name, "user_id", user_id, backup_dir)
        self._dump_quiz_answer(child_id, backup_dir)
        return str(backup_dir.relative_to(PROJECT_ROOT))

    def _dump_quiz_answer(self, child_id: int, out_dir: Path) -> None:
        """备份 quiz_answer（经 quiz_id 关联）"""
        quiz_tbl = Base.metadata.tables.get("quiz")
        qa_tbl = Base.metadata.tables.get("quiz_answer")
        if quiz_tbl is None or qa_tbl is None:
            return
        quiz_ids = [
            r[0]
            for r in self.db.execute(
                quiz_tbl.select()
                .with_only_columns(quiz_tbl.c.id)
                .where(quiz_tbl.c.child_id == child_id)
            ).all()
        ]
        if not quiz_ids:
            return
        rows = (
            self.db.execute(qa_tbl.select().where(qa_tbl.c.quiz_id.in_(quiz_ids)))
            .mappings()
            .all()
        )
        if not rows:
            return
        out_file = out_dir / "quiz_answer.csv"
        with out_file.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def _dump_table(
        self, table_name: str, column: str, value: int, out_dir: Path
    ) -> None:
        table = Base.metadata.tables.get(table_name)
        if table is None:
            return
        rows = (
            self.db.execute(table.select().where(table.c[column] == value))
            .mappings()
            .all()
        )
        if not rows:
            return
        out_file = out_dir / f"{table_name}.csv"
        with out_file.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def _collect_voice_files(self, child_id: int) -> list[str]:
        table = Base.metadata.tables.get("voice_recording")
        if table is None:
            return []
        rows = (
            self.db.execute(
                table.select()
                .with_only_columns(table.c.audio_url)
                .where(table.c.child_id == child_id)
            )
            .scalars()
            .all()
        )
        return [u for u in rows if u]

    @staticmethod
    def _delete_voice_files(audio_urls: list[str]) -> int:
        removed = 0
        for url in audio_urls:
            if url.startswith("http://") or url.startswith("https://"):
                continue  # 远程文件不删除
            rel = url.lstrip("/")
            if rel.startswith("uploads/"):
                rel = rel[len("uploads/") :]
            path = (UPLOADS_DIR / rel).resolve()
            # 防路径穿越：必须位于 uploads/ 之内
            if not str(path).startswith(str(UPLOADS_DIR.resolve())):
                logger.warning(f"Voice file path escape blocked: {url}")
                continue
            try:
                if path.is_file():
                    path.unlink()
                    removed += 1
            except OSError:
                logger.exception(f"Voice file delete failed: {path}")
        return removed

    def _write_log(
        self, user_id: int, child_id: int, operation: str, content: str
    ) -> None:
        from backend.domain.admin.models import OperationLog

        self.db.add(
            OperationLog(
                admin_id=0,
                module="child",
                operation=operation,
                content=f"user={user_id} child={child_id} {content}",
            )
        )

    def _notify_user(self, user_id: int, child_name: str, files_removed: int) -> None:
        from backend.domain.message.models import SystemMessage

        self.db.add(
            SystemMessage(
                user_id=user_id,
                msg_type=1,
                title="数据删除完成",
                content=(
                    f"您申请删除的孩子{child_name}的数据已处理完成"
                    f"（含语音文件 {files_removed} 个）。"
                    "交易凭证类数据将按法规要求保留至期限届满后自动清理。"
                ),
            )
        )
