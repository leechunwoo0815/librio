"""HTTP layer tests for 4 new routes — auth, serialization, parameter validation"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.database import Base, get_db
from backend.main import app
from backend.common.types import DepositStatus, BorrowStatus
from backend.middleware.auth import create_access_token

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@pytest.fixture
def http():
    Base.metadata.create_all(bind=_engine)
    Session = sessionmaker(bind=_engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    db = Session()
    yield client, db
    Base.metadata.drop_all(bind=_engine)
    app.dependency_overrides.clear()
    db.close()


def _create_user(db, openid="p1", phone="13800138001"):
    from backend.domain.user.models import User

    user = User(openid=openid, phone=phone, parent_name="测试")
    db.add(user)
    db.flush()
    return user


def _create_child(db, user, name="孩子"):
    from backend.domain.child.models import Child

    child = Child(
        user_id=user.id,
        name=name,
        age=6,
        grade="一",
        status=2,
        deposit_status=DepositStatus.PAID,
    )
    db.add(child)
    db.flush()
    return child


def _create_book(db, title="书", theme="主题"):
    from backend.domain.book.models import Book

    book = Book(
        title=title,
        author="A",
        isbn=f"978{abs(hash(title)) % 10**10:010d}",
        ar_value=3.5,
        age_min=6,
        age_max=12,
        theme=theme,
        is_published=1,
    )
    db.add(book)
    db.flush()
    return book


def _auth(user):
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


# ══════════════════════════════════════════════════════════════
# GET /child/transfer/records
# ══════════════════════════════════════════════════════════════


class TestTransferRecordsHTTP:
    def test_requires_auth(self, http):
        client, _ = http
        r = client.get("/child/transfer/records")
        assert r.status_code == 401

    def test_returns_records(self, http):
        from backend.domain.child.benefit_transfer_model import (
            BenefitTransferApplication,
        )

        client, db = http
        user = _create_user(db)
        src = _create_child(db, user, "源")
        tgt = _create_child(db, user, "目")
        db.add(
            BenefitTransferApplication(
                source_child_id=src.id,
                target_child_id=tgt.id,
                user_id=user.id,
                status=0,
            )
        )
        db.commit()

        r = client.get("/child/transfer/records", headers=_auth(user))
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["source_child_name"] == "源"
        assert data[0]["target_child_name"] == "目"
        assert data[0]["status"] == "pending"

    def test_empty(self, http):
        client, db = http
        user = _create_user(db)
        r = client.get("/child/transfer/records", headers=_auth(user))
        assert r.status_code == 200
        assert r.json() == []

    def test_soft_deleted_excluded(self, http):
        from backend.domain.child.benefit_transfer_model import (
            BenefitTransferApplication,
        )

        client, db = http
        user = _create_user(db)
        src = _create_child(db, user, "源")
        tgt = _create_child(db, user, "目")
        app = BenefitTransferApplication(
            source_child_id=src.id, target_child_id=tgt.id, user_id=user.id, status=1
        )
        app.soft_delete()
        db.add(app)
        db.commit()

        r = client.get("/child/transfer/records", headers=_auth(user))
        assert r.json() == []

    def test_ordered_newest_first(self, http):
        from backend.domain.child.benefit_transfer_model import (
            BenefitTransferApplication,
        )
        from datetime import datetime

        client, db = http
        user = _create_user(db)
        src = _create_child(db, user, "源")
        tgt = _create_child(db, user, "目")
        a1 = BenefitTransferApplication(
            source_child_id=src.id,
            target_child_id=tgt.id,
            user_id=user.id,
            status=0,
            create_time=datetime(2020, 1, 1),
        )
        db.add(a1)
        db.flush()
        a2 = BenefitTransferApplication(
            source_child_id=src.id,
            target_child_id=tgt.id,
            user_id=user.id,
            status=0,
            create_time=datetime(2020, 6, 1),
        )
        db.add(a2)
        db.commit()

        r = client.get("/child/transfer/records", headers=_auth(user))
        ids = [item["id"] for item in r.json()]
        assert ids == sorted(ids, reverse=True)

    def test_status_map_full(self, http):
        from backend.domain.child.benefit_transfer_model import (
            BenefitTransferApplication,
        )

        client, db = http
        user = _create_user(db)
        src = _create_child(db, user, "源")
        tgt = _create_child(db, user, "目")
        for s in (0, 1, 2):
            db.add(
                BenefitTransferApplication(
                    source_child_id=src.id,
                    target_child_id=tgt.id,
                    user_id=user.id,
                    status=s,
                )
            )
        db.commit()

        r = client.get("/child/transfer/records", headers=_auth(user))
        statuses = {item["status"] for item in r.json()}
        assert statuses == {"pending", "approved", "rejected"}


# ══════════════════════════════════════════════════════════════
# GET /book/{book_id}/related
# ══════════════════════════════════════════════════════════════


class TestRelatedBooksHTTP:
    def test_public_endpoint(self, http):
        client, _ = http
        r = client.get("/book/99999/related")
        assert r.status_code == 404

    def test_returns_related(self, http):
        client, db = http
        book = _create_book(db, "主", "文学")
        _create_book(db, "相关", "文学")
        _create_book(db, "无关", "科学")
        db.commit()

        r = client.get(f"/book/{book.id}/related")
        titles = {b["title"] for b in r.json()}
        assert "相关" in titles
        assert "无关" not in titles

    def test_empty(self, http):
        client, db = http
        book = _create_book(db, "唯一")
        db.commit()
        r = client.get(f"/book/{book.id}/related")
        assert r.json() == []

    def test_nonexistent_book(self, http):
        client, _ = http
        r = client.get("/book/99999/related")
        assert r.status_code == 404


# ══════════════════════════════════════════════════════════════
# GET /reading/checkin/{child_id}/records
# ══════════════════════════════════════════════════════════════


class TestCheckinRecordsHTTP:
    def test_requires_auth(self, http):
        client, _ = http
        r = client.get("/reading/checkin/1/records")
        assert r.status_code == 401

    def test_returns_records(self, http):
        from backend.domain.reading.models import ReadingSession
        from datetime import datetime

        client, db = http
        user = _create_user(db)
        child = _create_child(db, user)
        book = _create_book(db)
        session = ReadingSession(
            child_id=child.id,
            book_id=book.id,
            start_time=datetime.now(),
            duration_seconds=300,
            pages_read=15,
        )
        db.add(session)
        db.commit()

        r = client.get(f"/reading/checkin/{child.id}/records", headers=_auth(user))
        assert r.status_code == 200
        assert r.json()[0]["book_name"] == "书"
        assert r.json()[0]["pages"] == "15页"

    def test_empty(self, http):
        client, db = http
        user = _create_user(db)
        child = _create_child(db, user)
        r = client.get(f"/reading/checkin/{child.id}/records", headers=_auth(user))
        assert r.json() == []

    def test_forbidden_other_child(self, http):
        client, db = http
        user1 = _create_user(db, "p1", "13800138001")
        user2 = _create_user(db, "p2", "13800138002")
        child = _create_child(db, user1)
        r = client.get(f"/reading/checkin/{child.id}/records", headers=_auth(user2))
        assert r.status_code == 403


# ══════════════════════════════════════════════════════════════
# DELETE /child/{child_id}
# ══════════════════════════════════════════════════════════════


class TestDeleteChildHTTP:
    def test_requires_auth(self, http):
        client, _ = http
        r = client.delete("/child/1")
        assert r.status_code == 401

    def test_delete_own_child(self, http):
        client, db = http
        user = _create_user(db)
        child = _create_child(db, user)
        db.commit()

        r = client.delete(f"/child/{child.id}", headers=_auth(user))
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_forbidden_other_child(self, http):
        client, db = http
        user1 = _create_user(db, "p1", "13800138001")
        user2 = _create_user(db, "p2", "13800138002")
        child = _create_child(db, user1)
        db.commit()

        r = client.delete(f"/child/{child.id}", headers=_auth(user2))
        assert r.status_code == 403

    def test_nonexistent_child(self, http):
        client, db = http
        user = _create_user(db)
        r = client.delete("/child/99999", headers=_auth(user))
        assert r.status_code == 404

    def test_blocked_by_active_borrow(self, http):
        from backend.domain.borrow.models import BorrowRecord
        from datetime import datetime

        client, db = http
        user = _create_user(db)
        child = _create_child(db, user)
        book = _create_book(db)
        db.add(
            BorrowRecord(
                child_id=child.id,
                book_id=book.id,
                status=BorrowStatus.BORROWING,
                borrow_time=datetime.now(),
                due_date=datetime.now(),
            )
        )
        db.commit()

        r = client.delete(f"/child/{child.id}", headers=_auth(user))
        assert r.status_code == 422

    def test_blocked_by_overdue_borrow(self, http):
        from backend.domain.borrow.models import BorrowRecord
        from datetime import datetime

        client, db = http
        user = _create_user(db)
        child = _create_child(db, user)
        book = _create_book(db)
        db.add(
            BorrowRecord(
                child_id=child.id,
                book_id=book.id,
                status=BorrowStatus.OVERDUE,
                borrow_time=datetime.now(),
                due_date=datetime.now(),
            )
        )
        db.commit()

        r = client.delete(f"/child/{child.id}", headers=_auth(user))
        assert r.status_code == 422

    def test_already_deleted_returns_404(self, http):
        client, db = http
        user = _create_user(db)
        child = _create_child(db, user)
        child.soft_delete()
        db.commit()

        r = client.delete(f"/child/{child.id}", headers=_auth(user))
        assert r.status_code == 404


# ══════════════════════════════════════════════════════════════
# Order payment callback via encrypted gateway path (P0)
# ══════════════════════════════════════════════════════════════


def test_order_callback_via_encrypted_branch():
    """
    [What] 订单支付回调 — 走真实网关加密解密分支（resource wrapped）
    [Why] 测试盲区：mock 回调走 else 明文分支，未覆盖加密解密路径
    [How] 构造 resource 格式请求通过 MockPaymentGateway 解密，验证金额匹配
    """
    import os

    os.environ["MOCK_PAYMENT"] = "true"

    import backend.config

    backend.config.get_settings.cache_clear()

    from decimal import Decimal

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from fastapi.testclient import TestClient

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    db = Session()

    try:
        from backend.domain.user.models import User
        from backend.domain.child.models import Child
        from backend.domain.order.models import Order, PayStatus

        user = User(openid="cb_enc_test", phone="13800000000", parent_name="测试")
        db.add(user)
        db.flush()

        child = Child(user_id=user.id, name="测试孩子", age=6, grade="一", status=2)
        db.add(child)
        db.flush()

        order = Order(
            order_no="CB_ENCRYPTED_TEST",
            user_id=user.id,
            child_id=child.id,
            type=1,
            amount=Decimal("99.00"),
        )
        db.add(order)
        db.commit()
        assert order.pay_status == Order.PAY_PENDING

        import json as _json

        resp = client.post(
            "/order/payment-callback",
            json={
                "resource": {
                    "ciphertext": _json.dumps(
                        {
                            "out_trade_no": "CB_ENCRYPTED_TEST",
                            "amount": 9900,  # 99元 = 9900分
                        }
                    ),
                    "nonce": "mock_nonce",
                    "associated_data": "",
                }
            },
            headers={
                "wechatpay-signature": "mock_sig",
                "wechatpay-timestamp": "1234567890",
                "wechatpay-nonce": "mock_nonce",
            },
        )

        assert resp.status_code == 200, f"callback failed: {resp.text}"

        db.expire_all()
        order = (
            db.query(Order)
            .filter(Order.order_no == "CB_ENCRYPTED_TEST")
            .first()
        )
        assert order is not None
        assert order.pay_status == PayStatus.PAID, (
            f"order not paid: status={order.pay_status}"
        )
    finally:
        db.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
