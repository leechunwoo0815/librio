# features/steps/f_group_steps.py
"""F1 迁移/换绑 + F2 毕业 + F5 复活步骤"""

from behave import given, then, when

from backend.domain.child.models import Child
from backend.domain.order.models import Order
from backend.domain.user.models import User
from backend.middleware.admin_auth import create_admin_token


def _admin_headers(context, perms):
    from backend.domain.admin.models import Admin
    from backend.domain.admin.rbac_models import Role, RolePermission

    import uuid

    suffix = uuid.uuid4().hex[:8]
    role = Role(code=f"fg_role_{suffix}", name="FG角色", is_system=False)
    context.db.add(role)
    context.db.flush()
    for code in perms:
        context.db.add(RolePermission(role_id=role.id, permission_code=code))
    context.db.flush()
    admin = Admin(
        username=f"fg_admin_{suffix}",
        password_hash="x",
        name="FG管理员",
        role=0,
        status=1,
        admin_role_id=role.id,
    )
    context.db.add(admin)
    context.db.commit()
    token = create_admin_token(admin_id=admin.id, role=0)
    return {"Authorization": f"Bearer {token}"}


# ==================== F5 复活 ====================


@given("用户有一个已退出的孩子")
def step_exited_child(context):
    child = Child(
        user_id=context.user.id,
        name="已退出",
        age=9,
        grade="四年级",
        status=Child.STATUS_EXITED,
        total_books_finished=5,
    )
    context.db.add(child)
    context.db.commit()
    context.child = child


@when("管理员复活该孩子")
def step_admin_revive(context):
    headers = _admin_headers(context, ["child.edit"])
    context.response = context.client.post(
        f"/admin/api/children/{context.child.id}/revive", headers=headers
    )
    assert context.response.status_code == 200, context.response.text


@then('孩子状态变为"试读用户"')
def step_child_trial(context):
    context.db.refresh(context.child)
    assert context.child.status == Child.STATUS_TRIAL


@then("历史阅读数据保留")
def step_history_kept(context):
    context.db.refresh(context.child)
    assert context.child.total_books_finished == 5


@given("用户有一个已退出且历史付费的孩子")
def step_exited_paid_child(context):
    child = Child(
        user_id=context.user.id,
        name="大宝",
        age=9,
        grade="四年级",
        status=Child.STATUS_EXITED,
    )
    context.db.add(child)
    context.db.commit()
    order = Order(
        order_no="FG-HIST-1",
        user_id=context.user.id,
        child_id=child.id,
        type=Order.TYPE_OBSERVATION,
        amount=500,
        pay_status=Order.PAY_PAID,
    )
    context.db.add(order)
    context.db.commit()


@given("用户还有一个试读孩子")
def step_trial_child(context):
    child = Child(
        user_id=context.user.id,
        name="二宝",
        age=6,
        grade="一年级",
        status=Child.STATUS_TRIAL,
    )
    context.db.add(child)
    context.db.commit()
    context.child = child


@when("用户为试读孩子购买观察期")
def step_buy_observation_for_trial(context):
    context.response = context.client.post(
        "/order/",
        json={"child_id": context.child.id, "type": 2},
        headers=context.headers,
    )


@then("订单金额自动享受9折")
def step_discount_applied(context):
    assert context.response.status_code == 201
    assert float(context.response.json()["amount"]) == 450.0


# ==================== F1 迁移与监护人 ====================


@given("用户有一个孩子且已购观察期")
def step_child_with_order(context):
    child = Child(
        user_id=context.user.id,
        name="小明",
        age=7,
        grade="二年级",
        status=Child.STATUS_OBSERVATION,
    )
    context.db.add(child)
    context.db.commit()
    context.child = child
    order = Order(
        order_no="FG-MIG-1",
        user_id=context.user.id,
        child_id=child.id,
        type=Order.TYPE_OBSERVATION,
        amount=500,
        pay_status=Order.PAY_PAID,
    )
    context.db.add(order)
    context.db.commit()
    context.order = order


@given("用户有一个孩子")
def step_plain_child(context):
    child = Child(
        user_id=context.user.id,
        name="小明",
        age=7,
        grade="二年级",
        status=Child.STATUS_OBSERVATION,
    )
    context.db.add(child)
    context.db.commit()
    context.child = child


@given("存在另一个目标账号")
def step_target_user(context):
    target = User(openid="fg_target", phone="13900001111")
    context.db.add(target)
    context.db.commit()
    context.target_user = target


@when("管理员执行账号迁移")
def step_admin_migrate(context):
    headers = _admin_headers(context, ["user.edit"])
    context.response = context.client.post(
        f"/admin/api/users/{context.user.id}/migrate-account",
        json={"new_user_id": context.target_user.id},
        headers=headers,
    )
    assert context.response.status_code == 200, context.response.text


@then("孩子和订单都归属目标账号")
def step_migrated(context):
    context.db.refresh(context.child)
    context.db.refresh(context.order)
    assert context.child.user_id == context.target_user.id
    assert context.order.user_id == context.target_user.id


@when("管理员未经确认变更监护人")
def step_guardian_unconfirmed(context):
    headers = _admin_headers(context, ["child.edit"])
    context.response = context.client.post(
        f"/admin/api/children/{context.child.id}/change-guardian",
        json={"new_user_id": context.target_user.id, "confirmed": False},
        headers=headers,
    )


@then("系统拒绝变更")
def step_guardian_rejected(context):
    assert context.response.status_code in (400, 409, 422), context.response.text


@when("管理员经确认变更监护人")
def step_guardian_confirmed(context):
    headers = _admin_headers(context, ["child.edit"])
    context.response = context.client.post(
        f"/admin/api/children/{context.child.id}/change-guardian",
        json={"new_user_id": context.target_user.id, "confirmed": True},
        headers=headers,
    )


@then("孩子归属新监护人")
def step_guardian_changed(context):
    assert context.response.status_code == 200, context.response.text
    context.db.refresh(context.child)
    assert context.child.user_id == context.target_user.id


# ==================== F1 手机号换绑 ====================


@when('用户请求换绑手机号"{phone}"并输入正确验证码')
def step_change_phone(context, phone):
    from backend.common.dependencies import get_sms_gateway

    gateway = get_sms_gateway()
    import asyncio

    result = asyncio.run(gateway.send_code(phone))
    code = result.code  # Mock 网关返回明文验证码（仅测试环境）
    context.response = context.client.post(
        "/user/change-phone",
        json={"new_phone": phone, "sms_code": code},
        headers=context.headers,
    )


@then('用户手机号更新为"{phone}"')
def step_phone_updated(context, phone):
    assert context.response.status_code == 200, context.response.text
    context.db.refresh(context.user)
    assert context.user.phone == phone


# ==================== F2 毕业 ====================


@given("用户有一个{age:d}岁的正式会员孩子")
def step_official_child_of_age(context, age):
    child = Child(
        user_id=context.user.id,
        name="大宝",
        age=age,
        grade="初三",
        status=Child.STATUS_OFFICIAL,
    )
    context.db.add(child)
    context.db.commit()
    context.child = child


@when("系统执行毕业检查任务")
def step_run_graduation(context):
    from backend.tasks.scheduler import graduate_children

    graduate_children(context.db)


@then('孩子状态变为"校友"')
def step_child_alumni(context):
    context.db.refresh(context.child)
    assert context.child.status == Child.STATUS_ALUMNI


@then('用户收到"{title}"消息')
def step_user_received_message(context, title):
    from backend.domain.message.models import SystemMessage

    msg = (
        context.db.query(SystemMessage)
        .filter(
            SystemMessage.user_id == context.user.id,
            SystemMessage.title == title,
        )
        .first()
    )
    assert msg is not None, f"未找到标题为「{title}」的消息"
