# backend/common/dependencies.py
"""
[What] FastAPI Depends 工厂 — 统一 Service 实例获取
[Why] Router 不应自建 Service 工厂，统一入口便于横切关注点（日志、监控、权限）
[How] 为每个领域 Service 提供 get_xxx_service 依赖注入函数

架构意图：
  Router 层通过 Depends(get_order_service) 获取 Service 实例，
  不在 Router 中手动构造 Service。

  每个 Service 的构造函数只接收 db: Session，
  内部自行构造 Repository（不在 Router 层传 Repo）。

约束：
  - Service 构造函数只接收 db: Session
  - Depends 工厂自动注入 get_db 的 Session
  - 不在 Router 层手动 new Service()
  - 使用函数内延迟导入避免循环依赖
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.database import get_db


# ============================================================
# 核心域 Service 工厂
# ============================================================


def get_user_service(db: Session = Depends(get_db)):
    from backend.domain.user.service import UserService

    return UserService(db)


def get_child_service(db: Session = Depends(get_db)):
    from backend.domain.child.service import ChildService

    return ChildService(db)


def get_book_service(db: Session = Depends(get_db)):
    from backend.domain.book.service import BookService

    return BookService(db)


def get_bookshelf_service(db: Session = Depends(get_db)):
    from backend.domain.bookshelf.service import BookshelfService

    return BookshelfService(db)


def get_reading_service(db: Session = Depends(get_db)):
    from backend.domain.reading.service import ReadingService

    return ReadingService(db)


def get_vocabulary_service(db: Session = Depends(get_db)):
    from backend.domain.vocabulary.service import VocabularyService

    return VocabularyService(db)


def get_advancement_service(db: Session = Depends(get_db)):
    from backend.domain.advancement.service import AdvancementService

    return AdvancementService(db)


def get_leaderboard_service(db: Session = Depends(get_db)):
    from backend.domain.advancement.leaderboard_service import LeaderboardService

    return LeaderboardService(db)


# ============================================================
# 交易域 Service 工厂
# ============================================================


def get_order_service(db: Session = Depends(get_db)):
    from backend.domain.order.service import OrderService

    return OrderService(db)


def get_refund_service(db: Session = Depends(get_db)):
    from backend.domain.refund.service import RefundService

    return RefundService(db)


# ============================================================
# OMO 域 Service 工厂（V3.1）
# ============================================================


def get_borrow_service(db: Session = Depends(get_db)):
    from backend.domain.borrow.service import BorrowService

    return BorrowService(db)


def get_deposit_service(db: Session = Depends(get_db)):
    from backend.domain.deposit.service import DepositService

    return DepositService(db)


def get_reservation_service(db: Session = Depends(get_db)):
    from backend.domain.reservation.service import ReservationService

    return ReservationService(db)


# ============================================================
# 辅助域 Service 工厂
# ============================================================


def get_report_service(db: Session = Depends(get_db)):
    from backend.domain.report.service import ReportService

    return ReportService(db)


def get_certificate_service(db: Session = Depends(get_db)):
    from backend.domain.certificate.service import CertificateService

    return CertificateService(db)


def get_profile_service(db: Session = Depends(get_db)):
    from backend.domain.profile.service import ProfileService

    return ProfileService(db)


def get_activity_service(db: Session = Depends(get_db)):
    from backend.domain.activity.service import ActivityService

    return ActivityService(db)


def get_admin_service(db: Session = Depends(get_db)):
    from backend.domain.admin.service import AdminService

    return AdminService(db)


def get_admin_venue_service(db: Session = Depends(get_db)):
    from backend.domain.admin.services.venue_service import AdminVenueService

    return AdminVenueService(db)


def get_admin_teacher_service(db: Session = Depends(get_db)):
    from backend.domain.admin.services.teacher_service import AdminTeacherService

    return AdminTeacherService(db)


def get_admin_upload_service(db: Session = Depends(get_db)):
    from backend.domain.admin.services.upload_service import AdminUploadService

    return AdminUploadService(db)


def get_admin_export_service(db: Session = Depends(get_db)):
    from backend.domain.admin.services.export_service import AdminExportService

    return AdminExportService(db)


def get_admin_book_service(db: Session = Depends(get_db)):
    from backend.domain.admin.services.book_service import AdminBookService

    return AdminBookService(db)


def get_admin_report_service(db: Session = Depends(get_db)):
    from backend.domain.admin.services.report_service import AdminReportService

    return AdminReportService(db)


def get_admin_system_service(db: Session = Depends(get_db)):
    from backend.domain.admin.services.system_service import AdminSystemService

    return AdminSystemService(db)


def get_admin_account_service(db: Session = Depends(get_db)):
    from backend.domain.admin.services.account_service import AdminAccountService

    return AdminAccountService(db)


def get_admin_message_service(db: Session = Depends(get_db)):
    from backend.domain.admin.services.message_service import AdminMessageService
    from backend.domain.admin.services.system_service import AdminSystemService

    return AdminMessageService(db, system_service=AdminSystemService(db))


def get_admin_borrow_service(db: Session = Depends(get_db)):
    from backend.domain.admin.services.borrow_service import AdminBorrowService

    return AdminBorrowService(db)


def get_admin_order_service(db: Session = Depends(get_db)):
    from backend.domain.admin.services.order_service import AdminOrderService

    return AdminOrderService(db)


def get_admin_refund_service(db: Session = Depends(get_db)):
    from backend.domain.admin.services.refund_service import AdminRefundService

    return AdminRefundService(db)


def get_admin_user_service(db: Session = Depends(get_db)):
    from backend.domain.admin.services.user_service import AdminUserService

    return AdminUserService(db)


def get_admin_dashboard_service(db: Session = Depends(get_db)):
    from backend.domain.admin.services.dashboard_service import AdminDashboardService

    return AdminDashboardService(db)


def get_message_service(db: Session = Depends(get_db)):
    from backend.domain.message.service import MessageService

    return MessageService(db)
