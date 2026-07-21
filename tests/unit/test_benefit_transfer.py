"""权益转让校验单元测试 — T3.3"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.child.service import ChildService, assert_no_pending_transfer
from backend.domain.child.benefit_transfer_model import BenefitTransferApplication
from backend.common.exceptions import ValidationError
from backend.domain.borrow.models import BorrowRecord
from backend.common.types import BorrowStatus


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def child_service(db):
    return ChildService(db)


def _create_child(db, user_id, status=0, name="测试", fines=0):
    child = Child(
        user_id=user_id,
        name=name,
        age=6,
        grade="一年级",
        status=status,
        deposit_status=1,
        outstanding_fines=fines,
    )
    db.add(child)
    db.commit()
    return child


def _create_transfer_app(db, source_id, target_id, status=0, deleted=0):
    """创建转让申请记录"""
    from datetime import datetime
    app = BenefitTransferApplication(
        source_child_id=source_id,
        target_child_id=target_id,
        user_id=1,
        status=status,
        remark="",
        create_time=datetime.now(),
        update_time=datetime.now(),
        is_deleted=deleted,
    )
    db.add(app)
    db.commit()
    return app


class TestAssertNoPendingTransfer:
    """assert_no_pending_transfer 单元测试"""

    def test_no_record(self, db):
        """无任何转让记录 → 通过"""
        assert_no_pending_transfer(db, 1)

    def test_approved_as_source(self, db, child_service):
        """源孩子 APPROVED 记录 → 抛出异常"""
        user = User(openid="u1", phone="1")
        db.add(user)
        db.commit()
        src = _create_child(db, user.id, status=1)
        tgt = _create_child(db, user.id, status=0)
        _create_transfer_app(db, src.id, tgt.id, status=1)
        with pytest.raises(ValidationError, match="审核通过"):
            assert_no_pending_transfer(db, src.id)

    def test_approved_as_target(self, db):
        """目标孩子 APPROVED 记录 → 抛出异常"""
        user = User(openid="u2", phone="2")
        db.add(user)
        db.commit()
        src = _create_child(db, user.id, status=1)
        tgt = _create_child(db, user.id, status=0)
        _create_transfer_app(db, src.id, tgt.id, status=1)
        with pytest.raises(ValidationError, match="审核通过"):
            assert_no_pending_transfer(db, tgt.id)

    def test_rejected_record(self, db):
        """REJECTED 记录 → 通过"""
        user = User(openid="u3", phone="3")
        db.add(user)
        db.commit()
        src = _create_child(db, user.id, status=1)
        tgt = _create_child(db, user.id, status=0)
        _create_transfer_app(db, src.id, tgt.id, status=2)
        assert_no_pending_transfer(db, src.id)

    def test_pending_record(self, db, child_service):
        """PENDING 记录 → 抛出异常"""
        user = User(openid="u4", phone="4")
        db.add(user)
        db.commit()
        src = _create_child(db, user.id, status=1)
        tgt = _create_child(db, user.id, status=0)
        app = _create_transfer_app(db, src.id, tgt.id, status=0)
        with pytest.raises(ValidationError, match=f"申请ID={app.id}"):
            assert_no_pending_transfer(db, src.id)

    def test_soft_deleted_approved(self, db):
        """软删除的 APPROVED 记录 → 通过"""
        user = User(openid="u5", phone="5")
        db.add(user)
        db.commit()
        src = _create_child(db, user.id, status=1)
        tgt = _create_child(db, user.id, status=0)
        _create_transfer_app(db, src.id, tgt.id, status=1, deleted=1)
        assert_no_pending_transfer(db, src.id)


class TestValidateTransferTarget:
    """_validate_transfer 目标孩子校验测试"""

    def _setup_two_children(self, db, source_status=1, target_status=0):
        user = User(openid="ut1", phone="100")
        db.add(user)
        db.commit()
        src = _create_child(db, user.id, status=source_status)
        tgt = _create_child(db, user.id, status=target_status)
        return user, src, tgt

    def test_target_active_borrows(self, db, child_service):
        """目标孩子有活跃借阅 → 校验失败"""
        from datetime import datetime
        _, src, tgt = self._setup_two_children(db)
        borrow = BorrowRecord(
            child_id=tgt.id,
            book_id=1,
            status=BorrowStatus.BORROWING,
            borrow_time=datetime.now(),
            due_date=datetime.now(),
            is_deleted=0,
        )
        db.add(borrow)
        db.commit()
        with pytest.raises(ValidationError, match="未还书"):
            child_service._validate_transfer(src.id, tgt.id)

    def test_target_outstanding_fines(self, db, child_service):
        """目标孩子有未缴罚款 → 校验失败"""
        _, src, tgt = self._setup_two_children(db)
        tgt.outstanding_fines = 50
        db.commit()
        with pytest.raises(ValidationError, match="未缴罚款"):
            child_service._validate_transfer(src.id, tgt.id)

    def test_target_valid(self, db, child_service):
        """目标孩子校验通过 → 正常返回"""
        _, src, tgt = self._setup_two_children(db)
        result = child_service._validate_transfer(src.id, tgt.id)
        assert result is not None
        assert result[0].id == src.id
        assert result[1].id == tgt.id
