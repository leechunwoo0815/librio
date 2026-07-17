# backend/seeds/seed_admin.py
"""创建管理员种子数据"""

import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.database import get_session, Base, _get_engine
from backend.domain.admin.models import Admin
from backend.utils.password import hash_password

logger = logging.getLogger(__name__)


def seed():
    engine = _get_engine()
    Base.metadata.create_all(bind=engine)
    db = get_session()()
    try:
        # 检查是否已有管理员
        existing = db.query(Admin).filter(Admin.username == "admin").first()
        if existing:
            logger.info(f"管理员已存在: id={existing.id}, username={existing.username}")
            return

        admin = Admin(
            username="admin",
            name="超级管理员",
            role=0,  # ROLE_ADMIN
            status=1,
        )
        default_password = os.environ.get("ADMIN_PASSWORD")
        if not default_password:
            logger.info("❌ 必须设置 ADMIN_PASSWORD 环境变量才能创建管理员")
            logger.info(
                "   示例: ADMIN_PASSWORD=your-strong-password python -m backend.seeds.seed_admin"
            )
            return
        admin.password_hash = hash_password(default_password)
        db.add(admin)
        db.commit()
        logger.info(f"管理员创建成功: id={admin.id}, username=admin")
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed()
