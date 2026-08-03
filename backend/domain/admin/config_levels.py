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
    "review_sla_hours",
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
    "data_retention_finance_years",
    "data_retention_behavior_years",
    "data_retention_message_years",
    "voice_retention_months",
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


# ── 数值范围校验（P2-4）：key → (min, max)，int 与数值型 string 配置通用 ──
# 防止运营误填（如 borrow_limit=200 借空库存、quiz_pass_rate=0.5 晋级体系崩溃）
CONFIG_RANGES: dict[str, tuple[float, float]] = {
    "trial_pages": (1, 100),
    "vocab_lookup_limit": (1, 100),
    "observation_days": (1, 730),
    "member_days": (1, 1095),
    "member_grace_days": (0, 90),
    "renewal_discount": (0.01, 1),
    "multi_child_discount": (0.01, 1),
    "refund_free_days": (0, 30),
    "borrow_limit": (1, 50),
    "borrow_period_days": (1, 90),
    "overdue_fine_per_day": (0, 100),
    "overdue_grace_days": (0, 15),
    "overdue_fine_cap_ratio": (0, 1),
    "lost_book_fine_multiplier": (0, 3),
    "lost_search_days": (1, 30),
    "deposit_amount": (1, 100000),
    "deposit_partial_refund_amount": (0, 100000),
    "deposit_partial_refund_books": (1, 100),
    "refund_auto_approve_max": (0, 10000),
    "review_sla_hours": (1, 168),
    "reservation_expire_hours": (1, 720),
    "reservation_remind_hours": (1, 168),
    "default_required_books": (1, 50),
    "quiz_pass_rate": (0.01, 1),
    "quiz_total_questions": (1, 20),
    "quiz_pass_count": (1, 20),
    "quiz_cooldown_minutes": (5, 1440),
    "quiz_low_level_max_sort": (1, 26),
    "quiz_low_level_questions": (1, 10),
    "quiz_low_level_pass_count": (1, 10),
    "submission_min_minutes": (1, 120),
    "checkin_min_minutes": (1, 120),
    "checkin_min_vocab": (0, 50),
    "daily_checkin_limit": (1, 10),
    "bookshelf_limit": (0, 500),
    "order_expire_minutes": (5, 1440),
    "activity_cancel_hours": (0, 168),
    "admin_token_expire_hours": (1, 72),
    "data_retention_finance_years": (1, 10),
    "data_retention_behavior_years": (1, 10),
    "data_retention_message_years": (1, 10),
    "voice_retention_months": (1, 24),
}


def validate_config_value(config_key: str, value: str) -> str | None:
    """校验配置值数值范围（P2-4）。合法返回 None，非法返回错误消息。"""
    rng = CONFIG_RANGES.get(config_key)
    if not rng:
        return None
    try:
        num = float(str(value).strip())
    except (TypeError, ValueError):
        return f"配置 {config_key} 必须为数值，当前值: {value!r}"
    lo, hi = rng
    if not lo <= num <= hi:
        return f"配置 {config_key}={value} 超出允许范围 [{lo:g}, {hi:g}]"
    return None
