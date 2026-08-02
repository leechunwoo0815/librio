# features/steps/config_management_steps.py
"""E3 配置三级管控 / E4 轻量活动 / E6 运营报表 / E2 SLA 巡检步骤"""

from datetime import datetime, timedelta

from behave import given, then, when

from backend.domain.child.models import Child
from backend.middleware.admin_auth import create_admin_token


def _make_admin(context, username, perms, role=0):
    """创建带指定权限的管理员并返回 headers"""
    from backend.domain.admin.models import Admin
    from backend.domain.admin.rbac_models import Role, RolePermission

    r = Role(code=f"role_{username}", name=f"角色{username}", is_system=False)
    context.db.add(r)
    context.db.flush()
    for code in perms:
        context.db.add(RolePermission(role_id=r.id, permission_code=code))
    context.db.flush()
    admin = Admin(
        username=username,
        password_hash="x",
        name=username,
        role=role,
        status=1,
        admin_role_id=r.id,
    )
    context.db.add(admin)
    context.db.commit()
    token = create_admin_token(admin_id=admin.id, role=role)
    return {"Authorization": f"Bearer {token}"}


# ==================== E3 ====================


@given("存在非超管管理员（config.edit权限）")
def step_admin_config_edit(context):
    context.admin_headers = _make_admin(
        context, "cfg_admin", ["config.edit", "config.view"], role=1
    )


@given("存在非超管管理员（dashboard.view权限）")
def step_admin_dashboard_view(context):
    context.admin_headers = _make_admin(
        context, "dash_admin", ["dashboard.view"], role=1
    )


@when('该管理员修改配置"{key}"为"{value}"')
def step_admin_set_config(context, key, value):
    context.response = context.client.put(
        f"/admin/api/config/{key}?value={value}",
        headers=context.admin_headers,
    )


@when('该管理员不带确认修改配置"{key}"为"{value}"')
def step_admin_set_warning_unconfirmed(context, key, value):
    context.response = context.client.put(
        f"/admin/api/config/{key}?value={value}",
        headers=context.admin_headers,
    )


@when('该管理员带确认修改配置"{key}"为"{value}"')
def step_admin_set_warning_confirmed(context, key, value):
    context.response = context.client.put(
        f"/admin/api/config/{key}?value={value}&confirmed=true",
        headers=context.admin_headers,
    )


@then("系统返回409冲突")
def step_409(context):
    assert context.response.status_code == 409, context.response.text


@then("配置更新成功")
def step_config_updated(context):
    assert context.response.status_code == 200, context.response.text


@when("该管理员查看配置列表")
def step_admin_list_configs(context):
    context.response = context.client.get(
        "/admin/api/config", headers=context.admin_headers
    )
    assert context.response.status_code == 200
    context.config_items = context.response.json()["items"]


@then('配置"{key}"级别为"{level}"')
def step_config_level(context, key, level):
    assert context.config_items[key]["level"] == level


# ==================== E4 ====================


@given('管理员创建轻量活动"{title}"')
def step_create_light_activity(context, title):
    from backend.domain.activity.models import Activity

    activity = Activity(
        title=title,
        type=1,
        is_free=1,
        is_light=1,
        start_time=datetime.now() + timedelta(days=3),
        end_time=datetime.now() + timedelta(days=3, hours=2),
        max_participants=20,
        status=Activity.STATUS_ENROLLING,
    )
    context.db.add(activity)
    context.db.commit()
    context.activity = activity


@when("用户报名该活动")
def step_enroll_activity(context):
    context.response = context.client.post(
        "/activity/enroll",
        json={"activity_id": context.activity.id, "child_id": context.child.id},
        headers=context.headers,
    )


@then('报名状态直接为"已通过"')
def step_enrollment_auto_approved(context):
    assert context.response.status_code in (200, 201), context.response.text
    from backend.domain.activity.models import ActivityEnrollment

    enrollment = (
        context.db.query(ActivityEnrollment)
        .filter(
            ActivityEnrollment.activity_id == context.activity.id,
            ActivityEnrollment.child_id == context.child.id,
        )
        .first()
    )
    assert enrollment is not None
    assert enrollment.status == ActivityEnrollment.STATUS_APPROVED


# ==================== E6 ====================


@when("该管理员查看运营报表")
def step_view_ops(context):
    context.response = context.client.get(
        "/admin/api/dashboard/ops", headers=context.admin_headers
    )
    assert context.response.status_code == 200, context.response.text
    context.ops = context.response.json()


@then("返回今日借还量")
def step_ops_borrows(context):
    assert "today_borrows" in context.ops and "today_returns" in context.ops


@then("返回押金池总额")
def step_ops_deposit(context):
    assert "deposit_pool_total" in context.ops


@then("返回转化漏斗")
def step_ops_funnel(context):
    funnel = context.ops["conversion_funnel"]
    assert "parent_course" in funnel and "observation" in funnel


# ==================== E2 ====================


@given("存在一笔25小时前提交的待审核退款")
def step_stale_refund(context):
    from backend.domain.order.models import Order
    from backend.domain.refund.models import RefundApplication

    child = (
        context.child
        if context.child
        else Child(user_id=context.user.id, name="小明", age=7, grade="二年级")
    )
    context.db.add(child)
    context.db.commit()
    context.child = child
    order = Order(
        order_no="SLA-TEST-1",
        user_id=context.user.id,
        child_id=child.id,
        type=Order.TYPE_OFFICIAL_MEMBER,
        amount=5400,
        pay_status=Order.PAY_PAID,
        pay_time=datetime.now() - timedelta(days=30),
    )
    context.db.add(order)
    context.db.commit()
    refund = RefundApplication(
        order_id=order.id,
        user_id=context.user.id,
        child_id=child.id,
        refund_amount=5059.73,
        used_days=30,
        reason="SLA测试",
        status=RefundApplication.STATUS_PENDING,
        create_time=datetime.now() - timedelta(hours=25),
    )
    context.db.add(refund)
    context.db.commit()


@when("系统执行审核SLA巡检")
def step_run_sla(context):
    from backend.tasks.scheduler import audit_sla_escalation

    audit_sla_escalation(context.db)


@then('生成"{title}"管理端告警')
def step_sla_alert_created(context, title):
    from backend.domain.message.models import SystemMessage

    msg = (
        context.db.query(SystemMessage)
        .filter(SystemMessage.user_id == 0, SystemMessage.title == title)
        .first()
    )
    assert msg is not None, "未生成 SLA 超时告警"
    assert "退款申请" in msg.content
