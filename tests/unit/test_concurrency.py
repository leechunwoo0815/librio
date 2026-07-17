import tempfile
import os
import threading
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.database import Base
from backend.domain.book.models import Book, BookCopy

from backend.domain.borrow.models import BorrowRecord
from backend.domain.deposit.models import DepositRecord
from backend.domain.child.models import Child
from backend.domain.user.models import User
from backend.domain.advancement.models import QuestionBank, Quiz
from backend.domain.admin.models import SystemConfig
from backend.domain.reservation.service import ReservationService
from backend.domain.borrow.service import BorrowService
from backend.domain.deposit.service import DepositService
from backend.domain.advancement.service import AdvancementService
from backend.domain.reservation.schemas import ReservationCreateRequest
from backend.domain.borrow.schemas import ReturnBookRequest
from backend.domain.deposit.schemas import DepositDeductRequest, DepositRefundRequest
from backend.common.types import BorrowStatus, DepositStatus
from backend.bootstrap import register_event_handlers


def _seed_system_configs(session):
    for key, (value, config_type, desc) in SystemConfig.DEFAULTS.items():
        session.add(SystemConfig(config_key=key, config_value=value, config_type=config_type, description=desc))
    session.commit()


def _seed_user_child(session):
    u = User(openid='concurrency_test', phone='13800138000')
    session.add(u)
    session.flush()
    c = Child(name='并发测试', user_id=u.id, english_name='Test', age=8, grade='二年级',
              status=Child.STATUS_OFFICIAL, deposit_status=DepositStatus.PAID,
              total_words_read=0)
    session.add(c)
    session.flush()
    return u.id, c.id


@pytest.fixture
def file_db():
    db_path = tempfile.mktemp(suffix='.db')
    engine = create_engine(f'sqlite:///{db_path}', connect_args={'check_same_thread': False})
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()
    try:
        os.unlink(db_path)
    except OSError:
        pass


def _new_session(engine):
    return Session(bind=engine)


class TestConcurrencyReservation:
    def test_reservation_no_oversell(self, file_db):
        engine = file_db
        s = _new_session(engine)
        _seed_system_configs(s)
        uid, cid = _seed_user_child(s)
        b = Book(title='Test Book', author='Author', isbn='9780000000001',
                 total_stock=5, available_stock=5, offline_available=1,
                 ar_value=Decimal('2.0'), age_min=5, age_max=9, word_count=1000)
        s.add(b)
        s.commit()
        bid = b.id
        s.close()

        register_event_handlers()

        results = []
        errors = []
        lock = threading.Lock()

        def try_reserve():
            session = _new_session(engine)
            try:
                svc = ReservationService(session)
                svc.create_reservation(ReservationCreateRequest(child_id=cid, book_id=bid))
                with lock:
                    results.append(True)
            except Exception as e:
                with lock:
                    errors.append(str(e))
            finally:
                session.close()

        threads = [threading.Thread(target=try_reserve) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) <= 5, f"Oversell: {len(results)} reservations on 5 stock, errors: {errors[:5]}"
        assert len(results) >= 1, f"No reservations succeeded: {errors[:5]}"

    def test_borrow_dedup(self, file_db):
        engine = file_db
        s = _new_session(engine)
        _seed_system_configs(s)
        uid, cid = _seed_user_child(s)
        b = Book(title='Dedup Book', author='Author', isbn='9780000000002',
                 total_stock=1, available_stock=1, offline_available=1,
                 ar_value=Decimal('2.0'), age_min=5, age_max=9, word_count=1000)
        s.add(b)
        s.flush()
        bid = b.id
        copy = BookCopy(book_id=bid, barcode='DEDUP001', status=0)
        s.add(copy)
        s.commit()
        s.close()

        register_event_handlers()

        results = []
        errors = []
        lock = threading.Lock()

        def try_borrow():
            session = _new_session(engine)
            try:
                svc = BorrowService(session)
                svc.scan_and_borrow(cid, 'DEDUP001')
                with lock:
                    results.append(True)
            except Exception as e:
                with lock:
                    errors.append(str(e))
            finally:
                session.close()

        threads = [threading.Thread(target=try_borrow) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 1, f"Expected 1 borrow, got {len(results)}, errors: {errors[:5]}"

        s = _new_session(engine)
        b2 = s.query(Book).filter(Book.id == bid).first()
        assert b2.available_stock == 0, f"Stock should be 0, got {b2.available_stock}"
        s.close()

    def test_return_dedup(self, file_db):
        engine = file_db
        s = _new_session(engine)
        _seed_system_configs(s)
        uid, cid = _seed_user_child(s)
        b = Book(title='Return Dedup', author='Author', isbn='9780000000003',
                 total_stock=1, available_stock=1, offline_available=1,
                 ar_value=Decimal('2.0'), age_min=5, age_max=9, word_count=1000)
        s.add(b)
        s.flush()
        bid = b.id
        br = BorrowRecord(child_id=cid, book_id=bid, borrow_time=datetime.now(),
                          due_date=datetime.now() + timedelta(days=21),
                          status=BorrowStatus.BORROWING)
        s.add(br)
        s.commit()
        br_id = br.id
        s.close()

        register_event_handlers()

        results = []
        errors = []
        lock = threading.Lock()

        def try_return():
            session = _new_session(engine)
            try:
                svc = BorrowService(session)
                svc.return_book(ReturnBookRequest(borrow_record_id=br_id))
                with lock:
                    results.append(True)
            except Exception as e:
                with lock:
                    errors.append(str(e))
            finally:
                session.close()

        threads = [threading.Thread(target=try_return) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) >= 1, f"No returns succeeded, errors: {errors[:5]}"

        s = _new_session(engine)
        br_check = s.query(BorrowRecord).filter(BorrowRecord.id == br_id).first()
        assert br_check.status == BorrowStatus.RETURNED
        assert br_check.return_time is not None
        s.close()

    def test_deposit_no_illegal_transition(self, file_db):
        engine = file_db
        s = _new_session(engine)
        _seed_system_configs(s)
        uid, cid = _seed_user_child(s)
        d = DepositRecord(child_id=cid, amount=Decimal('1200.00'), status=DepositStatus.PAID)
        s.add(d)
        s.commit()
        s.close()

        register_event_handlers()

        results = {'refund': 0, 'deduct': 0}
        errors = []
        lock = threading.Lock()

        def try_refund():
            session = _new_session(engine)
            try:
                svc = DepositService(session)
                svc.refund_deposit(DepositRefundRequest(child_id=cid))
                with lock:
                    results['refund'] += 1
            except Exception as e:
                with lock:
                    errors.append(f"refund: {e}")
            finally:
                session.close()

        def try_deduct():
            session = _new_session(engine)
            try:
                svc = DepositService(session)
                svc.deduct_deposit(DepositDeductRequest(child_id=cid, amount=Decimal('100'), reason='test'))
                with lock:
                    results['deduct'] += 1
            except Exception as e:
                with lock:
                    errors.append(f"deduct: {e}")
            finally:
                session.close()

        threads = [threading.Thread(target=try_refund) for _ in range(25)]
        threads += [threading.Thread(target=try_deduct) for _ in range(25)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        s = _new_session(engine)
        deposit = s.query(DepositRecord).filter(
            DepositRecord.child_id == cid, DepositRecord.is_deleted == 0
        ).first()
        assert deposit is not None
        assert deposit.status in (DepositStatus.REFUND_PENDING, DepositStatus.DEDUCTED), \
            f"Expected REFUND_PENDING or DEDUCTED, got {deposit.status}"
        assert results['refund'] + results['deduct'] >= 1, \
            f"No operations succeeded, errors: {errors[:5]}"

        s.close()

    def test_score_anti_cheat(self, file_db):
        engine = file_db
        s = _new_session(engine)
        _seed_system_configs(s)
        uid, cid = _seed_user_child(s)
        b = Book(title='AntiCheat Book', author='Author', isbn='9780000000004',
                 total_stock=1, available_stock=1, offline_available=1,
                 ar_value=Decimal('2.0'), age_min=5, age_max=9, word_count=5000)
        s.add(b)
        s.flush()
        bid = b.id

        q1 = QuestionBank(book_id=bid, question_text='Q1', option_a='A', option_b='B', correct_answer='A')
        q2 = QuestionBank(book_id=bid, question_text='Q2', option_a='A', option_b='B', correct_answer='B')
        s.add_all([q1, q2])
        s.flush()

        quiz_ids = []
        for _ in range(50):
            quiz = Quiz(child_id=cid, book_id=bid, status=Quiz.STATUS_IN_PROGRESS, total_questions=2)
            s.add(quiz)
            s.flush()
            quiz_ids.append(quiz.id)

        s.commit()
        q1_id, q2_id = q1.id, q2.id
        s.close()

        register_event_handlers()

        results = []
        lock = threading.Lock()

        def try_pass(quiz_id):
            session = _new_session(engine)
            try:
                svc = AdvancementService(session)
                answers = [
                    type('Answer', (), {'question_id': q1_id, 'selected_answer': 'A'}),
                    type('Answer', (), {'question_id': q2_id, 'selected_answer': 'B'}),
                ]
                result = svc.submit_answers(quiz_id, answers)
                with lock:
                    results.append(result)
            except Exception:
                pass
            finally:
                session.close()

        threads = [threading.Thread(target=try_pass, args=(qid,)) for qid in quiz_ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        s = _new_session(engine)
        child = s.query(Child).filter(Child.id == cid).first()
        assert child.total_words_read == 5000, f"Expected 5000 words, got {child.total_words_read}"
        s.close()
