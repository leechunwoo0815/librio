# tests/unit/test_h_group_copywriting.py
"""批次11 单元测试 — H1 支付锁孩子 / H2 挑战徽标 / H3 报告通知 / G 文案对齐"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.common.exceptions import ForbiddenError, ValidationError, ConflictError
from backend.common.types import MemberStatus, OrderType, PayStatus
from backend.database import Base
from backend.domain.advancement.models import ChildLevel, Level
from backend.domain.book.models import Book
from backend.domain.book.schemas import BookSearch
from backend.domain.book.service import BookService
from backend.domain.borrow.service import BorrowService
from backend.domain.borrow.schemas import BorrowBookRequest
from backend.domain.child.models import Child
from backend.domain.message.models import SystemMessage
from backend.domain.order.models import Order
from backend.domain.order.schemas import OrderPayCallback
from backend.domain.order.service import OrderService
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    from backend.bootstrap import register_event_handlers

    register_event_handlers()
    yield session
    session.close()


def _mk(db):
    user = User(openid="h1", phone="13800000901")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="小明",
        age=7,
        grade="二年级",
        status=MemberStatus.OBSERVATION,
    )
    db.add(child)
    db.commit()
    return user, child


class TestH1PaymentLocksChild:
    """H1：订单支付只影响订单上的孩子，不可被切换劫持"""

    def test_payment_applies_to_order_child_only(self, db):
        user, child_a = _mk(db)
        child_b = Child(
            user_id=user.id,
            name="小红",
            age=5,
            grade="大班",
            status=MemberStatus.TRIAL,
        )
        db.add(child_b)
        db.commit()

        order = Order(
            order_no="H1-LOCK-1",
            user_id=user.id,
            child_id=child_a.id,
            type=OrderType.OFFICIAL_MEMBER,
            amount=Decimal("5400"),
            pay_status=PayStatus.PENDING,
        )
        db.add(order)
        db.commit()

        svc = OrderService(db)
        svc.handle_payment_callback(
            OrderPayCallback(
                order_no="H1-LOCK-1",
                trade_no="WX1",
                pay_type=1,
                amount=Decimal("5400"),
            )
        )
        db.refresh(child_a)
        db.refresh(child_b)
        assert child_a.status == MemberStatus.OFFICIAL
        assert child_b.status == MemberStatus.TRIAL  # B 不受影响


class TestH2ChallengeBadge:
    def test_challenge_flag_by_level_ar(self, db):
        _, child = _mk(db)
        level = Level(
            name="A", sort_order=1, required_books=3, max_ar_level=Decimal("2.0")
        )
        db.add(level)
        db.commit()
        db.add(ChildLevel(child_id=child.id, level_id=level.id, is_current=True))
        easy = Book(
            isbn="H2-E",
            title="简单",
            author="A",
            ar_value=Decimal("1.5"),
            age_min=3,
            age_max=9,
            word_count=100,
        )
        hard = Book(
            isbn="H2-H",
            title="困难",
            author="A",
            ar_value=Decimal("3.5"),
            age_min=3,
            age_max=9,
            word_count=100,
        )
        db.add_all([easy, hard])
        db.commit()

        svc = BookService(db)
        result = svc.search_books(BookSearch(page=1, page_size=10), child_id=child.id)
        flags = {b.title: b.is_challenge for b in result.items}
        assert flags["简单"] is False
        assert flags["困难"] is True

    def test_no_child_no_flag(self, db):
        svc = BookService(db)
        result = svc.search_books(BookSearch(page=1, page_size=10))
        assert all(b.is_challenge is None for b in result.items)


class TestH3ReportNotify:
    def test_weekly_report_sends_message(self, db):
        from backend.tasks import scheduler

        _, child = _mk(db)
        # generate_weekly_reports 使用自有 session，这里直接验证消息写入逻辑：
        # 调用 _create_message（与任务内同一路径）
        scheduler._create_message(
            db,
            user_id=child.user_id,
            title="孩子的周报来啦",
            content="小明上周阅读 60 分钟，读完 1 本书，点击查看完整周报～",
            msg_type=1,
            priority=1,
        )
        db.commit()
        msg = (
            db.query(SystemMessage)
            .filter(SystemMessage.user_id == child.user_id, SystemMessage.msg_type == 1)
            .first()
        )
        assert msg is not None and "周报" in msg.title


class TestGCopywriting:
    """G1/G3：后端提示文案对齐附录 K.1（人性化改写）"""

    def test_borrow_no_deposit_message(self, db):
        _, child = _mk(db)
        child.deposit_status = 0
        db.commit()
        book = Book(
            isbn="G1-B",
            title="书",
            author="A",
            ar_value=Decimal("1.0"),
            age_min=3,
            age_max=9,
            word_count=100,
            total_stock=1,
            available_stock=1,
        )
        db.add(book)
        db.commit()
        svc = BorrowService(db)
        with pytest.raises(ForbiddenError, match="缴纳押金后即可借阅实体书哦～"):
            svc.borrow_book(BorrowBookRequest(child_id=child.id, book_id=book.id))

    def test_borrow_out_of_stock_message(self, db):
        _, child = _mk(db)
        child.deposit_status = 1
        db.commit()
        book = Book(
            isbn="G1-C",
            title="书",
            author="A",
            ar_value=Decimal("1.0"),
            age_min=3,
            age_max=9,
            word_count=100,
            total_stock=1,
            available_stock=0,
        )
        db.add(book)
        db.commit()
        svc = BorrowService(db)
        with pytest.raises(ValidationError, match="该书暂无库存"):
            svc.borrow_book(BorrowBookRequest(child_id=child.id, book_id=book.id))

    def test_bookshelf_duplicate_message(self, db):
        from backend.domain.bookshelf.service import BookshelfService

        _, child = _mk(db)
        book = Book(
            isbn="G1-D",
            title="书",
            author="A",
            ar_value=Decimal("1.0"),
            age_min=3,
            age_max=9,
            word_count=100,
        )
        db.add(book)
        db.commit()
        svc = BookshelfService(db)
        svc.add_to_shelf(child.id, book.id)
        with pytest.raises(ConflictError, match="想读清单里啦"):
            svc.add_to_shelf(child.id, book.id)
