"""批次5 F-113 评估字段校验（score 范围/status 枚举/AR 倒挂/teacher 存在性）"""

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.domain.assessment.schemas import (
    AssessmentCreateRequest,
    AssessmentUpdateRequest,
)
from backend.domain.assessment.service import AssessmentService
from backend.domain.child.models import Child
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestSchemaValidation:
    def test_score_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            AssessmentCreateRequest(child_id=1, comprehension_score=999)
        with pytest.raises(ValidationError):
            AssessmentCreateRequest(child_id=1, comprehension_score=-1)

    def test_status_free_string_rejected(self):
        with pytest.raises(ValidationError):
            AssessmentCreateRequest(child_id=1, status="whatever")

    def test_ar_level_inverted_rejected(self):
        with pytest.raises(ValidationError, match="ar_level_after"):
            AssessmentCreateRequest(
                child_id=1, ar_level_before=3.5, ar_level_after=2.0
            )

    def test_update_score_range(self):
        with pytest.raises(ValidationError):
            AssessmentUpdateRequest(comprehension_score=101)
        assert AssessmentUpdateRequest(comprehension_score=100).comprehension_score == 100


class TestServiceTeacherExistence:
    def test_create_with_missing_teacher_rejected(self, db):
        from backend.common.exceptions import ValidationError as BizValidationError

        user = User(openid="f113", phone="13800011300")
        db.add(user)
        db.commit()
        child = Child(user_id=user.id, name="评估", age=7, grade="二年级")
        db.add(child)
        db.commit()

        with pytest.raises(BizValidationError, match="老师不存在"):
            AssessmentService(db).create_assessment(
                AssessmentCreateRequest(
                    child_id=child.id, teacher_id=999, status="completed"
                )
            )
