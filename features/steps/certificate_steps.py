# features/steps/certificate_steps.py
"""晋级证书BDD步骤"""

from behave import given, when, then
from backend.domain.advancement.models import Level, ChildLevel
from backend.domain.certificate.models import LevelCertificate
from backend.domain.certificate.service import CertificateService


def _ensure_levels(context):
    """确保A级和B级存在"""
    level_a = context.db.query(Level).filter(Level.name == "A").first()
    if not level_a:
        level_a = Level(name="A", sort_order=1, required_books=10,
                        max_borrow_count=20, badge_emoji="🌱")
        context.db.add(level_a); context.db.commit()
    level_b = context.db.query(Level).filter(Level.name == "B").first()
    if not level_b:
        level_b = Level(name="B", sort_order=2, required_books=15,
                        max_borrow_count=20, badge_emoji="🌿")
        context.db.add(level_b); context.db.commit()
    context.level_a = level_a
    context.level_b = level_b


@given(u'孩子从A级晋级到B级')
def step_advance_a_to_b(context):
    _ensure_levels(context)
    context.child.english_name = "Tom"
    context.db.commit()


@when(u'系统生成晋级证书')
def step_generate_cert(context):
    svc = CertificateService(context.db)
    context.certificate = svc.generate_certificate(context.child.id, context.level_b.id)


@then(u'生成一张证书')
def step_cert_generated(context):
    assert context.certificate is not None
    assert context.certificate["id"] is not None


@then(u'证书包含孩子姓名')
def step_cert_has_name(context):
    assert context.certificate["child_name"] == context.child.name


@then(u'证书包含级别信息"{level_name}"')
def step_cert_has_level(context, level_name):
    assert context.certificate["level_name"] == level_name


@given(u'孩子已有B级证书')
def step_has_b_cert(context):
    _ensure_levels(context)
    svc = CertificateService(context.db)
    context.existing_cert = svc.generate_certificate(context.child.id, context.level_b.id)


@when(u'再次请求生成B级证书')
def step_generate_again(context):
    svc = CertificateService(context.db)
    context.certificate = svc.generate_certificate(context.child.id, context.level_b.id)


@then(u'返回已有的证书')
def step_return_existing(context):
    assert context.certificate["id"] == context.existing_cert["id"]


@given(u'孩子已获得晋级证书')
def step_has_cert(context):
    _ensure_levels(context)
    context.child.english_name = "Tom"
    context.db.commit()
    svc = CertificateService(context.db)
    svc.generate_certificate(context.child.id, context.level_b.id)


@when(u'查看证书详情')
def step_view_cert(context):
    svc = CertificateService(context.db)
    certs = svc.get_child_certificates(context.child.id)
    context.certificate = certs[0] if certs else None


@then(u'证书包含孩子英文名')
def step_cert_has_english_name(context):
    assert context.certificate["child_english_name"] == "Tom"


@then(u'证书包含晋级日期')
def step_cert_has_date(context):
    assert context.certificate["create_time"] is not None


@then(u'证书包含徽章')
def step_cert_has_badge(context):
    assert context.certificate["badge_emoji"] is not None


@given(u'孩子已获得2张晋级证书')
def step_has_2_certs(context):
    _ensure_levels(context)
    svc = CertificateService(context.db)
    svc.generate_certificate(context.child.id, context.level_a.id)
    svc.generate_certificate(context.child.id, context.level_b.id)


@when(u'查询孩子的证书列表')
def step_list_certs(context):
    svc = CertificateService(context.db)
    context.cert_list = svc.get_child_certificates(context.child.id)


@then(u'返回2张证书')
def step_list_count_2(context):
    assert len(context.cert_list) == 2


@given(u'孩子尚无晋级证书')
def step_no_certs(context):
    # 确保孩子没有证书记录
    from backend.domain.certificate.models import LevelCertificate
    existing = context.db.query(LevelCertificate).filter(
        LevelCertificate.child_id == context.child.id
    ).count()
    assert existing == 0


@then(u'返回空列表')
def step_empty_list(context):
    assert len(context.cert_list) == 0
