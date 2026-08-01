# features/steps/member_expiry_steps.py
"""会员生命周期定时任务步骤 — T5.4 二批（会员到期/观察期节点）"""

from datetime import datetime, timedelta

from behave import given, then, when

from backend.common.types import MemberStatus
from backend.domain.child.models import Child


def _create_child(context, status, days_offset, name="小明"):
    """创建指定状态、到期日偏移的孩子"""
    context.db.query(Child).filter(
        Child.user_id == context.user.id, Child.is_deleted == 0
    ).update({Child.status: MemberStatus.EXPIRED})
    now = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
    child = Child(
        user_id=context.user.id,
        name=name,
        age=7,
        grade="二年级",
        status=status,
        member_start_time=now - timedelta(days=50),  # A3：观察期45天，起始须>45天前
        member_expire_time=now + timedelta(days=days_offset),
    )
    context.db.add(child)
    context.db.commit()
    context.child = child
    return child


# ==================== Given ====================


@given("用户的孩子是正式会员且 {days:d} 天后到期")
def step_official_child_expire_in(context, days):
    _create_child(context, MemberStatus.OFFICIAL, days)


@given("用户的孩子是观察期会员且 {days:d} 天后到期")
def step_observation_child_expire_in(context, days):
    _create_child(context, MemberStatus.OBSERVATION, days)


@given("用户的孩子是观察期会员且已过期 {days:d} 天")
def step_observation_child_expired(context, days):
    _create_child(context, MemberStatus.OBSERVATION, -days)


# ==================== When ====================


@when("会员到期检查任务执行")
def step_run_member_expiry(context):
    from backend.tasks.scheduler import check_member_expiry

    check_member_expiry(context.db)


@when("观察期提醒任务执行")
def step_run_observation_reminders(context):
    from backend.tasks.scheduler import check_observation_reminders

    check_observation_reminders(context.db)


@when("观察期到期检查任务执行")
def step_run_observation_expiry(context):
    from backend.tasks.scheduler import check_observation_expiry

    check_observation_expiry(context.db)


# ==================== Then ====================


def _has_message(context, title):
    from backend.domain.message.models import SystemMessage

    return (
        context.db.query(SystemMessage)
        .filter(
            SystemMessage.user_id == context.user.id,
            SystemMessage.title == title,
            SystemMessage.is_deleted == 0,
        )
        .count()
        > 0
    )


@then('用户收到标题为"{title}"的消息')
def step_has_message(context, title):
    assert _has_message(context, title), f"未找到标题为「{title}」的消息"


@then('用户没有收到标题为"{title}"的消息')
def step_no_message(context, title):
    assert not _has_message(context, title), f"不应出现标题为「{title}」的消息"


@then('孩子状态变为"已过期"')
def step_child_expired(context):
    context.db.refresh(context.child)
    assert context.child.status == MemberStatus.EXPIRED, (
        f"期望 EXPIRED，实际 {context.child.status}"
    )


@then('孩子状态仍为"观察期"')
def step_child_still_observation(context):
    context.db.refresh(context.child)
    assert context.child.status == MemberStatus.OBSERVATION, (
        f"期望 OBSERVATION，实际 {context.child.status}"
    )


@then("系统为孩子生成观察期报告")
def step_observation_report_generated(context):
    from backend.domain.report.models import ObservationReport

    report = (
        context.db.query(ObservationReport)
        .filter(
            ObservationReport.child_id == context.child.id,
            ObservationReport.is_deleted == 0,
        )
        .first()
    )
    assert report is not None, "未生成观察期报告"
