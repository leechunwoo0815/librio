"""
Verify all ORM models are self-consistent and can create their schema on SQLite.
This is a lightweight alternative to `alembic check` that works without MySQL.
"""
import sys
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["MOCK_PAYMENT"] = "true"
os.environ["MOCK_SMS"] = "true"

from sqlalchemy import create_engine
from backend.database import Base

# Import all domain models to register them with Base.metadata
from backend.domain.user.models import User  # noqa: F401
from backend.domain.child.models import Child  # noqa: F401
from backend.domain.child.benefit_transfer_model import BenefitTransferApplication  # noqa: F401
from backend.domain.book.models import Book, BookCopy  # noqa: F401
from backend.domain.bookshelf.models import Bookshelf, Favorites  # noqa: F401
from backend.domain.reading.models import BookPage, ReadingProgress, ReadingSession, CheckIn  # noqa: F401
from backend.domain.vocabulary.models import DictionaryWord, UserVocabulary  # noqa: F401
from backend.domain.advancement.models import Level, ChildLevel, ReadingSubmission, QuestionBank, Quiz, QuizAnswer, Achievement, ChildAchievement  # noqa: F401
from backend.domain.order.models import Order  # noqa: F401
from backend.domain.refund.models import RefundApplication  # noqa: F401
from backend.domain.borrow.models import BorrowRecord  # noqa: F401
from backend.domain.deposit.models import DepositRecord  # noqa: F401
from backend.domain.reservation.models import Reservation  # noqa: F401
from backend.domain.report.models import ObservationReport, LearningReport  # noqa: F401
from backend.domain.certificate.models import LevelCertificate  # noqa: F401
from backend.domain.activity.models import Activity, ActivityEnrollment  # noqa: F401
from backend.domain.admin.models import Admin, OperationLog, SystemConfig, Teacher, TeacherSchedule, Venue  # noqa: F401
from backend.domain.admin.rbac_models import Role, Permission, RolePermission  # noqa: F401
from backend.domain.evaluation.models import AREvaluation, GuidanceRecord, ObservationEvaluation  # noqa: F401
from backend.domain.message.models import SystemMessage  # noqa: F401
from backend.domain.parent_course_time.models import ParentCourseTime  # noqa: F401
from backend.domain.quiz_question.models import QuizQuestion  # noqa: F401
from backend.domain.voice.models import VoiceRecording  # noqa: F401
from backend.domain.assessment.models import Assessment  # noqa: F401
from backend.domain.audio.models import AudioFile  # noqa: F401
from backend.common.dead_letter_model import DeadLetterEvent  # noqa: F401
from backend.common.config_audit_model import ConfigAuditLog  # noqa: F401

errors = []

try:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    tables = Base.metadata.tables
    print(f"OK: {len(tables)} tables created on SQLite")
except Exception as e:
    errors.append(f"Schema creation failed: {e}")

if errors:
    for err in errors:
        print(f"FAIL: {err}")
    sys.exit(1)

print("Model consistency check: PASSED")
