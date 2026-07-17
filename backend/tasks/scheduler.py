# backend/tasks/scheduler.py
"""
[What] 定时任务调度器
[Why] 会员到期提醒、学习报告生成
[How] 使用APScheduler，启动时注册所有定时任务
"""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import func as sql_func
from backend.common.distributed_lock import distributed_lock
from backend.common.types import MemberStatus

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def init_scheduler(app):
    """
    [What] 初始化定时任务调度器
    [Why] FastAPI lifespan中调用
    [How] 注册所有任务并启动
    """
    # 每天早上9点：检查会员到期提醒
    scheduler.add_job(
        check_member_expiry,
        CronTrigger(hour=9, minute=0),
        id="check_member_expiry",
        replace_existing=True,
    )

    # 每周一早上8点：生成周报
    scheduler.add_job(
        generate_weekly_reports,
        CronTrigger(day_of_week="mon", hour=8, minute=0),
        id="generate_weekly_reports",
        replace_existing=True,
    )

    # 每月1号早上8点：生成月报
    scheduler.add_job(
        generate_monthly_reports,
        CronTrigger(day=1, hour=8, minute=0),
        id="generate_monthly_reports",
        replace_existing=True,
    )

    # 每天凌晨2点：检查缓冲期关停
    scheduler.add_job(
        check_grace_period_shutdown,
        CronTrigger(hour=2, minute=0),
        id="check_grace_period_shutdown",
        replace_existing=True,
    )

    # 每分钟：订单30分钟未支付自动关闭
    scheduler.add_job(
        close_expired_orders,
        CronTrigger(minute="*/1"),
        id="close_expired_orders",
        replace_existing=True,
    )

    # 每5分钟：活动状态自动迁移
    scheduler.add_job(
        migrate_activity_status,
        CronTrigger(minute="*/5"),
        id="migrate_activity_status",
        replace_existing=True,
    )

    # 每天11点：晋级待审超过7天提醒
    scheduler.add_job(
        remind_pending_submissions,
        CronTrigger(hour=11, minute=0),
        id="remind_pending_submissions",
        replace_existing=True,
    )

    # 每天12点：退款7天未到账告警
    scheduler.add_job(
        alert_stale_refunds,
        CronTrigger(hour=12, minute=0),
        id="alert_stale_refunds",
        replace_existing=True,
    )

    # 每天凌晨1点：借阅到期提醒
    scheduler.add_job(
        check_due_date_reminders,
        CronTrigger(hour=1, minute=0),
        id="check_due_date_reminders",
        replace_existing=True,
    )

    # 每30分钟：预约过期检查
    scheduler.add_job(
        expire_reservations,
        CronTrigger(minute="*/30"),
        id="expire_reservations",
        replace_existing=True,
    )

    # 每天凌晨2点30分：逾期检测
    scheduler.add_job(
        mark_overdue_books,
        CronTrigger(hour=2, minute=30),
        id="mark_overdue_books",
        replace_existing=True,
    )

    # 每天早上9点：观察期到期提醒
    scheduler.add_job(
        check_observation_reminders,
        CronTrigger(hour=9, minute=0),
        id="check_observation_reminders",
        replace_existing=True,
    )

    # 每天早上9点30分：观察期到期检查
    scheduler.add_job(
        check_observation_expiry,
        CronTrigger(hour=9, minute=30),
        id="check_observation_expiry",
        replace_existing=True,
    )

    # 每天早上10点：活动开始前3天提醒
    scheduler.add_job(
        check_activity_reminders,
        CronTrigger(hour=10, minute=0),
        id="check_activity_reminders",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started with 14 jobs")


def stop_scheduler():
    """停止调度器"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def _get_db_session():
    """获取数据库会话"""
    from backend.database import get_session

    return get_session()()


def _create_message(
    db, user_id: int, title: str, content: str, msg_type: int = 1, priority: int = 0
):
    """写入系统消息"""
    from backend.domain.message.models import SystemMessage

    msg = SystemMessage(
        user_id=user_id,
        title=title,
        content=content,
        msg_type=msg_type,
        priority=priority,
    )
    db.add(msg)


@distributed_lock("job:check_member_expiry", timeout=600)
def check_member_expiry():
    """
    [What] 会员到期提醒
    [Why] 正式会员到期前提醒续费
    [How] 查询即将到期的正式会员，写入消息表
    """
    from backend.domain.child.models import Child

    db = _get_db_session()
    try:
        from backend.common.config_service import ConfigService

        today = date.today()
        notify_days = ConfigService.get_int_list(
            db, "member_expire_remind_days", [30, 15, 7, 3, 2, 1, 0]
        )

        for days in notify_days:
            target_date = today + timedelta(days=days)
            children = (
                db.query(Child)
                .filter(
                    Child.status == MemberStatus.OFFICIAL,
                    Child.member_expire_time.isnot(None),
                    sql_func.date(Child.member_expire_time) == target_date,
                    Child.is_deleted == 0,
                )
                .all()
            )

            for child in children:
                _create_message(
                    db,
                    user_id=child.user_id,
                    title="会员续费提醒",
                    content=f"您的孩子 {child.name} 的正式会员将在{days}天后（{target_date}）到期，请及时续费以免影响阅读。",
                    msg_type=5,
                    priority=1 if days <= 3 else 0,
                )
                logger.info(
                    f"MEMBER_EXPIRY: child={child.id}, name={child.name}, "
                    f"expires={target_date}, days_left={days}"
                )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"check_member_expiry failed: {e}", exc_info=True)
    finally:
        db.close()


@distributed_lock("job:check_grace_period_shutdown", timeout=600)
def check_grace_period_shutdown():
    """
    [What] 检查缓冲期关停
    [Why] 到期15天后自动关停账号
    [How] 查询已过期超过15天的会员，标记为已过期
    """
    from backend.domain.child.models import Child

    db = _get_db_session()
    try:
        # 从配置读取缓冲期天数
        from backend.common.config_service import ConfigService

        grace_days = ConfigService.get_int(db, "member_grace_days", 15)
        cutoff = datetime.now() - timedelta(days=grace_days)

        expired = (
            db.query(Child)
            .filter(
                Child.status == MemberStatus.OFFICIAL,
                Child.member_expire_time.isnot(None),
                Child.member_expire_time < cutoff,
                Child.is_deleted == 0,
            )
            .all()
        )

        for child in expired:
            old_status = child.status
            child.status = MemberStatus.EXPIRED
            logger.info(
                f"GRACE_SHUTDOWN: child={child.id}, name={child.name}, {old_status} -> {MemberStatus.EXPIRED}"
            )

        if expired:
            db.commit()
            logger.info(f"Grace period shutdown: {len(expired)} children expired")
    except Exception as e:
        db.rollback()
        logger.error(f"check_grace_period_shutdown failed: {e}", exc_info=True)
    finally:
        db.close()


@distributed_lock("job:generate_weekly_reports", timeout=600)
def generate_weekly_reports():
    """
    [What] 生成周报
    [Why] 每周一自动生成上周阅读报告
    [How] 查询每个child上周的阅读数据，生成报告
    """
    from backend.domain.child.models import Child
    from backend.domain.report.service import ReportService

    db = _get_db_session()
    try:
        children = (
            db.query(Child)
            .filter(
                Child.status.in_([MemberStatus.OBSERVATION, MemberStatus.OFFICIAL]),
                Child.is_deleted == 0,
            )
            .all()
        )

        svc = ReportService(db)
        count = 0
        for child in children:
            try:
                report = svc.generate_weekly_report(child.id)
                logger.info(
                    f"WEEKLY_REPORT: child={child.id}, minutes={report['total_minutes']}, books={report['books_finished']}"
                )
                count += 1
            except Exception as e:
                logger.error(f"Weekly report failed for child {child.id}: {e}")

        logger.info(f"Weekly reports generated: {count}")
    except Exception as e:
        db.rollback()
        logger.error(f"generate_weekly_reports failed: {e}", exc_info=True)
    finally:
        db.close()


@distributed_lock("job:generate_monthly_reports", timeout=600)
def generate_monthly_reports():
    """
    [What] 生成月报 + 平台级月度统计
    [Why] 每月1日自动生成上月阅读报告，同时汇总平台级运营指标
    [How] 查询每个child上月的阅读数据；汇总新增用户/活跃用户/借阅TOP10/测评通过率/退费率
    """
    from backend.domain.child.models import Child
    from backend.domain.report.service import ReportService
    from backend.domain.user.models import User
    from backend.domain.borrow.models import BorrowRecord
    from backend.domain.advancement.models import Quiz
    from backend.domain.reading.models import ReadingSession
    from backend.domain.order.models import Order
    from backend.domain.book.models import Book

    db = _get_db_session()
    try:
        # 上月时间范围
        today = date.today()
        last_month_end = today.replace(day=1) - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)

        # === 平台级月度统计 ===

        # 新增用户数
        new_users = (
            db.query(sql_func.count(User.id))
            .filter(
                User.create_time >= last_month_start,
                User.create_time <= last_month_end,
                User.is_deleted == 0,
            )
            .scalar()
            or 0
        )

        # 活跃用户数（上月有阅读会话的不同 child）
        active_users = (
            db.query(sql_func.count(sql_func.distinct(ReadingSession.child_id)))
            .filter(
                ReadingSession.start_time >= last_month_start,
                ReadingSession.start_time <= last_month_end,
                ReadingSession.is_deleted == 0,
            )
            .scalar()
            or 0
        )

        # 借阅 TOP10（上月借阅量最多的书）
        top_books = (
            db.query(
                BorrowRecord.book_id,
                sql_func.count(BorrowRecord.id).label("borrow_count"),
            )
            .filter(
                BorrowRecord.create_time >= last_month_start,
                BorrowRecord.create_time <= last_month_end,
                BorrowRecord.is_deleted == 0,
            )
            .group_by(BorrowRecord.book_id)
            .order_by(sql_func.count(BorrowRecord.id).desc())
            .limit(10)
            .all()
        )

        top_books_info = []
        for book_id, borrow_count in top_books:
            book = db.query(Book).filter(Book.id == book_id).first()
            top_books_info.append(
                {
                    "book_id": book_id,
                    "title": book.title if book else "未知",
                    "borrow_count": borrow_count,
                }
            )

        # 测评通过率
        total_quizzes = (
            db.query(sql_func.count(Quiz.id))
            .filter(
                Quiz.status == Quiz.STATUS_COMPLETED,
                Quiz.create_time >= last_month_start,
                Quiz.create_time <= last_month_end,
                Quiz.is_deleted == 0,
            )
            .scalar()
            or 0
        )
        passed_quizzes = (
            db.query(sql_func.count(Quiz.id))
            .filter(
                Quiz.status == Quiz.STATUS_COMPLETED,
                Quiz.score >= 70,
                Quiz.create_time >= last_month_start,
                Quiz.create_time <= last_month_end,
                Quiz.is_deleted == 0,
            )
            .scalar()
            or 0
        )
        quiz_pass_rate = (
            round(passed_quizzes / total_quizzes * 100, 1) if total_quizzes > 0 else 0.0
        )

        # 退费率
        total_paid_orders = (
            db.query(sql_func.count(Order.id))
            .filter(
                Order.pay_status == 1,
                Order.create_time >= last_month_start,
                Order.create_time <= last_month_end,
                Order.is_deleted == 0,
            )
            .scalar()
            or 0
        )
        refunded_orders = (
            db.query(sql_func.count(Order.id))
            .filter(
                Order.refund_status.in_([1, 2]),  # REFUND_PROCESSING, REFUND_DONE
                Order.create_time >= last_month_start,
                Order.create_time <= last_month_end,
                Order.is_deleted == 0,
            )
            .scalar()
            or 0
        )
        refund_rate = (
            round(refunded_orders / total_paid_orders * 100, 1)
            if total_paid_orders > 0
            else 0.0
        )

        logger.info(
            f"MONTHLY_PLATFORM_STATS: period={last_month_start}~{last_month_end}, "
            f"new_users={new_users}, active_users={active_users}, "
            f"quiz_pass_rate={quiz_pass_rate}%, refund_rate={refund_rate}%, "
            f"top_books={[b['title'] + '(' + str(b['borrow_count']) + ')' for b in top_books_info]}"
        )

        # === 逐 child 生成月报 ===
        children = (
            db.query(Child)
            .filter(
                Child.status.in_([MemberStatus.OBSERVATION, MemberStatus.OFFICIAL]),
                Child.is_deleted == 0,
            )
            .all()
        )

        svc = ReportService(db)
        count = 0
        for child in children:
            try:
                report = svc.generate_monthly_report(child.id)
                logger.info(
                    f"MONTHLY_REPORT: child={child.id}, minutes={report['total_minutes']}, "
                    f"books={report['books_finished']}, checkin_rate={report['checkin_rate']}%"
                )
                count += 1
            except Exception as e:
                logger.error(f"Monthly report failed for child {child.id}: {e}")

        logger.info(f"Monthly reports generated: {count}")
    except Exception as e:
        db.rollback()
        logger.error(f"generate_monthly_reports failed: {e}", exc_info=True)
    finally:
        db.close()


@distributed_lock("job:close_expired_orders", timeout=120)
def close_expired_orders():
    """
    [What] 关闭超时未支付订单
    [Why] 下单后30分钟未支付自动关闭
    [How] 查询待支付且创建时间超过30分钟的订单
    """
    from backend.domain.order.models import Order
    from backend.common.types import PayStatus

    db = _get_db_session()
    try:
        # 从配置读取订单超时时间
        from backend.common.config_service import ConfigService

        timeout_minutes = ConfigService.get_int(db, "order_expire_minutes", 30)
        cutoff = datetime.now() - timedelta(minutes=timeout_minutes)
        expired = (
            db.query(Order)
            .filter(
                Order.pay_status == PayStatus.PENDING,
                Order.create_time < cutoff,
                Order.is_deleted == 0,
            )
            .all()
        )
        for order in expired:
            order.pay_status = PayStatus.CLOSED
            logger.info(f"ORDER_CLOSED: {order.order_no}, created={order.create_time}")
        if expired:
            db.commit()
            logger.info(f"Expired orders closed: {len(expired)}")
    except Exception as e:
        db.rollback()
        logger.error(f"close_expired_orders failed: {e}", exc_info=True)
    finally:
        db.close()


@distributed_lock("job:migrate_activity_status", timeout=120)
def migrate_activity_status():
    """
    [What] 活动状态自动迁移
    [Why] 报名截止/进行中/结束 三个时间点自动切换状态
    [How] 根据当前时间与活动时间比较，自动迁移状态
    """
    from backend.domain.activity.models import Activity

    db = _get_db_session()
    try:
        now = datetime.now()
        migrated = 0

        # 报名中 → 报名截止（到达报名截止时间）
        activities = (
            db.query(Activity)
            .filter(
                Activity.status == Activity.STATUS_ENROLLING,
                Activity.enroll_deadline.isnot(None),
                Activity.enroll_deadline < now,
                Activity.is_deleted == 0,
            )
            .all()
        )
        for a in activities:
            a.status = Activity.STATUS_ENROLL_CLOSED
            migrated += 1

        # 报名截止 → 进行中（到达开始时间）
        activities = (
            db.query(Activity)
            .filter(
                Activity.status == Activity.STATUS_ENROLL_CLOSED,
                Activity.start_time <= now,
                Activity.is_deleted == 0,
            )
            .all()
        )
        for a in activities:
            a.status = Activity.STATUS_IN_PROGRESS
            migrated += 1

        # 进行中 → 已结束（到达结束时间）
        activities = (
            db.query(Activity)
            .filter(
                Activity.status == Activity.STATUS_IN_PROGRESS,
                Activity.end_time < now,
                Activity.is_deleted == 0,
            )
            .all()
        )
        for a in activities:
            a.status = Activity.STATUS_FINISHED
            migrated += 1

        if migrated:
            db.commit()
            logger.info(f"Activity status migrated: {migrated} changes")
    except Exception as e:
        db.rollback()
        logger.error(f"migrate_activity_status failed: {e}", exc_info=True)
    finally:
        db.close()


@distributed_lock("job:remind_pending_submissions", timeout=120)
def remind_pending_submissions():
    """
    [What] 晋级待审超过7天提醒
    [Why] 提交审核超过7天未处理时提醒老师
    [How] 查询超过7天仍为待审核的提交记录，写入消息表
    """
    from backend.domain.advancement.models import ReadingSubmission
    from backend.domain.child.models import Child

    db = _get_db_session()
    try:
        cutoff = datetime.now() - timedelta(days=7)
        pending = (
            db.query(ReadingSubmission)
            .filter(
                ReadingSubmission.status == ReadingSubmission.STATUS_PENDING,
                ReadingSubmission.submitted_at < cutoff,
            )
            .all()
        )
        for s in pending:
            child = db.query(Child).filter(Child.id == s.child_id).first()
            if child and child.teacher_id:
                days = (datetime.now() - s.submitted_at).days
                _create_message(
                    db,
                    user_id=child.user_id,
                    title="待审核提醒",
                    content=f"孩子 {child.name} 的阅读提交已等待审核 {days} 天，请及时处理",
                    msg_type=5,
                    priority=1,
                )
            logger.warning(
                f"STALE_SUBMISSION: id={s.id}, child={s.child_id}, book={s.book_id}"
            )
        if pending:
            db.commit()
            logger.info(f"Stale submissions reminder: {len(pending)}")
    except Exception as e:
        db.rollback()
        logger.error(f"remind_pending_submissions failed: {e}", exc_info=True)
    finally:
        db.close()


@distributed_lock("job:alert_stale_refunds", timeout=120)
def alert_stale_refunds():
    """
    [What] 退款7天未到账告警
    [Why] 审核通过超过7天仍未退款成功时告警
    [How] 查询退款状态为已批准且审核时间超过7天的记录，写入消息表
    """
    from backend.domain.refund.models import RefundApplication

    db = _get_db_session()
    try:
        cutoff = datetime.now() - timedelta(days=7)
        stale = (
            db.query(RefundApplication)
            .filter(
                RefundApplication.status == RefundApplication.STATUS_APPROVED,
                RefundApplication.review_time < cutoff,
                RefundApplication.is_deleted == 0,
            )
            .all()
        )
        for r in stale:
            logger.warning(
                f"STALE_REFUND: id={r.id}, order={r.order_id}, amount={r.refund_amount}, "
                f"review_time={r.review_time}, days_overdue={(datetime.now() - r.review_time).days}"
            )
            _create_message(
                db,
                user_id=r.user_id,
                title="退款超时告警",
                content=f"退款申请 #{r.id} 已审核通过超过7天仍未到账，金额 {r.refund_amount} 元",
                msg_type=5,
                priority=2,
            )
        if stale:
            db.commit()
            logger.info(f"Stale refunds alert: {len(stale)}")
    except Exception as e:
        db.rollback()
        logger.error(f"alert_stale_refunds failed: {e}", exc_info=True)
    finally:
        db.close()


@distributed_lock("job:check_due_date_reminders", timeout=600)
def check_due_date_reminders():
    """
    [What] 借阅到期提醒
    [Why] 到期前5/3/1/当天发送提醒
    [How] 查询即将到期的借阅记录，写入消息表
    """
    from backend.domain.borrow.models import BorrowRecord
    from backend.domain.child.models import Child
    from backend.domain.book.models import Book
    from backend.common.types import BorrowStatus

    db = _get_db_session()
    try:
        from backend.common.config_service import ConfigService

        today = date.today()
        remind_days = ConfigService.get_int_list(db, "due_remind_days", [5, 3, 1, 0])

        for days in remind_days:
            target_date = today + timedelta(days=days)
            # 使用 JOIN 一次查询，避免 N+1
            records = (
                db.query(BorrowRecord, Child, Book)
                .join(Child, BorrowRecord.child_id == Child.id)
                .outerjoin(Book, BorrowRecord.book_id == Book.id)
                .filter(
                    BorrowRecord.status == BorrowStatus.BORROWING,
                    BorrowRecord.is_deleted == 0,
                    BorrowRecord.due_date.isnot(None),
                )
                .all()
            )

            for record, child, book in records:
                if record.due_date and record.due_date.date() == target_date:
                    if not child:
                        continue
                    book_name = book.title if book else "图书"
                    if days == 0:
                        msg = f"您借阅的《{book_name}》今天到期，请尽快归还"
                    elif days == 1:
                        msg = f"您借阅的《{book_name}》将于明天到期"
                    else:
                        msg = f"您借阅的《{book_name}》将于{days}天后到期"
                    _create_message(
                        db,
                        user_id=child.user_id,
                        title="借阅到期提醒",
                        content=msg,
                        msg_type=5,
                    )
                    logger.info(
                        f"DUE_REMIND: child={child.id}, book={record.book_id}, days={days}"
                    )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"check_due_date_reminders failed: {e}", exc_info=True)
    finally:
        db.close()


@distributed_lock("job:expire_reservations", timeout=120)
def expire_reservations():
    """
    [What] 预约过期检查
    [Why] 72小时未取书自动取消预约并释放库存
    [How] 查询过期预约，通过 Service 层处理过期逻辑
    """
    from backend.domain.reservation.models import Reservation
    from backend.common.types import ReservationStatus
    from backend.domain.reservation.service import ReservationService

    db = _get_db_session()
    try:
        now = datetime.now()
        expired = (
            db.query(Reservation)
            .filter(
                Reservation.status == ReservationStatus.PENDING,
                Reservation.expire_time < now,
                Reservation.is_deleted == 0,
            )
            .all()
        )

        svc = ReservationService(db)
        for r in expired:
            try:
                svc.expire_reservation(r.id)
                logger.info(
                    f"RESERVATION_EXPIRED: id={r.id}, child={r.child_id}, book={r.book_id}"
                )
            except Exception as e:
                logger.error(f"Failed to expire reservation {r.id}: {e}")

        if expired:
            db.commit()
            logger.info(f"Reservations expired: {len(expired)}")
    except Exception as e:
        db.rollback()
        logger.error(f"expire_reservations failed: {e}", exc_info=True)
    finally:
        db.close()


@distributed_lock("job:mark_overdue_books", timeout=600)
def mark_overdue_books():
    """
    [What] 逾期检测 + 罚款按日累计
    [Why] 超过21天未还的借阅记录标记为逾期，已逾期的更新罚款
    [How] 查询到期日已过的BORROWING/OVERDUE记录，更新状态和罚款
    """
    from backend.domain.borrow.models import BorrowRecord
    from backend.domain.child.models import Child
    from backend.common.types import BorrowStatus
    from backend.common.config_service import ConfigService

    db = _get_db_session()
    try:
        now = datetime.now()
        daily_fine = ConfigService.get_decimal(db, "overdue_fine_per_day", Decimal("1"))

        # 新逾期：BORROWING → OVERDUE
        new_overdue = (
            db.query(BorrowRecord)
            .filter(
                BorrowRecord.status == BorrowStatus.BORROWING,
                BorrowRecord.due_date < now,
                BorrowRecord.is_deleted == 0,
            )
            .all()
        )

        for record in new_overdue:
            overdue_days = (now - record.due_date).days
            record.status = BorrowStatus.OVERDUE
            record.overdue_days = overdue_days
            record.fine_amount = Decimal(str(overdue_days)) * daily_fine
            logger.debug(
                f"BOOK_OVERDUE: id={record.id}, child={record.child_id}, book={record.book_id}, days={overdue_days}"
            )

        # 已逾期：更新罚款按日累计
        existing_overdue = (
            db.query(BorrowRecord)
            .filter(
                BorrowRecord.status == BorrowStatus.OVERDUE,
                BorrowRecord.is_deleted == 0,
            )
            .all()
        )

        for record in existing_overdue:
            current_days = (now - record.due_date).days
            if current_days > (record.overdue_days or 0):
                record.overdue_days = current_days
                record.fine_amount = Decimal(str(current_days)) * daily_fine

        # 按孩子汇总 outstanding_fines（覆盖模式，避免双写分叉）
        affected_child_ids = set()
        for record in new_overdue + existing_overdue:
            affected_child_ids.add(record.child_id)

        for child_id in affected_child_ids:
            total_fine = Decimal("0")
            for record in new_overdue + existing_overdue:
                if record.child_id == child_id:
                    total_fine += record.fine_amount or Decimal("0")
            child = (
                db.query(Child)
                .filter(Child.id == child_id, Child.is_deleted == 0)
                .first()
            )
            if child:
                child.outstanding_fines = total_fine

        total = len(new_overdue) + len(existing_overdue)
        if total:
            db.commit()
            logger.info(
                f"Overdue books processed: {len(new_overdue)} new, {len(existing_overdue)} updated"
            )
    except Exception as e:
        db.rollback()
        logger.error(f"mark_overdue_books failed: {e}", exc_info=True)
    finally:
        db.close()


@distributed_lock("job:check_observation_expiry", timeout=600)
def check_observation_expiry():
    """
    [What] 观察期到期检查 + 自动生成评估报告
    [Why] 观察期到期后自动设置为 EXPIRED，并生成报告引导转化
    [How] 1. 生成观察期报告 2. 状态变更 OBSERVATION→EXPIRED
    """
    from backend.domain.child.models import Child
    from backend.common.types import MemberStatus

    db = _get_db_session()
    try:
        now = datetime.now()
        expired = (
            db.query(Child)
            .filter(
                Child.status == MemberStatus.OBSERVATION,
                Child.member_expire_time < now,
                Child.is_deleted == 0,
            )
            .all()
        )

        if not expired:
            return

        # 1. 生成观察期报告（在状态变更前，因为 generate_due_reports 查询 OBSERVATION 状态）
        try:
            from backend.domain.report.service import ReportService

            report_svc = ReportService(db)
            generated = report_svc.generate_due_reports()
            logger.info(
                f"Observation reports generated: {len(generated)} for {len(expired)} expired children"
            )
        except Exception as e:
            logger.error(f"Failed to generate observation reports: {e}", exc_info=True)

        # 2. 状态变更
        for child in expired:
            child.status = MemberStatus.EXPIRED
            logger.info(f"Observation expired: child_id={child.id}, name={child.name}")

        db.commit()
        logger.info(f"Observation expiry: {len(expired)} children expired")
    except Exception as e:
        db.rollback()
        logger.error(f"check_observation_expiry failed: {e}", exc_info=True)
    finally:
        db.close()


@distributed_lock("job:check_observation_reminders", timeout=600)
def check_observation_reminders():
    """
    [What] 观察期到期提醒
    [Why] 观察期到期前发送提醒，引导转化
    [How] 查询即将到期的观察期用户，写入消息表
    """
    from backend.domain.child.models import Child
    from backend.common.config_service import ConfigService

    db = _get_db_session()
    try:
        today = date.today()
        remind_days = ConfigService.get_int_list(
            db, "observation_remind_days", [7, 5, 3, 2, 1, 0]
        )

        for days in remind_days:
            target_date = today + timedelta(days=days)
            children = (
                db.query(Child)
                .filter(
                    Child.status == MemberStatus.OBSERVATION,
                    Child.member_expire_time.isnot(None),
                    sql_func.date(Child.member_expire_time) == target_date,
                    Child.is_deleted == 0,
                )
                .all()
            )
            for child in children:
                if days == 0:
                    msg = f"您的孩子 {child.name} 的观察期今天到期，请决定是否升级为正式会员"
                else:
                    msg = f"您的孩子 {child.name} 的观察期将在{days}天后到期"
                _create_message(
                    db,
                    user_id=child.user_id,
                    title="观察期到期提醒",
                    content=msg,
                    msg_type=6,
                    priority=1 if days <= 2 else 0,
                )
                logger.info(f"OBSERVATION_REMIND: child={child.id}, days_left={days}")
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"check_observation_reminders failed: {e}", exc_info=True)
    finally:
        db.close()


@distributed_lock("job:check_activity_reminders", timeout=120)
def check_activity_reminders():
    """活动开始前 3 天提醒 — 每天 10:00 执行"""
    db = _get_db_session()
    try:
        from backend.domain.activity.models import Activity, ActivityEnrollment
        from backend.domain.child.models import Child

        now = datetime.now()
        target_start = now + timedelta(days=3)
        target_end = now + timedelta(days=4)

        activities = (
            db.query(Activity)
            .filter(
                Activity.start_time >= target_start,
                Activity.start_time < target_end,
                Activity.status.in_(
                    [Activity.STATUS_ENROLLING, Activity.STATUS_ENROLL_CLOSED]
                ),
                Activity.is_deleted == 0,
            )
            .all()
        )

        for activity in activities:
            enrollments = (
                db.query(ActivityEnrollment)
                .filter(
                    ActivityEnrollment.activity_id == activity.id,
                    ActivityEnrollment.status == ActivityEnrollment.STATUS_APPROVED,
                    ActivityEnrollment.is_deleted == 0,
                )
                .all()
            )
            for e in enrollments:
                child = db.query(Child).filter(Child.id == e.child_id).first()
                if not child:
                    continue
                _create_message(
                    db,
                    user_id=child.user_id,
                    title="活动开始提醒",
                    content=f"您报名的活动「{activity.title}」将于 3 天后（{activity.start_time.strftime('%m月%d日 %H:%M')}）开始，请做好准备！",
                    msg_type=5,
                    priority=0,
                )
                logger.info(
                    f"ACTIVITY_REMIND: child={child.id}, activity={activity.id}"
                )

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"check_activity_reminders failed: {e}", exc_info=True)
    finally:
        db.close()
