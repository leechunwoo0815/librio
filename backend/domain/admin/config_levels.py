# backend/domain/admin/config_levels.py
"""E3 配置三级管控 — 防止运营人员误改关键配置

- 🔒 锁定级（locked）：价格/押金/折扣类，仅超级管理员可改
- ⚠️ 警告级（warning）：上限/罚款/通过率类，修改需显式确认（confirmed=true）
- ✅ 自由级（free）：名称/提醒天数类，运营人员可直接修改
"""

# 🔒 锁定级：仅超管
LOCKED_KEYS = {
    "price_parent_course",
    "price_observation",
    "price_official_member",
    "price_quarterly",
    "price_semi_annual",
    "original_price_parent_course",
    "original_price_official_member",
    "deposit_amount",
    "deposit_partial_refund_amount",
    "renewal_discount",
    "multi_child_discount",
}

# ⚠️ 警告级：改前需确认
WARNING_KEYS = {
    "observation_days",
    "member_days",
    "member_grace_days",
    "refund_free_days",
    "refund_auto_approve_max",
    "borrow_limit",
    "borrow_period_days",
    "overdue_fine_per_day",
    "overdue_grace_days",
    "overdue_fine_cap_ratio",
    "first_overdue_free",
    "lost_book_fine_multiplier",
    "lost_search_days",
    "quiz_pass_rate",
    "quiz_total_questions",
    "quiz_pass_count",
    "quiz_cooldown_minutes",
    "require_teacher_review",
    "submission_auto_approve",
    "submission_min_minutes",
    "daily_checkin_limit",
    "checkin_min_minutes",
    "checkin_min_vocab",
    "bookshelf_limit",
    "vocab_lookup_limit",
    "trial_pages",
    "parent_course_required",
    "upgrade_deduct_enabled",
    "deposit_refund_auto_approve",
    "damage_dual_review",
}

LEVEL_LOCKED = "locked"
LEVEL_WARNING = "warning"
LEVEL_FREE = "free"


def level_of(config_key: str) -> str:
    """配置项管控级别"""
    if config_key in LOCKED_KEYS:
        return LEVEL_LOCKED
    if config_key in WARNING_KEYS:
        return LEVEL_WARNING
    return LEVEL_FREE
