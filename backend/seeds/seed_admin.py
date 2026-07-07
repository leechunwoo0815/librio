# backend/seeds/seed_admin.py
"""创建管理员种子数据"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.database import get_session, Base, _get_engine
from backend.domain.admin.models import Admin


def seed():
    engine = _get_engine()
    Base.metadata.create_all(bind=engine)
    db = get_session()()

    # 检查是否已有管理员
    existing = db.query(Admin).filter(Admin.username == "admin").first()
    if existing:
        print(f"管理员已存在: id={existing.id}, username={existing.username}")
        db.close()
        return

    admin = Admin(
        username="admin",
        name="超级管理员",
        role=0,  # ROLE_ADMIN
        status=1,
    )
    default_password = os.environ.get("ADMIN_PASSWORD")
    if not default_password:
        print("❌ 必须设置 ADMIN_PASSWORD 环境变量才能创建管理员")
        print(
            "   示例: ADMIN_PASSWORD=your-strong-password python -m backend.seeds.seed_admin"
        )
        db.close()
        return
    admin.set_password(default_password)
    db.add(admin)
    db.commit()
    print(f"管理员创建成功: id={admin.id}, username=admin")
    db.close()


if __name__ == "__main__":
    seed()
