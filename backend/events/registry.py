# backend/events/registry.py
"""事件处理器注册表 — 从各模块 import 并注册到 event_bus"""

import logging

from backend.common.events import event_bus

logger = logging.getLogger(__name__)


def register_event_handlers():
    """注册所有领域事件处理器（在 main.py lifespan 启动时调用）"""
    from backend.events.quiz_handlers import (
        handle_quiz_passed_for_advancement,
        handle_quiz_passed_for_child_stats,
        handle_quiz_passed_for_borrow,
        handle_quiz_passed_for_bookshelf,
        handle_quiz_passed_for_submission,
        handle_quiz_failed_for_logging,
    )
    from backend.events.order_handlers import (
        handle_order_paid_for_child,
        handle_deposit_paid_for_child,
    )
    from backend.events.borrow_handlers import (
        handle_book_borrowed_for_copy_status,
        handle_book_returned_for_copy_status,
        handle_reservation_created_for_stock,
        handle_reservation_cancelled_for_stock,
        handle_reservation_expired_for_stock,
        handle_reservation_fulfilled_for_borrow,
        handle_book_overdue_for_fines,
    )
    from backend.events.misc_handlers import (
        handle_level_advanced_for_certificate,
        handle_checkin_for_child_streak,
    )
    from backend.events.reading_handlers import (
        handle_book_finished_for_advancement,
        handle_session_completed_for_child_stats,
    )

    # ── 测验通过 ──
    event_bus.subscribe("quiz.passed", handle_quiz_passed_for_advancement)
    event_bus.subscribe("quiz.passed", handle_quiz_passed_for_child_stats)
    event_bus.subscribe("quiz.passed", handle_quiz_passed_for_borrow)
    event_bus.subscribe("quiz.passed", handle_quiz_passed_for_bookshelf)
    event_bus.subscribe("quiz.passed", handle_quiz_passed_for_submission)

    # ── 测验未通过 ──
    event_bus.subscribe("quiz.failed", handle_quiz_failed_for_logging)

    # ── 订单支付 ──
    event_bus.subscribe("order.paid", handle_order_paid_for_child)

    # ── 押金支付 ──
    event_bus.subscribe("deposit.paid", handle_deposit_paid_for_child)

    # ── 借书 ──
    event_bus.subscribe("book.borrowed", handle_book_borrowed_for_copy_status)

    # ── 还书 ──
    event_bus.subscribe("book.returned", handle_book_returned_for_copy_status)

    # ── 晋级 ──
    event_bus.subscribe("level.advanced", handle_level_advanced_for_certificate)

    # ── 预约创建 ──
    event_bus.subscribe("reservation.created", handle_reservation_created_for_stock)

    # ── 预约取消 ──
    event_bus.subscribe("reservation.cancelled", handle_reservation_cancelled_for_stock)

    # ── 预约过期 ──
    event_bus.subscribe("reservation.expired", handle_reservation_expired_for_stock)

    # ── 预约取书 ──
    event_bus.subscribe(
        "reservation.fulfilled", handle_reservation_fulfilled_for_borrow
    )

    # ── 打卡 ──
    event_bus.subscribe("reading.checkin", handle_checkin_for_child_streak)

    # ── 图书逾期 ──
    event_bus.subscribe("book.overdue", handle_book_overdue_for_fines)

    # ── 阅读读完一本书 ──
    event_bus.subscribe("reading.book_finished", handle_book_finished_for_advancement)

    # ── 阅读会话结束 ──
    event_bus.subscribe(
        "reading.session_completed", handle_session_completed_for_child_stats
    )

    logger.info("Event handlers registered: 14 event types, 18 handlers")
