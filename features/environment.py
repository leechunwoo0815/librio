# features/environment.py
"""
[What] Behave测试环境配置
[Why] 提供真实FastAPI TestClient，覆盖数据库为SQLite内存库
[How] 使用app.dependency_overrides替换get_db
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 测试环境强制使用 Mock 网关
os.environ["MOCK_PAYMENT"] = "true"
os.environ["MOCK_SMS"] = "true"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db

# 注册所有 ORM 模型（让 Base.metadata 知道所有表）
from backend.domain.user.models import *  # noqa: F401,F403
from backend.domain.child.models import *  # noqa: F401,F403
from backend.domain.book.models import *  # noqa: F401,F403
from backend.domain.bookshelf.models import *  # noqa: F401,F403
from backend.domain.borrow.models import *  # noqa: F401,F403
from backend.domain.deposit.models import *  # noqa: F401,F403
from backend.domain.reservation.models import *  # noqa: F401,F403
from backend.domain.reading.models import *  # noqa: F401,F403
from backend.domain.vocabulary.models import *  # noqa: F401,F403
from backend.domain.advancement.models import *  # noqa: F401,F403
from backend.domain.quiz_question.models import *  # noqa: F401,F403
from backend.domain.order.models import *  # noqa: F401,F403
from backend.domain.refund.models import *  # noqa: F401,F403
from backend.domain.activity.models import *  # noqa: F401,F403
from backend.domain.report.models import *  # noqa: F401,F403
from backend.domain.certificate.models import *  # noqa: F401,F403
from backend.domain.admin.models import *  # noqa: F401,F403
from backend.main import app
from backend.bootstrap import register_event_handlers


def before_all(context):
    context.config.setup_logging()
    register_event_handlers()


def before_scenario(context, scenario):
    """
    [What] 每个场景前创建独立SQLite数据库
    [Why] 使用StaticPool保持单连接，避免:memory:的per-connection问题
    [How] 覆盖FastAPI的get_db依赖
    """
    # 使用StaticPool确保所有连接共享同一个:memory:数据库
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    context.engine = engine
    context.db = Session()

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    from fastapi.testclient import TestClient

    context.client = TestClient(app)

    context.user = None
    context.child = None
    context.book = None
    context.response = None
    context.headers = {}


def after_scenario(context, scenario):
    context.db.rollback()
    context.db.close()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=context.engine)
