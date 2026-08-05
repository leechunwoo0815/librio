# tests/unit/test_f40_f47_reservation_borrow.py
"""第二批 P1 批：F40/F42/F43/F45/F46/F47 预约/借阅链

F40: 取消预约仅 PENDING→CANCELLED（EXPIRED/FULFILLED 取消 = 库存双重释放）
F42: 手动取书强制绑定 AVAILABLE 副本（杜绝 book_copy_id=None 孤儿借阅）
F43: 管理端扫码取书 {barcode} 请求不再 422（schema 补 barcode 透传）
F45: fulfill/expire/cancel 统一条件 UPDATE（WHERE status=PENDING），防并发双释放
F46: 预约创建拦截"同书未还借阅"（库存不再白锁 72h）
F47: 首次扫码建档 author 必填（此前 NOT NULL 必 500）
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.common.exceptions import ConflictError, ValidationError
from backend.common.types import (
    BookCopyStatus,
    BorrowStatus,
    DepositStatus,
    MemberStatus,
    ReservationStatus,
)
from backend.database import Base
from backend.domain.book.models import Book, BookCopy
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.models import Child
from backend.domain.reservation.models import Reservation
from backend.domain.reservation.schemas import ReservationCreateRequest
from backend.domain.user.models import User


@pytest.fixture
def db():
    from backend.events.registry import register_event_handlers

    register_event_handlers()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _seed(db, available=1, total=1):
    user = User(
        id=1, phone="13800000002", parent_name="家长", openid="op_f40", status=1
    )
    db.add(user)
    child = Child(
        id=1,
        user_id=1,
        name="小明",
        age=7,
        grade="二年级",
        status=MemberStatus.OFFICIAL,
        deposit_status=DepositStatus.PAID,
        member_expire_time=datetime.now() + timedelta(days=300),
    )
    db.add(child)
    book = Book(
        id=1,
        isbn="978F4000001",
        title="F40 Book",
        author="A",
        ar_value=2.0,
        age_min=5,
        age_max=9,
        total_stock=total,
        available_stock=available,
        offline_available=1,
        price=50,
    )
    db.add(book)
    if total >= 1:
        db.add(
            BookCopy(
                id=1, book_id=1, barcode="BC-F40-001", status=BookCopyStatus.AVAILABLE
            )
        )
    db.commit()
    return user, child, book


class TestF40CancelOnlyPending:
    def _mk_reservation(self, db, child, status=ReservationStatus.PENDING):
        res = Reservation(
            id=1,
            child_id=child.id,
            book_id=1,
            status=status,
            expire_time=datetime.now() + timedelta(hours=72),
        )
        db.add(res)
        db.commit()
        return res

    def test_cancel_expired_reservation_rejected(self, db):
        """F40：EXPIRED 预约不可取消（此前放行 → 库存双重释放）"""
        from backend.domain.reservation.service import ReservationService

        _, child, book = _seed(db)
        self._mk_reservation(db, child, ReservationStatus.EXPIRED)
        svc = ReservationService(db)
        with pytest.raises(ConflictError, match="仅待取预约可取消"):
            svc.cancel_reservation(1)

    def test_cancel_fulfilled_reservation_rejected(self, db):
        """F40：FULFILLED 预约不可取消（书已借出，取消会释放幻影库存）"""
        from backend.domain.reservation.service import ReservationService

        _, child, book = _seed(db)
        self._mk_reservation(db, child, ReservationStatus.FULFILLED)
        svc = ReservationService(db)
        with pytest.raises(ConflictError, match="仅待取预约可取消"):
            svc.cancel_reservation(1)

    def test_cancel_pending_ok(self, db):
        """F40：PENDING 预约取消正常 + 库存回补一次"""
        from backend.domain.reservation.service import ReservationService

        _, child, book = _seed(db)
        self._mk_reservation(db, child, ReservationStatus.PENDING)
        book.available_stock = 0  # 预约已锁库存
        db.commit()
        svc = ReservationService(db)
        result = svc.cancel_reservation(1)
        assert result["success"] is True
        db.refresh(book)
        assert book.available_stock == 1  # 只 +1，不双重释放


class TestF45ConditionalUpdate:
    def test_expire_after_fulfilled_no_double_release(self, db):
        """F45：已取书后过期任务不再释放库存"""
        from backend.domain.reservation.service import ReservationService

        _, child, book = _seed(db)
        res = Reservation(
            id=1,
            child_id=child.id,
            book_id=1,
            status=ReservationStatus.FULFILLED,
            expire_time=datetime.now() + timedelta(hours=1),
        )
        db.add(res)
        book.available_stock = 0
        db.commit()
        svc = ReservationService(db)
        svc.expire_reservation(1)  # 不应发 ExpiredEvent（条件 UPDATE affected=0）
        db.refresh(book)
        assert book.available_stock == 0  # 无幻影回补

    def test_expire_after_cancelled_no_double_release(self, db):
        """F45：已取消后过期任务不再释放库存"""
        from backend.domain.reservation.service import ReservationService

        _, child, book = _seed(db)
        Reservation(
            id=1,
            child_id=child.id,
            book_id=1,
            status=ReservationStatus.CANCELLED,
            expire_time=datetime.now() + timedelta(hours=1),
        )
        book.available_stock = 1
        db.commit()
        svc = ReservationService(db)
        svc.expire_reservation(1)
        db.refresh(book)
        assert book.available_stock == 1


class TestF46CreateBlocksActiveBorrow:
    def test_create_reservation_with_active_borrow_rejected(self, db):
        """F46：同书未还借阅时不可预约（库存不再白锁 72h）"""
        from backend.domain.reservation.service import ReservationService

        _, child, book = _seed(db)
        db.add(
            BorrowRecord(
                id=1,
                child_id=child.id,
                book_id=1,
                book_copy_id=1,
                status=BorrowStatus.BORROWING,
                borrow_time=datetime.now() - timedelta(days=1),
                due_date=datetime.now() + timedelta(days=20),
            )
        )
        db.commit()
        svc = ReservationService(db)
        with pytest.raises(ValidationError, match="同一本书的未还借阅"):
            svc.create_reservation(
                ReservationCreateRequest(child_id=child.id, book_id=1, venue_id=1)
            )


class TestF47ScanBorrowAuthorRequired:
    def test_scan_new_barcode_requires_author(self, db):
        """F47：首次扫码建档缺 author 必须 422/ValidationError（此前 IntegrityError 500）"""
        from backend.domain.borrow.service import BorrowService

        _, child, book = _seed(db, total=0, available=0)
        svc = BorrowService(db)
        with pytest.raises(ValidationError, match="author"):
            svc.scan_and_borrow(
                child_id=child.id,
                barcode="BC-NEW-001",
                title="New Book",
                isbn="978F4700001",
                ar_value=2.5,
                age_min=5,
                age_max=9,
            )

    def test_scan_new_barcode_with_author_creates_book(self, db):
        """F47：提供 author 后首次扫码建档成功"""
        from backend.domain.borrow.service import BorrowService

        _, child, book = _seed(db, total=0, available=0)
        svc = BorrowService(db)
        result = svc.scan_and_borrow(
            child_id=child.id,
            barcode="BC-NEW-002",
            title="New Book",
            author="New Author",
            isbn="978F4700002",
            ar_value=2.5,
            age_min=5,
            age_max=9,
        )
        assert result is not None
        created = db.query(Book).filter(Book.isbn == "978F4700002").first()
        assert created is not None
        assert created.author == "New Author"
        copy = db.query(BookCopy).filter(BookCopy.barcode == "BC-NEW-002").first()
        assert copy is not None


class TestF43AdminScanFulfill:
    def test_admin_fulfill_with_barcode_only_ok(self):
        """F43：管理端扫码取书只提交 {barcode} 不再 422（此前 schema 强制 reservation_id/child_id）"""
        from datetime import datetime, timedelta, timezone

        from fastapi.testclient import TestClient
        from jose import jwt
        from sqlalchemy.pool import StaticPool

        from backend.config import get_settings
        from backend.database import get_db
        from backend.domain.admin.models import Admin
        from backend.domain.admin.rbac_models import Role
        from backend.main import app
        from backend.seeds.seed_rbac import (
            seed_permissions,
            seed_role_permissions,
            seed_roles,
        )

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        from backend.events.registry import register_event_handlers

        register_event_handlers()

        def override_get_db():
            try:
                yield session
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)
        try:
            user, child, book = _seed(session)
            session.add(
                Reservation(
                    id=1,
                    child_id=child.id,
                    book_id=1,
                    status=ReservationStatus.PENDING,
                    expire_time=datetime.now() + timedelta(hours=72),
                )
            )
            seed_roles(session)
            seed_permissions(session)
            seed_role_permissions(session)
            session.flush()
            role = session.query(Role).filter(Role.code == "staff").first()
            admin = Admin(
                username="f43_admin",
                name="扫码取书",
                admin_role_id=role.id,
                password_hash="x",
            )
            session.add(admin)
            session.commit()
            settings = get_settings()
            token = jwt.encode(
                {
                    "sub": str(admin.id),
                    "role": 1,
                    "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                    "type": "admin",
                    "jti": "f43-scan",
                    "gen": 0,
                },
                settings.SECRET_KEY,
                algorithm=settings.ALGORITHM,
            )
            r = client.post(
                "/admin/api/reservations/fulfill",
                json={"barcode": "BC-F40-001"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200, r.text
            from backend.domain.borrow.models import BorrowRecord

            record = (
                session.query(BorrowRecord).filter(BorrowRecord.child_id == 1).first()
            )
            assert record is not None
            assert record.book_copy_id == 1
        finally:
            app.dependency_overrides.clear()
            session.close()
