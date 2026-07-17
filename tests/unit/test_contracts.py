"""前后端字段契约校验 — 审计确认的 9 页 + 核心接口

验证前端引用的关键字段在后端 Schema 中存在。
"""

from backend.domain.book.schemas import BookResponse
from backend.domain.deposit.schemas import DepositResponse
from backend.domain.refund.schemas import RefundResponse
from backend.domain.activity.schemas import ActivityResponse
from backend.domain.bookshelf.schemas import BookshelfResponse, FavoriteResponse
from backend.domain.reservation.schemas import ReservationResponse
from backend.domain.certificate.schemas import CertificateResponse
from backend.domain.profile.schemas import ProfileResponse
from backend.domain.admin.admin_schemas import ConfigResponse


SCHEMAS = {
    "BookResponse": BookResponse,
    "DepositResponse": DepositResponse,
    "RefundResponse": RefundResponse,
    "ActivityResponse": ActivityResponse,
    "BookshelfResponse": BookshelfResponse,
    "FavoriteResponse": FavoriteResponse,
    "ReservationResponse": ReservationResponse,
    "CertificateResponse": CertificateResponse,
    "ProfileResponse": ProfileResponse,
    "ConfigResponse": ConfigResponse,
}


def test_book_response():
    expected = {"title", "author", "cover", "ar_value", "word_count",
                "total_pages", "isbn", "age_min", "age_max",
                "available_copies", "total_copies",
                "audio_narrator", "audio_duration"}
    missing = [f for f in expected if f not in BookResponse.model_fields]
    assert not missing, f"BookResponse missing: {missing}"


def test_deposit_response():
    expected = {"child_id", "amount", "status", "pay_time", "pay_order_id",
                "refund_time", "refund_amount", "deduct_amount", "deduct_reason"}
    missing = [f for f in expected if f not in DepositResponse.model_fields]
    assert not missing, f"DepositResponse missing: {missing}"


def test_refund_response():
    expected = {"order_id", "child_id", "refund_amount", "reason", "status",
                "reviewer_id", "review_time", "review_comment",
                "actual_refund_amount", "create_time"}
    missing = [f for f in expected if f not in RefundResponse.model_fields]
    assert not missing, f"RefundResponse missing: {missing}"


def test_activity_response():
    expected = {"id", "title", "type", "price", "start_time", "end_time",
                "location", "description", "status", "max_participants",
                "current_participants"}
    missing = [f for f in expected if f not in ActivityResponse.model_fields]
    assert not missing, f"ActivityResponse missing: {missing}"


def test_bookshelf_response():
    expected = {"book_title", "book_cover", "title", "author",
                "ar_value", "word_count", "cover_emoji", "cover_bg"}
    missing = [f for f in expected if f not in BookshelfResponse.model_fields]
    assert not missing, f"BookshelfResponse missing: {missing}"


def test_favorite_response():
    expected = {"book_title", "book_cover", "title", "author",
                "ar_value", "create_time"}
    missing = [f for f in expected if f not in FavoriteResponse.model_fields]
    assert not missing, f"FavoriteResponse missing: {missing}"


def test_reservation_response():
    expected = {"child_id", "book_id", "venue_id", "status", "expire_time",
                "fulfilled_time", "borrow_record_id", "create_time"}
    missing = [f for f in expected if f not in ReservationResponse.model_fields]
    assert not missing, f"ReservationResponse missing: {missing}"


def test_certificate_response():
    expected = {"child_name", "level_name", "badge_emoji",
                "certificate_no", "create_time"}
    missing = [f for f in expected if f not in CertificateResponse.model_fields]
    assert not missing, f"CertificateResponse missing: {missing}"


def test_profile_response():
    expected = {"name", "english_name", "current_level", "total_books_finished",
                "total_words_read", "total_reading_minutes",
                "current_streak_days", "achievement_count"}
    missing = [f for f in expected if f not in ProfileResponse.model_fields]
    assert not missing, f"ProfileResponse missing: {missing}"


def test_config_response():
    assert "items" in ConfigResponse.model_fields
