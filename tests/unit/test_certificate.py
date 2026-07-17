# tests/unit/test_certificate.py
"""晋级证书服务测试"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.advancement.models import Level
from backend.domain.certificate.service import CertificateService


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _setup(db):
    user = User(openid="cert_user", phone="13800138004")
    db.add(user)
    db.commit()

    child = Child(
        user_id=user.id,
        name="小明",
        age=7,
        grade="二年级",
        english_name="Tom",
        status=Child.STATUS_OFFICIAL,
    )
    db.add(child)
    db.commit()

    level_a = Level(
        name="A", sort_order=1, required_books=10, max_borrow_count=20, badge_emoji="🌱"
    )
    level_b = Level(
        name="B", sort_order=2, required_books=15, max_borrow_count=20, badge_emoji="🌿"
    )
    db.add_all([level_a, level_b])
    db.commit()

    return user, child, level_a, level_b


def test_generate_certificate(db):
    """生成晋级证书"""
    user, child, level_a, level_b = _setup(db)
    svc = CertificateService(db)
    cert = svc.generate_certificate(child.id, level_b.id)

    assert cert["child_name"] == "小明"
    assert cert["child_english_name"] == "Tom"
    assert cert["level_name"] == "B"
    assert cert["badge_emoji"] == "🌿"
    assert cert["certificate_no"] is not None
    assert cert["certificate_no"].startswith("MW-")


def test_no_duplicate_certificate(db):
    """同级不重复生成"""
    user, child, level_a, level_b = _setup(db)
    svc = CertificateService(db)
    cert1 = svc.generate_certificate(child.id, level_b.id)
    cert2 = svc.generate_certificate(child.id, level_b.id)
    assert cert1["id"] == cert2["id"]


def test_get_certificate(db):
    """获取证书详情"""
    user, child, level_a, level_b = _setup(db)
    svc = CertificateService(db)
    cert = svc.generate_certificate(child.id, level_b.id)

    fetched = svc.get_certificate(cert["id"])
    assert fetched is not None
    assert fetched["level_name"] == "B"


def test_get_child_certificates(db):
    """获取孩子所有证书"""
    user, child, level_a, level_b = _setup(db)
    svc = CertificateService(db)
    svc.generate_certificate(child.id, level_a.id)
    svc.generate_certificate(child.id, level_b.id)

    certs = svc.get_child_certificates(child.id)
    assert len(certs) == 2


def test_empty_certificates(db):
    """无证书时返回空列表"""
    user, child, level_a, level_b = _setup(db)
    svc = CertificateService(db)
    certs = svc.get_child_certificates(child.id)
    assert len(certs) == 0


def test_certificate_number_unique(db):
    """证书编号唯一"""
    user, child, level_a, level_b = _setup(db)
    svc = CertificateService(db)
    cert1 = svc.generate_certificate(child.id, level_a.id)
    cert2 = svc.generate_certificate(child.id, level_b.id)
    assert cert1["certificate_no"] != cert2["certificate_no"]
