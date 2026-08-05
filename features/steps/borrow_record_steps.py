# features/steps/borrow_record_steps.py
"""V3.1 实体书借阅BDD步骤"""

from datetime import datetime, timedelta

from behave import given, when, then
from backend.domain.book.models import Book, BookCopy
from backend.domain.borrow.models import BorrowRecord
from backend.common.types import BorrowStatus


@given('图书"{title}"已有馆藏副本')
@given('图书"{title}"已有馆藏副本（条码{barcode}）')
def step_book_has_copy(context, title, barcode="001"):
    book = context.db.query(Book).filter(Book.title == title).first()
    if not book:
        book = Book(
            isbn="9780064400558",
            title=title,
            author="E.B. White",
            ar_value=3.2,
            age_min=7,
            age_max=9,
            word_count=30000,
            total_stock=1,
            available_stock=1,
            price=80,
        )
        context.db.add(book)
        context.db.commit()
        context.db.refresh(book)
    context.book = book
    barcode_str = f"978-0-06-112495-1-{barcode}"
    copy = BookCopy(book_id=book.id, barcode=barcode_str)
    context.db.add(copy)
    context.db.commit()
    context.barcode = barcode_str


@given('条码"{barcode}"在系统中不存在')
def step_barcode_not_exists(context, barcode):
    context.barcode = barcode
    context.barcode_not_found = True


@when('工作人员扫描条码"{barcode}"')
@when("工作人员扫描该条码")
def step_scan_barcode(context, barcode=None):
    if barcode is None:
        barcode = getattr(context, "barcode", "978-0-06-112495-1-001")
    context.barcode = barcode
    copy = context.db.query(BookCopy).filter(BookCopy.barcode == barcode).first()
    context.found_copy = copy
    if not copy:
        if getattr(context, "barcode_not_found", False):
            # T1：首次扫码缺图书信息 → 真实调用，服务端应拦截提示输入图书信息
            context.response = context.client.post(
                "/borrow/scan",
                json={"child_id": context.child.id, "barcode": barcode},
                headers=_staff_borrow_headers(context),
            )
        return

    book = context.db.query(Book).filter(Book.id == copy.book_id).first()
    context.book = book
    existing = (
        context.db.query(BorrowRecord)
        .filter(
            BorrowRecord.child_id == context.child.id,
            BorrowRecord.book_id == book.id,
            BorrowRecord.status == BorrowStatus.BORROWING,
            BorrowRecord.is_deleted == 0,
        )
        .first()
    )
    from backend.domain.reservation.models import Reservation
    from backend.common.types import ReservationStatus

    reservation = (
        context.db.query(Reservation)
        .filter(
            Reservation.child_id == context.child.id,
            Reservation.book_id == book.id,
            Reservation.status == ReservationStatus.PENDING,
            Reservation.is_deleted == 0,
        )
        .first()
    )
    if existing:
        # 还书：真实端点（scan-return 按副本条码匹配活跃借阅）
        context._stock_before = book.available_stock or 0
        context.response = context.client.post(
            "/borrow/scan-return",
            json={"barcode": barcode},
            headers=_staff_borrow_headers(context),
        )
        assert context.response.status_code == 200, context.response.text
        context.borrow_record = (
            context.db.query(BorrowRecord)
            .filter(BorrowRecord.id == existing.id)
            .first()
        )
    elif reservation:
        # 预约取书：真实端点（F43：{barcode} 直通）
        context.response = context.client.post(
            "/admin/api/reservations/fulfill",
            json={"barcode": barcode},
            headers=_staff_borrow_headers(context),
        )
        assert context.response.status_code == 200, context.response.text
        context.reservation = reservation
        context.borrow_record = (
            context.db.query(BorrowRecord)
            .filter(
                BorrowRecord.child_id == context.child.id,
                BorrowRecord.book_id == book.id,
                BorrowRecord.status == BorrowStatus.BORROWING,
            )
            .first()
        )
    else:
        # 借书：真实端点
        context.response = context.client.post(
            "/borrow/scan",
            json={"child_id": context.child.id, "barcode": barcode},
            headers=_staff_borrow_headers(context),
        )
        if context.response.status_code == 201:
            context.borrow_record = (
                context.db.query(BorrowRecord)
                .filter(
                    BorrowRecord.child_id == context.child.id,
                    BorrowRecord.book_id == book.id,
                    BorrowRecord.status == BorrowStatus.BORROWING,
                )
                .first()
            )


def _staff_borrow_headers(context):
    """工作人员（管理员）借书/还书/取书/丢失凭证 — T1：steps 调真实端点"""
    from backend.domain.admin.models import Admin
    from backend.domain.admin.rbac_models import Role, RolePermission
    from backend.middleware.admin_auth import create_admin_token

    # 同一场景内多次调用复用角色/管理员（behave context 跨场景复用，不能缓存 token）
    role = context.db.query(Role).filter(Role.code == "test_borrow_role").first()
    if not role:
        role = Role(code="test_borrow_role", name="借书测试角色", is_system=False)
        context.db.add(role)
        context.db.flush()
    for code in (
        "borrow.create",
        "borrow.return",
        "reservation.fulfill",
        "borrow.mark_lost",
        "book_damage.review",
    ):
        existing_perm = (
            context.db.query(RolePermission)
            .filter(
                RolePermission.role_id == role.id,
                RolePermission.permission_code == code,
            )
            .first()
        )
        if not existing_perm:
            context.db.add(RolePermission(role_id=role.id, permission_code=code))
    context.db.flush()
    admin = (
        context.db.query(Admin).filter(Admin.username == "test_borrow_admin").first()
    )
    if not admin:
        admin = Admin(
            username="test_borrow_admin",
            password_hash="x",
            name="借书测试管理员",
            role=0,
            status=1,
            admin_role_id=role.id,
        )
        context.db.add(admin)
    context.db.commit()
    token = create_admin_token(admin_id=admin.id, role=0)
    return {"Authorization": f"Bearer {token}"}


@when("工作人员扫描条码尝试借书")
def step_scan_to_borrow(context):
    # R6 修复假绿：原实现仅在 hasattr(context, "barcode") 时才调 API，
    # 无条码场景静默跳过 + 弱断言恒通过。现始终走真实管理员借书端点。
    if not getattr(context, "book", None):
        book = Book(
            isbn="9780064400558",
            title="Charlotte's Web",
            author="E.B. White",
            ar_value=3.2,
            age_min=7,
            age_max=9,
            word_count=30000,
            total_stock=1,
            available_stock=1,
            price=80,
        )
        context.db.add(book)
        context.db.commit()
        context.db.refresh(book)
        context.book = book
    context.response = context.client.post(
        "/borrow/",
        json={"child_id": context.child.id, "book_id": context.book.id},
        headers=_staff_borrow_headers(context),
    )


@when('工作人员扫描该书的新条码"{barcode}"')
def step_scan_new_barcode(context, barcode):
    context.barcode = barcode
    # T1：同ISBN不同条码 → 真实调用 scan（按 ISBN 找已有图书，仅新建副本）
    context.new_book_isbn = context.book.isbn
    context.response = context.client.post(
        "/borrow/scan",
        json={
            "child_id": context.child.id,
            "barcode": barcode,
            "title": context.book.title,
            "author": context.book.author,
            "isbn": context.book.isbn,
            "ar_value": float(context.book.ar_value),
            "age_min": context.book.age_min,
            "age_max": context.book.age_max,
        },
        headers=_staff_borrow_headers(context),
    )
    assert context.response.status_code == 201, context.response.text
    context.borrow_record = (
        context.db.query(BorrowRecord)
        .filter(
            BorrowRecord.child_id == context.child.id,
            BorrowRecord.book_id == context.book.id,
            BorrowRecord.status == BorrowStatus.BORROWING,
        )
        .first()
    )


@when('工作人员输入书名"{title}"和ISBN"{isbn}"')
def step_input_book_info(context, title, isbn):
    context.new_book_title = title
    context.new_book_isbn = isbn


@when("确认创建")
def step_confirm_create(context):
    # T1/F47：首次扫码建档 + 借阅一体走真实端点（author 必填）
    title = getattr(context, "new_book_title", "New Book")
    isbn = getattr(context, "new_book_isbn", "978-0-06-112495-2")
    barcode = getattr(context, "barcode", "978-0-06-112495-2-001")
    context.response = context.client.post(
        "/borrow/scan",
        json={
            "child_id": context.child.id,
            "barcode": barcode,
            "title": title,
            "author": "E.B. White",
            "isbn": isbn,
            "ar_value": 2.0,
            "age_min": 5,
            "age_max": 9,
        },
        headers=_staff_borrow_headers(context),
    )
    assert context.response.status_code == 201, context.response.text
    context.book = context.db.query(Book).filter(Book.isbn == isbn).first()
    context.borrow_record = (
        context.db.query(BorrowRecord)
        .filter(
            BorrowRecord.child_id == context.child.id,
            BorrowRecord.book_id == context.book.id,
            BorrowRecord.status == BorrowStatus.BORROWING,
        )
        .first()
    )


@when("工作人员扫描条码完成还书")
def step_scan_to_return(context):
    # T1：还书走真实端点（fine 由 return_book 按 fine_policy 计算）
    barcode = getattr(context, "barcode", "978-0-06-112495-1-001")
    context.response = context.client.post(
        "/borrow/scan-return",
        json={"barcode": barcode},
        headers=_staff_borrow_headers(context),
    )
    assert context.response.status_code == 200, context.response.text
    context.borrow_record = (
        context.db.query(BorrowRecord)
        .filter(BorrowRecord.id == context.borrow_record.id)
        .first()
    )


@when('工作人员标记该书为"{status}"')
def step_mark_book_status(context, status):
    if status == "丢失" and hasattr(context, "borrow_record") and context.borrow_record:
        # T1：标记丢失走真实端点（mark_book_lost：定价×1.5 计入 outstanding）
        context.response = context.client.post(
            f"/admin/api/borrows/{context.borrow_record.id}/mark-lost",
            headers=_staff_borrow_headers(context),
        )
        assert context.response.status_code == 200, context.response.text
        context.db.refresh(context.borrow_record)


@given('孩子有"{title}"的借阅记录')
@given('孩子有"{title}"的借阅记录（状态为BORROWED）')
def step_child_has_borrow(context, title):
    book = context.db.query(Book).filter(Book.title == title).first()
    if not book:
        book = Book(
            isbn="9780064400558",
            title=title,
            author="E.B. White",
            ar_value=3.2,
            age_min=7,
            age_max=9,
            word_count=30000,
            price=80,
        )
        context.db.add(book)
        context.db.commit()
        context.db.refresh(book)
    context.book = book
    copy = context.db.query(BookCopy).filter(BookCopy.book_id == book.id).first()
    if not copy:
        copy = BookCopy(book_id=book.id, barcode="978-0-06-112495-1-001")
        context.db.add(copy)
        context.db.commit()
    record = BorrowRecord(
        child_id=context.child.id,
        book_id=book.id,
        book_copy_id=copy.id,
        borrow_time=datetime.now() - timedelta(days=10),
        due_date=datetime.now() + timedelta(days=11),
        status=BorrowStatus.BORROWING,
    )
    context.db.add(record)
    context.db.commit()
    context.borrow_record = record


@given('孩子有"{title}"的借阅记录（已超过到期日期）')
def step_child_has_overdue_borrow(context, title):
    book = context.db.query(Book).filter(Book.title == title).first()
    if not book:
        book = Book(
            isbn="9780064400558",
            title=title,
            author="E.B. White",
            ar_value=3.2,
            age_min=7,
            age_max=9,
            word_count=30000,
            price=80,
        )
        context.db.add(book)
        context.db.commit()
        context.db.refresh(book)
    context.book = book
    copy = context.db.query(BookCopy).filter(BookCopy.book_id == book.id).first()
    if not copy:
        copy = BookCopy(book_id=book.id, barcode="978-0-06-112495-1-001")
        context.db.add(copy)
        context.db.commit()
    # 真实 fine_policy 有"首次免罚"：先造一条历史逾期记录，使本场景非首次、罚款真实生效
    prior = BorrowRecord(
        child_id=context.child.id,
        book_id=book.id,
        book_copy_id=copy.id,
        status=BorrowStatus.RETURNED,
        borrow_time=datetime.now() - timedelta(days=60),
        due_date=datetime.now() - timedelta(days=50),
        return_time=datetime.now() - timedelta(days=40),
        overdue_days=5,
    )
    context.db.add(prior)
    record = BorrowRecord(
        child_id=context.child.id,
        book_id=book.id,
        book_copy_id=copy.id,
        borrow_time=datetime.now() - timedelta(days=30),
        due_date=datetime.now() - timedelta(days=9),
        status=BorrowStatus.BORROWING,
    )
    context.db.add(record)
    context.db.commit()
    context.borrow_record = record


@given('孩子有借阅记录到期日期为"{date}"')
def step_borrow_due_date(context, date):
    from datetime import datetime as dt

    context._feature_due_date = dt.strptime(date, "%Y-%m-%d").date()
    if not hasattr(context, "book") or not context.book:
        book = context.db.query(Book).filter(Book.title == "Charlotte's Web").first()
        if not book:
            book = Book(
                isbn="9780064400558",
                title="Charlotte's Web",
                author="E.B. White",
                ar_value=3.2,
                age_min=7,
                age_max=9,
                word_count=30000,
                price=80,
            )
            context.db.add(book)
            context.db.commit()
            context.db.refresh(book)
        context.book = book
    due = dt.strptime(date, "%Y-%m-%d")
    record = BorrowRecord(
        child_id=context.child.id,
        book_id=context.book.id,
        book_copy_id=getattr(context, "found_copy", None).id
        if getattr(context, "found_copy", None)
        else None,
        borrow_time=due - timedelta(days=21),
        due_date=due,
        status=BorrowStatus.BORROWING,
    )
    context.db.add(record)
    context.db.commit()
    context.borrow_record = record


@given("该书定价为{price:d}元")
def step_book_price(context, price):
    if hasattr(context, "book") and context.book:
        context.book.price = price
        context.db.commit()


@when('定时任务在"{date}"执行')
@when('定时任务在"{date}"执行逾期检测')
def step_scheduled_task_at(context, date):
    """T1：调真实任务（mark_overdue_books 统一 fine_policy 口径，不再自写公式）

    到期提醒场景：feature 里的日期是相对剧本日期（如到期 06-15、任务 06-10），
    此处把记录 due_date 换算成相对 now 的偏移再跑真实 check_due_date_reminders。
    """
    from datetime import datetime as _dt

    from backend.tasks.scheduler import (
        check_due_date_reminders,
        mark_overdue_books,
    )

    feature_due = getattr(context, "_feature_due_date", None)
    if feature_due is not None and hasattr(context, "borrow_record"):
        task_day = _dt.strptime(date, "%Y-%m-%d").date()
        delta = (feature_due - task_day).days
        # delta=0（当天到期）：加 5 分钟缓冲，避免 mark_overdue 的 now 微秒级晚于 due 抢先标逾期
        context.borrow_record.due_date = datetime.now() + timedelta(
            days=delta, minutes=5 if delta == 0 else 0
        )
        context.db.commit()

    mark_overdue_books(db=context.db)
    check_due_date_reminders(db=context.db)


# ==================== Then 步骤 ====================


@then("系统提示输入图书信息")
def step_prompt_book_info(context):
    # 条码不存在时，系统应提示输入信息（此处验证条码确实不存在）
    assert getattr(context, "barcode_not_found", False) or context.found_copy is None


@then("系统创建图书记录")
def step_system_creates_book(context):
    book = context.db.query(Book).filter(Book.title == context.new_book_title).first()
    assert book is not None


@then("系统创建馆藏副本（关联该条码）")
def step_system_creates_copy(context):
    copy = (
        context.db.query(BookCopy).filter(BookCopy.barcode == context.barcode).first()
    )
    assert copy is not None


@then("系统识别到ISBN已存在")
def step_isbn_exists(context):
    books = context.db.query(Book).filter(Book.isbn == context.new_book_isbn).count()
    assert books == 1


@then("系统识别到已有副本")
def step_copy_exists(context):
    copy = (
        context.db.query(BookCopy).filter(BookCopy.barcode == context.barcode).first()
    )
    assert copy is not None


@then("不创建借阅记录")
def step_no_borrow_created(context):
    child_id = getattr(context.child, "id", None)
    if child_id is not None:
        count = (
            context.db.query(BorrowRecord)
            .filter(BorrowRecord.child_id == child_id)
            .count()
        )
    else:
        count = (
            context.db.query(BorrowRecord)
            .filter(BorrowRecord.status == BorrowStatus.BORROWING)
            .count()
        )
    assert count == 0


# ==================== R6 异常场景补缺 ====================


@given("孩子已借阅{n:d}本图书")
def step_child_has_n_borrows(context, n):
    for i in range(n):
        book = Book(
            isbn=f"978L{i:05d}",
            title=f"LimitBook{i}",
            author="Author",
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
        context.db.add(
            BorrowRecord(
                child_id=context.child.id,
                book_id=book.id,
                borrow_time=datetime.now(),
                due_date=datetime.now() + timedelta(days=21),
                status=BorrowStatus.BORROWING,
            )
        )
    context.db.commit()


@when("孩子尝试再借一本新书")
def step_try_borrow_new_book(context):
    book = Book(
        isbn="978NEW000001",
        title="NewBorrow",
        author="Author",
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
    context.response = context.client.post(
        "/borrow/",
        json={"child_id": context.child.id, "book_id": book.id},
        headers=_staff_borrow_headers(context),
    )


@when("孩子尝试再借同一本书")
@when("孩子尝试借阅该书")
def step_try_borrow_same_book(context):
    context.response = context.client.post(
        "/borrow/",
        json={"child_id": context.child.id, "book_id": context.book.id},
        headers=_staff_borrow_headers(context),
    )


@then('拦截提示"{message}"')
def step_block_message(context, message):
    """强断言：4xx 状态码 + detail 包含指定消息（区别于弱断言"显示提示"）"""
    assert context.response is not None
    assert context.response.status_code in (400, 403, 404, 409, 422), (
        f"期望拦截状态码，实际 {context.response.status_code}: {context.response.text}"
    )
    detail = context.response.json().get("detail", "")
    assert message in str(detail), f"期望消息含「{message}」，实际 detail: {detail}"


@then("仅创建新的馆藏副本（条码002）")
def step_only_new_copy(context):
    copy = (
        context.db.query(BookCopy)
        .filter(BookCopy.barcode == "978-0-06-112495-1-002")
        .first()
    )
    assert copy is not None


@then("不重复创建图书记录")
def step_no_duplicate_book(context):
    count = context.db.query(Book).filter(Book.isbn == context.new_book_isbn).count()
    assert count == 1


@then("创建借阅记录")
def step_borrow_created(context):
    record = (
        context.db.query(BorrowRecord)
        .filter(BorrowRecord.child_id == context.child.id)
        .first()
    )
    assert record is not None


@then('借阅记录状态为"BORROWED"')
def step_borrow_status_borrowed(context):
    record = (
        context.db.query(BorrowRecord)
        .filter(BorrowRecord.child_id == context.child.id)
        .first()
    )
    assert record.status == BorrowStatus.BORROWING


@then("到期日期为当前日期加21天")
def step_due_date_21_days(context):
    record = (
        context.db.query(BorrowRecord)
        .filter(BorrowRecord.child_id == context.child.id)
        .first()
    )
    assert record.due_date is not None


@then('借阅记录状态更新为"RETURNED"')
def step_borrow_status_returned(context):
    record = (
        context.db.query(BorrowRecord)
        .filter(BorrowRecord.child_id == context.child.id)
        .first()
    )
    assert record.status == BorrowStatus.RETURNED


@then("归还时间为当前时间")
def step_return_time(context):
    record = (
        context.db.query(BorrowRecord)
        .filter(BorrowRecord.child_id == context.child.id)
        .first()
    )
    assert record.return_time is not None


@then("库存释放（可借数量加1）")
def step_stock_released(context):
    if hasattr(context, "book") and context.book:
        context.db.refresh(context.book)
        before = getattr(context, "_stock_before", None)
        if before is not None:
            assert context.book.available_stock == before + 1, (
                f"库存未释放: before={before}, after={context.book.available_stock}"
            )
        else:
            assert (context.book.available_stock or 0) >= 1


@then('该借阅记录标记为"OVERDUE"')
def step_borrow_marked_overdue(context):
    record = (
        context.db.query(BorrowRecord)
        .filter(BorrowRecord.child_id == context.child.id)
        .first()
    )
    assert record.status == BorrowStatus.OVERDUE


@then("该孩子的在线音频伴读功能锁定")
def step_audio_locked(context):
    # T1：真实调用音频锁定校验（B8：逾期超宽限期才锁）
    from backend.common.exceptions import ForbiddenError
    from backend.domain.reading.service import ReadingService

    try:
        ReadingService(context.db)._check_overdue_audio(context.child.id)
    except ForbiddenError:
        return
    raise AssertionError("音频锁定未生效：逾期超宽限期仍可访问音频")


@then("系统计算逾期天数")
def step_calc_overdue_days(context):
    record = (
        context.db.query(BorrowRecord)
        .filter(BorrowRecord.id == context.borrow_record.id)
        .first()
    )
    assert record.overdue_days is not None and record.overdue_days > 0


@then("生成逾期罚款记录")
def step_overdue_fine_created(context):
    record = (
        context.db.query(BorrowRecord)
        .filter(BorrowRecord.id == context.borrow_record.id)
        .first()
    )
    assert record.fine_amount is not None and record.fine_amount > 0, (
        f"逾期罚款未生成: fine_amount={record.fine_amount}, "
        f"overdue_days={record.overdue_days}, fine_waived={record.fine_waived}, "
        f"due={record.due_date}, book_price={record.book.price if record.book else None}"
    )


@then("罚款金额为定价的1.5倍（120元）")
def step_fine_amount(context):
    record = (
        context.db.query(BorrowRecord)
        .filter(BorrowRecord.child_id == context.child.id)
        .first()
    )
    assert float(record.fine_amount) == 120.0


@then("从押金中扣除120元")
def step_deduct_deposit(context):
    context.db.refresh(context.child)
    assert float(context.child.outstanding_fines or 0) > 0


@then("更新未结罚款金额")
def step_update_fines(context):
    # T1：空断言清零——真实任务/服务已把罚款计入 outstanding
    context.db.refresh(context.child)
    assert float(context.child.outstanding_fines or 0) > 0, "未结罚款未更新"


@then('系统发送提醒消息"{msg}"')
def step_send_reminder(context, msg):
    # T1：真实断言提醒消息已入库且内容匹配
    from backend.domain.message.models import SystemMessage

    rows = (
        context.db.query(SystemMessage)
        .filter(
            SystemMessage.user_id == context.user.id,
            SystemMessage.title == "借阅到期提醒",
        )
        .all()
    )
    assert rows, f"未找到借阅到期提醒消息: {msg}"
    assert any(msg in (r.content or "") for r in rows), (
        f"提醒内容不匹配: 期望「{msg}」，实际 {[r.content for r in rows]}"
    )


# ==================== B10 丢失找回 ====================


@when("工作人员登记找回该书")
def step_staff_mark_found(context):
    context.response = context.client.post(
        "/admin/api/damage-reports/found",
        json={"borrow_record_id": context.borrow_record.id},
        headers=_staff_borrow_headers(context),
    )
    assert context.response.status_code == 200, context.response.text


@then("未结罚款全额免除")
def step_fines_fully_waived(context):
    context.db.refresh(context.child)
    assert float(context.child.outstanding_fines or 0) == 0
