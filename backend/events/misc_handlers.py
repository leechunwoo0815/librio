# backend/events/misc_handlers.py
"""其他事件处理器（打卡、晋级证书）"""

import logging
from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository

logger = logging.getLogger(__name__)


def handle_level_advanced_for_certificate(event, db: Session):
    """晋级 → 生成晋级证书"""
    from backend.domain.certificate.service import CertificateService

    service = CertificateService(db)
    service.create_level_certificate(event.child_id, event.to_level)


def handle_checkin_for_child_streak(event, db: Session):
    """打卡 → 更新连续打卡天数（自然日口径，PRD §10.1）

    同日 4 类型打卡各发一次 CheckInEvent，但 streak 按"有打卡的自然日"计——
    每次事件都从今天向前重算连续段，结果幂等（同日多次打卡不叠加）；
    断签时 current 重置为 1，longest 只升不降。此前实现每次 +1，
    同日 4 类型会 +4 且断签不重置，展示端/观察期报告读到错误中间值
    （对账任务凌晨 3:45 才修正）。
    """
    from backend.domain.child.models import Child
    from backend.domain.reading.models import CheckIn
    from datetime import date, datetime, timedelta

    from sqlalchemy import func

    today = date.today()
    rows = (
        db.query(func.date(CheckIn.check_date))
        .filter(CheckIn.child_id == event.child_id, CheckIn.is_deleted == 0)
        .distinct()
        .all()
    )
    dates: set[date] = set()
    for (d,) in rows:
        if d is None:
            continue
        if isinstance(d, str):
            d = date.fromisoformat(d)
        elif isinstance(d, datetime):
            d = d.date()
        dates.add(d)
    dates.add(today)  # 本次打卡必然已落库；防御性兜底

    child_repo = BaseRepository(db, Child)
    child = (
        db.query(Child)
        .filter(Child.id == event.child_id, Child.is_deleted == 0)
        .with_for_update()
        .first()
    )
    if child:
        current = 0
        cursor = today
        while cursor in dates:
            current += 1
            cursor -= timedelta(days=1)
        longest = run = 1 if dates else 0
        prev = None
        for d in sorted(dates):
            if prev is not None and (d - prev).days == 1:
                run += 1
                longest = max(longest, run)
            else:
                run = 1
            prev = d
        child.current_streak_days = current
        if longest > (child.longest_streak_days or 0):
            child.longest_streak_days = longest
        child_repo.update(child)
