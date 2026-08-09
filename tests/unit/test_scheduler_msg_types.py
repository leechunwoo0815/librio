# tests/unit/test_scheduler_msg_types.py
"""scheduler 消息类型（msg_type）断言 — R2 防回归

权威枚举（backend/domain/message/models.py SystemMessage.msg_type 注释，
与小程序 messages.js / 管理端 message_manage.js 映射一致）：
1=系统通知 2=活动通知 3=借阅通知 4=老师消息 5=阅读提醒

历史 bug：观察期提醒 msg_type=6、退款失败 msg_type=7 越界（前端兜底为系统），
借阅到期/逾期提醒错挂活动/阅读分类，活动通知错挂阅读分类。
"""

from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def _disable_locks(monkeypatch):
    """禁用 distributed_lock 装饰器"""
    import functools
    from backend.tasks import scheduler

    def _noop_decorator(*args, **kwargs):
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*a, **kw):
                return func(*a, **kw)

            return wrapper

        return decorator

    monkeypatch.setattr(scheduler, "distributed_lock", _noop_decorator)


@pytest.fixture
def _stub_config(monkeypatch):
    """stub ConfigService.get_int_list 返回默认提醒天数"""
    from backend.common import config_service

    def _fake_get_int_list(db, key, default):
        return default

    monkeypatch.setattr(
        config_service.ConfigService, "get_int_list", _fake_get_int_list
    )


def _mock_db_with_children(children):
    """构造 query(Child).filter(...).all() 返回指定孩子的 mock session"""
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = children
    return db


class TestMemberExpiryMsgType:
    """check_member_expiry：会员续费提醒 = 1（系统通知）"""

    def test_msg_type_is_system(self, _disable_locks, _stub_config):
        from backend.tasks import scheduler

        today = date.today()
        child = MagicMock()
        child.id = 10
        child.user_id = 100
        child.name = "小明"
        child.member_expire_time = datetime.combine(
            today + timedelta(days=3), datetime.min.time()
        )
        db = _mock_db_with_children([child])

        with patch.object(scheduler, "_create_message") as mock_create:
            scheduler.check_member_expiry(db=db)
            assert mock_create.call_count == 1
            call = mock_create.call_args
            assert call.kwargs["title"] == "会员续费提醒"
            assert call.kwargs["msg_type"] == 1


class TestObservationRemindersMsgType:
    """check_observation_reminders：观察期到期提醒 = 1（系统通知），越界 6 已修"""

    def test_msg_type_is_system(self, _disable_locks, _stub_config):
        from backend.tasks import scheduler

        today = date.today()
        child = MagicMock()
        child.id = 10
        child.user_id = 100
        child.name = "小明"
        child.member_expire_time = datetime.combine(
            today + timedelta(days=3), datetime.min.time()
        )
        # F-015 终审：一次范围查询替代逐日查询，仅 days=3 命中
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [child]

        with patch.object(scheduler, "_create_message") as mock_create:
            scheduler.check_observation_reminders(db=db)
            assert mock_create.call_count == 1
            # 守护：范围查询只执行一次 all（逐日实现会调 6 次 → 本断言红）
            assert db.query.return_value.filter.return_value.all.call_count == 1
            call = mock_create.call_args
            assert call.kwargs["title"] == "观察期到期提醒"
            assert call.kwargs["msg_type"] == 1


class TestAlertStaleRefunds:
    """alert_stale_refunds：退款 7 天未到账告警（P3 补缺）"""

    def test_stale_refund_creates_alert(self, monkeypatch):
        from backend.tasks import scheduler
        from backend.domain.refund.models import RefundApplication

        refund = MagicMock()
        refund.id = 7
        refund.user_id = 100
        refund.order_id = 55
        refund.refund_amount = 500
        refund.review_time = datetime.now() - timedelta(days=8)

        db = MagicMock()

        def _fake_query(model):
            q = MagicMock()
            if model is RefundApplication:
                rows = [refund]
            else:
                rows = []  # DepositRecord 等其余查询返回空（F55 押金巡检分支）
            q.filter.return_value.all.return_value = rows
            return q

        db.query.side_effect = _fake_query
        monkeypatch.setattr(scheduler, "_get_db_session", lambda: db)

        with patch.object(scheduler, "_create_message") as mock_create:
            scheduler.alert_stale_refunds()
            assert mock_create.call_count == 1
            call = mock_create.call_args
            assert call.kwargs["title"] == "退款超时告警（运营）"  # F72：告警发运营
            assert call.kwargs["user_id"] == 0
            assert call.kwargs["msg_type"] == 1
            assert call.kwargs["priority"] == 2
            assert "#7" in call.kwargs["content"]

    def test_no_stale_refund_no_message(self, monkeypatch):
        from backend.tasks import scheduler

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        monkeypatch.setattr(scheduler, "_get_db_session", lambda: db)

        with patch.object(scheduler, "_create_message") as mock_create:
            scheduler.alert_stale_refunds()
            mock_create.assert_not_called()
