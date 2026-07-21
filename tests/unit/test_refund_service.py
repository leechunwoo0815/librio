import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.order.models import Order
from backend.domain.refund.models import RefundApplication
from backend.domain.refund.service import RefundService
from backend.domain.refund.schemas import RefundCreate
from backend.domain.order.service import OrderService
from backend.domain.borrow.models import BorrowRecord
from backend.domain.book.models import Book
from backend.common.types import PayStatus, OrderType, BorrowStatus


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _setup(db):
    user = User(openid="test_refund_svc", phone="13800138031")
    db.add(user)
    db.flush()
    child = Child(
        user_id=user.id,
        name="退款测试",
        age=7,
        grade="二年级",
        status=Child.STATUS_OFFICIAL,
    )
    db.add(child)
    db.flush()
    order = Order(
        order_no="MW_REFUND_SVC_001",
        user_id=user.id,
        child_id=child.id,
        type=OrderType.OBSERVATION,
        amount=Decimal("500.00"),
        pay_status=PayStatus.PAID,
        pay_time=datetime.now(),
    )
    db.add(order)
    db.commit()
    return user, child, order


def test_apply_refund_duplicate_raises_conflict(db):
    user, child, order = _setup(db)
    svc = RefundService(db)
    data = RefundCreate(order_id=order.id, used_days=5, reason="不满意")
    r1 = svc.apply_refund(user.id, data)
    assert r1.id is not None
    assert r1.status == RefundApplication.STATUS_PENDING
    with pytest.raises(Exception, match="正在处理|已有|pending|退款申请已存在|重复"):
        svc.apply_refund(user.id, data)


# ── T1.5 退款拦截网：活跃借阅拦截 ──
def _book(db):
    book = Book(
        isbn="T1_5_TEST",
        title="退款拦截测试用书",
        author="测试作者",
        ar_value="1.0",
        age_min=3,
        age_max=12,
    )
    db.add(book)
    db.flush()
    return book


def test_apply_refund_active_borrows_blocks(db):
    """P0 拦截：有 BORROWING 借阅记录时拒绝退款"""
    user, child, order = _setup(db)
    book = _book(db)
    due = datetime.now() + timedelta(days=21)
    borrow = BorrowRecord(
        child_id=child.id,
        book_id=book.id,
        status=BorrowStatus.BORROWING,
        borrow_time=datetime.now(),
        due_date=due,
    )
    db.add(borrow)
    db.commit()

    svc = RefundService(db)
    data = RefundCreate(order_id=order.id, used_days=5, reason="不满意")
    with pytest.raises(Exception, match="未归还|归还.*图书|active.*borrow"):
        svc.apply_refund(user.id, data)


def test_apply_refund_overdue_borrows_blocks(db):
    """P0 拦截：有 OVERDUE 借阅记录时拒绝退款"""
    user, child, order = _setup(db)
    book = _book(db)
    due = datetime.now() - timedelta(days=9)
    borrow = BorrowRecord(
        child_id=child.id,
        book_id=book.id,
        status=BorrowStatus.OVERDUE,
        borrow_time=datetime.now() - timedelta(days=30),
        due_date=due,
    )
    db.add(borrow)
    db.commit()

    svc = RefundService(db)
    data = RefundCreate(order_id=order.id, used_days=5, reason="不满意")
    with pytest.raises(Exception, match="未归还|归还.*图书|active.*borrow"):
        svc.apply_refund(user.id, data)


def test_apply_refund_returned_borrows_allowed(db):
    """已归还的借阅记录不应阻止退款"""
    user, child, order = _setup(db)
    book = _book(db)
    due = datetime.now() - timedelta(days=5)
    borrow = BorrowRecord(
        child_id=child.id,
        book_id=book.id,
        status=BorrowStatus.RETURNED,
        borrow_time=datetime.now() - timedelta(days=5),
        due_date=due,
        return_time=datetime.now(),
    )
    db.add(borrow)
    db.commit()

    svc = RefundService(db)
    data = RefundCreate(order_id=order.id, used_days=5, reason="不满意")
    r = svc.apply_refund(user.id, data)
    assert r.id is not None
    assert r.status == RefundApplication.STATUS_PENDING


# ── T1.5 退款拦截网：365天退款上限 ──
def test_apply_refund_annual_limit_blocks(db):
    """P2-7：同一孩子 365 天内有已退款的记录则拒绝"""
    user, child, order = _setup(db)
    # 创建一笔已完成的退款申请
    old_refund = RefundApplication(
        order_id=order.id,
        user_id=user.id,
        child_id=child.id,
        refund_amount=Decimal("100.00"),
        status=RefundApplication.STATUS_APPROVED,
        create_time=datetime.now() - timedelta(days=30),
    )
    db.add(old_refund)
    db.commit()

    svc = RefundService(db)
    data = RefundCreate(order_id=order.id, used_days=5, reason="还想退")
    with pytest.raises(Exception, match="365|年度上限|退款.*1 次|only.*one"):
        svc.apply_refund(user.id, data)


# ── T1.5 退款拦截网：订单合法性校验 ──
def test_apply_refund_order_not_found(db):
    """不存在的订单应报 NotFound"""
    user, _, _ = _setup(db)
    svc = RefundService(db)
    data = RefundCreate(order_id=99999, used_days=5, reason="不存在")
    with pytest.raises(Exception, match="不存在|not.*found"):
        svc.apply_refund(user.id, data)


def test_apply_refund_order_not_owned(db):
    """他人订单应报 Forbidden"""
    _, _, order = _setup(db)
    # 创建另一个用户
    other = User(openid="other_user", phone="13900139002")
    db.add(other)
    db.commit()

    svc = RefundService(db)
    data = RefundCreate(order_id=order.id, used_days=5, reason="这不是我的")
    with pytest.raises(Exception, match="不属于|forbidden|not.*owner"):
        svc.apply_refund(other.id, data)


def test_apply_refund_order_not_paid(db):
    """未支付的订单应报 ValidationError"""
    user, child, order = _setup(db)
    order.pay_status = PayStatus.PENDING
    db.commit()

    svc = RefundService(db)
    data = RefundCreate(order_id=order.id, used_days=5, reason="没付钱")
    with pytest.raises(Exception, match="未支付|not.*paid"):
        svc.apply_refund(user.id, data)


def test_preview_refund_matches_actual_calculation(db):
    """预览退款金额必须与实际退款计算金额一致（无中间取整偏差）"""
    user = User(openid="preview_vs_actual", phone="13800138000")
    db.add(user)
    db.flush()
    child = Child(
        user_id=user.id,
        name="预览测试",
        age=7,
        grade="二年级",
        status=Child.STATUS_OFFICIAL,
    )
    db.add(child)
    db.flush()
    order = Order(
        order_no="MW_PREVIEW_001",
        user_id=user.id,
        child_id=child.id,
        type=OrderType.OFFICIAL_MEMBER,
        amount=Decimal("5400.00"),
        pay_status=PayStatus.PAID,
        pay_time=datetime.now(),
    )
    db.add(order)
    db.commit()

    used_days = 30
    preview = OrderService(db).calculate_refund(order.id, used_days)
    actual = RefundService(db)._calculate(order, used_days)

    assert preview["refund_amount"] == actual, (
        f"预览 {preview['refund_amount']} ≠ 实际 {actual}"
        f" | daily_rate={preview['daily_rate']} used_amount={preview['used_amount']}"
    )
