import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from decimal import Decimal

from backend.database import get_session
from backend.domain.advancement.models import Level

logger = logging.getLogger(__name__)

LEVELS = [
    ("A", 1, 10, 20, "🌱", "阅读入门"),
    ("B", 2, 10, 20, "🌿", "阅读初学"),
    ("C", 3, 10, 20, "🍀", "阅读进阶"),
    ("D", 4, 15, 20, "🌳", "阅读稳固"),
    ("E", 5, 15, 20, "🌲", "阅读成长"),
    ("F", 6, 15, 20, "🌻", "阅读绽放"),
    ("G", 7, 20, 20, "🌼", "阅读自信"),
    ("H", 8, 20, 20, "⭐", "阅读之星"),
    ("I", 9, 20, 20, "🌟", "阅读光芒"),
    ("J", 10, 25, 20, "💎", "阅读钻石"),
    ("K", 11, 25, 20, "🏆", "阅读冠军"),
    ("L", 12, 25, 20, "🎓", "阅读学者"),
    ("M", 13, 30, 20, "📚", "阅读书虫"),
    ("N", 14, 30, 20, "🦉", "阅读智者"),
    ("O", 15, 30, 20, "🦅", "阅读翱翔"),
    ("P", 16, 35, 20, "🚀", "阅读火箭"),
    ("Q", 17, 35, 20, "🌈", "阅读彩虹"),
    ("R", 18, 35, 20, "⚡", "阅读闪电"),
    ("S", 19, 40, 20, "🔥", "阅读火焰"),
    ("T", 20, 40, 20, "💫", "阅读星光"),
    ("U", 21, 40, 20, "🌍", "阅读世界"),
    ("V", 22, 45, 20, "📖", "阅读大师"),
    ("W", 23, 45, 20, "🏅", "阅读精英"),
    ("X", 24, 50, 20, "🎯", "阅读精准"),
    ("Y", 25, 50, 20, "👑", "阅读王者"),
    ("Z", 26, 50, 20, "🏆", "阅读传奇"),
]


def seed_levels():
    db = get_session()()
    try:
        existing = db.query(Level).count()
        if existing > 0:
            logger.info(f"已存在 {existing} 个级别，跳过")
            return
        for name, sort, books, borrow, emoji, _desc in LEVELS:
            level = Level(
                name=name,
                sort_order=sort,
                required_books=books,
                max_borrow_count=borrow,
                badge_emoji=emoji,
                required_quiz_pass_rate=Decimal("0.80"),
            )
            db.add(level)
        db.commit()
        logger.info(f"成功创建 {len(LEVELS)} 个 A-Z 级别")
    except Exception as e:
        logger.info(f"错误: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_levels()
