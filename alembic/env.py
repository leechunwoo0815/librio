from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Import all models so Alembic can detect them
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.database import Base

# Import all domain models to register them with Base.metadata
from backend.domain.user.models import User  # noqa: F401
from backend.domain.child.models import Child  # noqa: F401
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
from backend.domain.evaluation.models import AREvaluation, GuidanceRecord, ObservationEvaluation  # noqa: F401
from backend.domain.message.models import SystemMessage  # noqa: F401
from backend.domain.parent_course_time.models import ParentCourseTime  # noqa: F401
from backend.domain.quiz_question.models import QuizQuestion  # noqa: F401
from backend.domain.voice.models import VoiceRecording  # noqa: F401

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata to our Base
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
