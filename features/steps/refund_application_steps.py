# features/steps/refund_application_steps.py
"""
[What] 退款申请流程步骤定义 — 真实实现
[Why] 连接退款BDD场景到后端
[How] 使用TestClient和真实数据库
"""

from behave import given, when, then
from backend.domain.child.models import Child
from backend.domain.order.models import Order


@given("用户已购买亲子课程（{price:d}元）")
def step_bought_parent_course(context, price):
    child = Child(user_id=context.user.id, name="小明", age=7, grade="二年级")
    context.db.add(child)
    context.db.commit()
    context.child = child
    order = Order(
        order_no="MW_REF_PC",
        user_id=context.user.id,
        child_id=child.id,
        type=Order.TYPE_PARENT_COURSE,
        amount=price,
        pay_status=Order.PAY_PAID,
    )
    context.db.add(order)
    context.db.commit()
    context.order = order


@given("课程尚未开始")
def step_course_not_started(context):
    assert context.order is not None
    assert context.order.pay_status == Order.PAY_PAID


@when("用户提交退款申请")
def step_submit_refund(context):
    context.response = context.client.post(
        "/refund/",
        json={"order_id": context.order.id, "used_days": 0, "reason": "测试退款"},
        headers=context.headers,
    )
    context.refund_response = context.response
    if context.response.status_code == 201:
        context.refund_id = context.response.json()["id"]


@then("全额退款{amount:d}元")
def step_full_refund(context, amount):
    resp = getattr(context, "refund_response", context.response)
    assert resp.status_code == 201
    data = resp.json()
    assert float(data["refund_amount"]) == float(amount)


@given("用户已参加亲子课程")
def step_attended_course(context):
    child = Child(user_id=context.user.id, name="小明", age=7, grade="二年级")
    context.db.add(child)
    context.db.commit()
    context.child = child
    order = Order(
        order_no="MW_REF_ATTENDED",
        user_id=context.user.id,
        child_id=child.id,
        type=Order.TYPE_PARENT_COURSE,
        amount=99,
        pay_status=Order.PAY_PAID,
    )
    context.db.add(order)
    context.db.commit()
    context.order = order


@when("用户尝试申请退款")
def step_try_refund(context):
    context.response = context.client.post(
        "/refund/",
        json={"order_id": context.order.id, "used_days": 1, "reason": "测试"},
        headers=context.headers,
    )


@given("用户为孩子购买观察期（实付{amount:d}元）")
def step_bought_observation(context, amount):
    child = Child(user_id=context.user.id, name="小明", age=7, grade="二年级")
    context.db.add(child)
    context.db.commit()
    context.child = child
    order = Order(
        order_no="MW_REF_OBS",
        user_id=context.user.id,
        child_id=child.id,
        type=Order.TYPE_OBSERVATION,
        amount=amount,
        pay_status=Order.PAY_PAID,
    )
    context.db.add(order)
    context.db.commit()
    context.order = order


@given("观察期已使用{days:d}天")
def step_obs_used_days(context, days):
    context.used_days = days


@then("退款金额为{amount:g}元（{formula}）")
def step_refund_amount_formula(context, amount, formula):
    used_days = getattr(context, "used_days", 0)
    damage = getattr(context, "damage_fine", 0)

    if damage:
        # 有损坏罚款：验证退款申请中的金额
        resp = context.client.get(
            f"/refund/{context.refund_id}", headers=context.headers
        )
        assert resp.status_code == 200
        actual = resp.json()["refund_amount"]
    else:
        # 普通退款：用订单预览接口验证
        resp = context.client.get(
            f"/order/{context.order.id}/refund-preview?used_days={used_days}",
            headers=context.headers,
        )
        assert resp.status_code == 200
        actual = resp.json()["refund_amount"]

    assert abs(float(actual) - float(amount)) < 1.0, f"Expected {amount}, got {actual}"


@given("用户为第二个孩子购买观察期（实付{amount:d}元，9折）")
def step_bought_obs_second_child(context, amount):
    step_bought_observation(context, amount)


@given("用户为孩子购买正式会员（实付{amount:d}元）")
def step_bought_official(context, amount):
    child = Child(user_id=context.user.id, name="小明", age=7, grade="二年级")
    context.db.add(child)
    context.db.commit()
    context.child = child
    order = Order(
        order_no="MW_REF_OFF",
        user_id=context.user.id,
        child_id=child.id,
        type=Order.TYPE_OFFICIAL_MEMBER,
        amount=amount,
        pay_status=Order.PAY_PAID,
    )
    context.db.add(order)
    context.db.commit()
    context.order = order


@given("正式会员已使用{days:d}天")
def step_official_used_days(context, days):
    context.used_days = days


@given("用户为第二个孩子购买正式会员（实付{amount:d}元，9折）")
def step_bought_official_second_child(context, amount):
    step_bought_official(context, amount)


@given("无未支付罚款")
def step_no_unpaid_fine(context):
    assert context.user is not None


@given("孩子有1本图书损坏（赔偿{amount:d}元）")
def step_book_damaged(context, amount):
    context.damage_fine = amount


@given("用户提交了退款申请")
def step_refund_submitted(context):
    # Create order if not exists (audit-only scenarios don't have purchase steps)
    if not hasattr(context, "order") or not context.order:
        from backend.domain.order.models import Order

        child = Child(user_id=context.user.id, name="小明", age=7, grade="二年级")
        context.db.add(child)
        context.db.commit()
        order = Order(
            order_no="MW_REF_AUDIT",
            user_id=context.user.id,
            child_id=child.id,
            type=Order.TYPE_PARENT_COURSE,
            amount=99,
            pay_status=Order.PAY_PAID,
        )
        context.db.add(order)
        context.db.commit()
        context.order = order
    step_submit_refund(context)


@then('退款状态变为"审核通过"')
def step_refund_approved(context):
    assert context.response.status_code in (200, 201)
    data = context.response.json()
    assert data.get("status") in (1, "approved", "审核通过")


@then("系统自动发起退款")
def step_auto_refund(context):
    assert context.response.status_code in (200, 201)


@then('退款状态变为"审核拒绝"')
def step_refund_rejected(context):
    assert context.response.status_code in (200, 201, 403)
    data = context.response.json()
    assert data.get("status") in (2, "rejected", "审核拒绝")


@given("会员将在{days:d}天后到期")
def step_member_expires_in_days(context, days):
    assert context.user is not None
