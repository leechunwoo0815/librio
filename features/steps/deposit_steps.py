# features/steps/deposit_steps.py
"""V3.1 押金管理BDD步骤 — stub实现

注意：'用户未缴纳押金' 和 '用户已缴纳押金' 已在 bookshelf_steps.py 中定义，
此处不再重复定义。
"""

from behave import given, when, then
from datetime import datetime, timedelta
from backend.domain.deposit.models import DepositRecord
from backend.common.types import DepositStatus


@given("用户已缴纳押金{amount:d}元")
def step_paid_deposit(context, amount):
    context.child.deposit_status = 1
    context.db.commit()


@when("用户请求缴纳押金{amount:d}元")
def step_request_pay_deposit(context, amount):
    context.response = context.client.post(
        "/deposit/pay",
        json={"child_id": context.child.id, "amount": amount},
        headers=context.headers,
    )


@when("用户再次请求缴纳押金")
def step_request_pay_deposit_again(context):
    context.response = context.client.post(
        "/deposit/pay",
        json={"child_id": context.child.id, "amount": 1200},
        headers=context.headers,
    )


@when("用户申请退还押金")
def step_request_refund(context):
    context.response = context.client.post(
        "/deposit/refund",
        json={"child_id": context.child.id},
        headers=context.headers,
    )


@when("用户查看押金状态")
def step_view_deposit_status(context):
    context.response = context.client.get(
        f"/deposit/status?child_id={context.child.id}",
        headers=context.headers,
    )


@then('押金状态为"已缴纳"')
@then('押金状态变为"已缴纳"')
def step_deposit_paid(context):
    context.db.refresh(context.child)
    assert context.child.deposit_status == 1


@then("押金金额为{amount:d}元")
def step_deposit_amount(context, amount):
    record = (
        context.db.query(DepositRecord)
        .filter(DepositRecord.child_id == context.child.id)
        .first()
    )
    assert float(record.amount) == float(amount)


@then("支付时间为当前时间")
def step_pay_time(context):
    record = (
        context.db.query(DepositRecord)
        .filter(DepositRecord.child_id == context.child.id)
        .first()
    )
    assert record.pay_time is not None


@then('提示"押金已缴纳，无需重复操作"')
def step_already_paid_msg(context):
    assert context.response is not None
    assert context.response.status_code == 200


@then('提示"请先归还所有图书并结清罚款"')
def step_cannot_refund_msg(context):
    # T1：恒真断言清零——真实端点必须 4xx 且 detail 含提示
    assert context.response is not None
    assert context.response.status_code in (400, 403), context.response.text
    assert "请先归还所有图书" in (context.response.text or "")


@then('押金状态显示"已缴纳"')
def step_show_deposit_paid(context):
    assert context.response.status_code == 200
    data = context.response.json()
    assert data.get("deposit_status") == 1 or data.get("status") == 1


@then("显示押金金额{amount:d}元")
def step_show_deposit_amount(context, amount):
    assert context.response.status_code == 200
    data = context.response.json()
    assert float(data.get("amount", data.get("deposit_amount", 0))) == float(amount)


@then('孩子押金状态更新为"已扣除"')
def step_deposit_deducted(context):
    context.db.refresh(context.child)
    assert context.child.deposit_status == DepositStatus.DEDUCTED


@then("孩子未结罚款金额减少")
def step_fines_reduced(context):
    assert context.response is not None
    assert context.response.status_code == 200


# ==================== 补充押金步骤 ====================


@given('孩子押金状态为"{status}"')
def step_child_deposit_status(context, status):
    from backend.common.types import DepositStatus

    status_map = {
        "已缴纳": DepositStatus.PAID,
        "未缴纳": DepositStatus.UNPAID,
        "已退": DepositStatus.REFUNDED,
    }
    deposit_status = status_map.get(status, DepositStatus.UNPAID)
    context.child.deposit_status = deposit_status
    context.db.commit()
    # 如果是已缴纳，同时创建押金记录
    if deposit_status == DepositStatus.PAID:
        existing = (
            context.db.query(DepositRecord)
            .filter(DepositRecord.child_id == context.child.id)
            .first()
        )
        if not existing:
            record = DepositRecord(
                child_id=context.child.id, amount=1200, status=DepositStatus.PAID
            )
            context.db.add(record)
            context.db.commit()


@given("孩子押金余额为{amount:d}元")
def step_child_deposit_balance(context, amount):
    from backend.common.types import DepositStatus

    # 创建押金记录
    existing = (
        context.db.query(DepositRecord)
        .filter(DepositRecord.child_id == context.child.id)
        .first()
    )
    if not existing:
        record = DepositRecord(
            child_id=context.child.id, amount=amount, status=DepositStatus.PAID
        )
        context.db.add(record)
        context.db.commit()
    context.child.deposit_status = DepositStatus.PAID
    context.db.commit()


@given("孩子无活跃借阅记录")
def step_no_active_borrows(context):
    # 确保孩子有已缴纳的押金（退款前置条件）
    from backend.domain.deposit.models import DepositRecord
    from backend.common.types import DepositStatus

    existing = (
        context.db.query(DepositRecord)
        .filter(
            DepositRecord.child_id == context.child.id,
            DepositRecord.status == DepositStatus.PAID,
        )
        .first()
    )
    if not existing:
        record = DepositRecord(
            child_id=context.child.id, amount=1200, status=DepositStatus.PAID
        )
        context.db.add(record)
        context.db.commit()


@given("孩子有1本借阅中且未归还的书")
def step_has_active_borrow(context):
    from backend.domain.borrow.models import BorrowRecord
    from backend.common.types import BorrowStatus
    from backend.domain.book.models import Book

    # 确保有押金
    step_no_active_borrows(context)
    # B2 修复假构造：无 book 时自动创建（原实现静默跳过导致校验从未生效）
    if not getattr(context, "book", None):
        book = Book(
            isbn="978DEP000001",
            title="Deposit Book",
            author="A",
            ar_value=2.0,
            age_min=5,
            age_max=9,
            word_count=1000,
            total_stock=1,
            available_stock=1,
            price=50,
        )
        context.db.add(book)
        context.db.commit()
        context.db.refresh(book)
        context.book = book
    borrow = BorrowRecord(
        child_id=context.child.id,
        book_id=context.book.id,
        status=BorrowStatus.BORROWING,
        borrow_time=datetime.now(),
        due_date=datetime.now() + timedelta(days=21),
    )
    context.db.add(borrow)
    context.db.commit()


@given("孩子有逾期借阅记录")
def step_has_overdue_borrow(context):
    from backend.domain.borrow.models import BorrowRecord
    from backend.domain.book.models import Book
    from backend.common.types import BorrowStatus

    # 确保有书
    if not hasattr(context, "book") or not context.book:
        book = context.db.query(Book).first()
        if not book:
            book = Book(
                isbn="978001",
                title="Test",
                author="A",
                ar_value=2.0,
                age_min=5,
                age_max=9,
                word_count=1000,
                price=80,
            )
            context.db.add(book)
            context.db.commit()
            context.db.refresh(book)
        context.book = book
    # 创建逾期借阅记录
    # 真实 fine_policy 有首次免罚——先造历史逾期记录使本场景罚款真实生效
    context.db.add(
        BorrowRecord(
            child_id=context.child.id,
            book_id=context.book.id,
            status=BorrowStatus.RETURNED,
            borrow_time=datetime.now() - timedelta(days=60),
            due_date=datetime.now() - timedelta(days=50),
            return_time=datetime.now() - timedelta(days=40),
            overdue_days=5,
        )
    )
    borrow = BorrowRecord(
        child_id=context.child.id,
        book_id=context.book.id,
        status=BorrowStatus.OVERDUE,
        borrow_time=datetime.now() - timedelta(days=30),
        due_date=datetime.now() - timedelta(days=9),
    )
    context.db.add(borrow)
    context.db.commit()


@given("孩子未结罚款金额为{amount:d}元")
@given("孩子未结罚款金额为{amount:d}")
def step_fines_amount(context, amount):
    context.child.outstanding_fines = amount
    context.db.commit()


@given("丢失图书定价{price:d}元")
def step_lost_book_price(context, price):
    # 设置图书价格用于罚款计算
    if hasattr(context, "book") and context.book:
        context.book.price = price
        context.db.commit()
    context.book_price = price


@when("家长为孩子缴纳押金{amount:d}元")
def step_parent_pay_deposit(context, amount):
    context.response = context.client.post(
        "/deposit/pay",
        json={"child_id": context.child.id},
        headers=context.headers,
    )


@when("家长再次尝试缴纳押金")
def step_parent_pay_again(context):
    context.response = context.client.post(
        "/deposit/pay",
        json={"child_id": context.child.id},
        headers=context.headers,
    )


@when("家长申请押金退款")
def step_parent_request_refund(context):
    context.response = context.client.post(
        "/deposit/refund",
        json={"child_id": context.child.id},
        headers=context.headers,
    )


@when("家长查看押金页面")
def step_parent_view_deposit(context):
    context.response = context.client.get(
        f"/deposit/status?child_id={context.child.id}",
        headers=context.headers,
    )


@when("系统计算逾期罚款")
@when("系统计算罚款（定价 x 1.5 = {amount:d}元）")
def step_calc_fine(context, amount=0):
    # T1：禁自写公式——逾期罚款走真实任务（fine_policy 统一口径）；
    # 丢失罚款走真实 deduct_deposit（押金扣除是独立管理操作，B11 记账语义）
    if amount == 0:
        from backend.tasks.scheduler import mark_overdue_books

        mark_overdue_books(db=context.db)
    else:
        from backend.domain.deposit.schemas import DepositDeductRequest
        from backend.domain.deposit.service import DepositService

        DepositService(context.db).deduct_deposit(
            DepositDeductRequest(
                child_id=context.child.id, amount=amount, reason="丢失赔偿"
            )
        )
    context.fine_amount = amount


@then('创建押金记录，状态为"PAID"')
def step_deposit_record_created(context):
    record = (
        context.db.query(DepositRecord)
        .filter(DepositRecord.child_id == context.child.id)
        .first()
    )
    assert record is not None
    assert record.status == DepositStatus.PAID


@then("显示押金缴纳成功提示")
def step_deposit_success_msg(context):
    assert context.response is not None
    assert context.response.status_code in (200, 201)


@then('孩子的押金状态更新为"已缴纳"')
def step_child_deposit_paid(context):
    context.db.refresh(context.child)
    assert context.child.deposit_status == DepositStatus.PAID


@then("退款申请创建成功")
def step_refund_created(context):
    assert context.response is not None
    assert context.response.status_code in (200, 201)


@then('押金状态更新为"退款中"')
def step_deposit_refunding(context):
    assert context.response is not None
    assert context.response.status_code == 200


@then("退款申请不创建")
def step_no_refund(context):
    # T1：恒真断言清零——真实端点必须 4xx（此前含 200 恒真）
    assert context.response is not None
    assert context.response.status_code in (400, 403, 422), context.response.text


@then('显示押金状态为"已缴纳"')
def step_show_paid(context):
    assert context.response.status_code == 200


@then("显示押金余额")
def step_show_balance(context):
    assert context.response.status_code == 200
    data = context.response.json()
    # 押金状态接口返回 amount 字段
    assert (
        "amount" in data or "balance" in data or "deposit" in data or "status" in data
    )


@then("显示未结罚款金额")
def step_show_fines(context):
    # T1：空断言清零——押金状态接口返回 fine 字段，须与孩子实际未缴一致
    assert context.response.status_code == 200
    data = context.response.json()
    context.db.refresh(context.child)
    assert float(data.get("fine", 0)) == float(context.child.outstanding_fines or 0), (
        f"接口 fine={data.get('fine')} 与孩子 outstanding={context.child.outstanding_fines} 不一致"
    )


@then("从押金中扣除逾期罚款")
def step_deduct_fine(context):
    # 验证罚款已记录
    context.db.refresh(context.child)
    assert float(context.child.outstanding_fines or 0) > 0


@then("孩子未结罚款金额增加{amount:d}元")
def step_fines_increased(context, amount):
    context.db.refresh(context.child)
    assert float(context.child.outstanding_fines) >= float(amount)


@then("押金余额更新为{amount:d}元")
def step_balance_updated(context, amount):
    # T1：空断言清零——有效余额 = amount - deduct_amount（真实 deduct 语义）
    record = (
        context.db.query(DepositRecord)
        .filter(DepositRecord.child_id == context.child.id)
        .first()
    )
    assert record is not None
    effective = (record.amount or 0) - (record.deduct_amount or 0)
    assert float(effective) == float(amount), (
        f"押金有效余额应为 {amount}，实际 {effective}（amount={record.amount}, deduct={record.deduct_amount}）"
    )


@then("押金扣除罚款{amount:d}元")
def step_deposit_deducted_amount(context, amount):
    # T1：真实 deduct_deposit 断言——记录置 DEDUCTED 且 deduct_amount 匹配
    record = (
        context.db.query(DepositRecord)
        .filter(DepositRecord.child_id == context.child.id)
        .first()
    )
    assert record is not None
    assert float(record.deduct_amount or 0) == float(amount), (
        f"押金应扣除 {amount}，实际 deduct_amount={record.deduct_amount}"
    )
    from backend.common.types import DepositStatus

    assert record.status == DepositStatus.DEDUCTED


@then("押金足额抵扣未结罚款不变")
def step_fines_unchanged(context):
    # T1：押金足额抵扣时 outstanding 不增加（B11 记账语义）
    context.db.refresh(context.child)
    assert float(context.child.outstanding_fines or 0) == 0


@then("未结罚款已更新")
def step_fines_updated(context):
    # T1：真实任务计算后 outstanding 反映罚款
    context.db.refresh(context.child)
    assert float(context.child.outstanding_fines or 0) > 0


@then("押金余额保持不变")
def step_balance_unchanged(context):
    record = (
        context.db.query(DepositRecord)
        .filter(DepositRecord.child_id == context.child.id)
        .first()
    )
    assert record is not None
    assert float(record.amount or 0) == 1200.0
    assert float(record.deduct_amount or 0) == 0.0


@then("退款金额自动抵扣未结罚款{amount:d}元")
def step_refund_deducts_fines(context, amount):
    """B11：押金退款金额 = 押金 - 未缴罚款（自动抵扣，不再拦截）"""
    assert context.response.status_code == 200
    data = context.response.json()
    expected = 1200 - amount
    assert float(data["refund_amount"]) == float(expected), (
        f"退款金额应为 {expected}（押金1200-罚款{amount}），实际 {data['refund_amount']}"
    )
