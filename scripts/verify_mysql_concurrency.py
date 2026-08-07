#!/usr/bin/env python
"""MySQL 并发安全真实验证（审查尾巴补齐）

SQLite 的 with_for_update() 是 no-op（项目陷阱清单已注明），test_concurrency.py
的 SQLite 线程测试不能证明 MySQL 下行锁/唯一索引真实生效。本脚本在真实 MySQL
独立测试库上验证三类并发兜底：
  A. 预约并发超卖：5 库存 × 100 孩子并发预约 → 成功数 ≤ 5（Book 行锁串行化）
  B. 副本并发双借：1 副本 × 50 孩子并发扫码借 → 成功数 = 1（F69 副本行锁）
  C. 押金活跃唯一索引：并发直插 2 条 PENDING 押金 → 第二条 IntegrityError
     （迁移 048 uq_deposit_active_child，F68 并发双单 DB 兜底）

用法：venv/bin/python scripts/verify_mysql_concurrency.py
可选：CONCURRENCY_DB_URL 覆盖测试库连接串；--keep 保留数据（默认清理）
"""

import os
import sys
import threading
import uuid
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MYSQL_URL = os.environ.get(
    "CONCURRENCY_DB_URL",
    "mysql+pymysql://root:@localhost:3306/dmkwords_concurrency_test?charset=utf8mb4",
)


def main():
    engine = create_engine(MYSQL_URL, pool_pre_ping=True, pool_size=8, max_overflow=8)

    # 导入 main 触发全部路由 → 全部模型注册到 Base.metadata（与 pytest 收集一致）
    import backend.main  # noqa: F401

    from backend.database import Base

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    from backend.bootstrap import register_event_handlers

    register_event_handlers()
    _seed_configs(Session)

    results = []
    results.append(("A 预约并发超卖（行锁）", _scenario_reservation_oversell(Session)))
    results.append(("B 副本并发双借（行锁）", _scenario_borrow_dedup(Session)))
    results.append(("C 押金活跃唯一索引（DB 兜底）", _scenario_deposit_unique(Session)))

    if "--keep" not in sys.argv:
        _cleanup(engine)

    ok = True
    print("\n========== MySQL 并发验证结果 ==========")
    for name, (passed, detail) in results:
        print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}")
        ok = ok and passed
    print("========================================")
    sys.exit(0 if ok else 1)


def _seed_configs(Session):
    from backend.domain.admin.models import SystemConfig

    s = Session()
    try:
        for key, (value, config_type, desc) in SystemConfig.DEFAULTS.items():
            exists = (
                s.query(SystemConfig).filter(SystemConfig.config_key == key).first()
            )
            if not exists:
                s.add(
                    SystemConfig(
                        config_key=key,
                        config_value=value,
                        config_type=config_type,
                        description=desc,
                    )
                )
        s.commit()
    finally:
        s.close()


def _make_user_child(s, openid):
    from backend.domain.child.models import Child
    from backend.domain.user.models import User

    u = User(openid=openid, phone=f"139{str(uuid.uuid4().int)[:8]}")
    s.add(u)
    s.flush()
    c = Child(
        user_id=u.id,
        name="并发",
        age=7,
        grade="一年级",
        status=Child.STATUS_OFFICIAL,
        deposit_status=1,
    )
    s.add(c)
    s.flush()
    return u.id, c.id


def _scenario_reservation_oversell(Session):
    from backend.domain.book.models import Book
    from backend.domain.reservation.schemas import ReservationCreateRequest
    from backend.domain.reservation.service import ReservationService

    s = Session()
    u, c0 = _make_user_child(s, f"rsv_{uuid.uuid4().hex[:8]}")
    b = Book(
        title="并发预约书",
        author="A",
        isbn=f"978{str(uuid.uuid4().int)[:13]}",
        total_stock=5,
        available_stock=5,
        offline_available=1,
        ar_value=Decimal("2.0"),
        age_min=5,
        age_max=9,
        word_count=500,
    )
    s.add(b)
    s.commit()
    bid = b.id
    s.close()

    child_ids = [c0]
    ok_count = 0
    errors = []
    lock = threading.Lock()

    def try_reserve(cid):
        nonlocal ok_count
        sess = Session()
        try:
            svc = ReservationService(sess)
            svc.create_reservation(ReservationCreateRequest(child_id=cid, book_id=bid))
            with lock:
                ok_count += 1
        except Exception as e:
            with lock:
                errors.append(str(e)[:80])
        finally:
            sess.close()

    # 100 个孩子（前 5 个预置，其余现场建）
    s = Session()
    for _ in range(99):
        _, cid = _make_user_child(s, f"rsv_{uuid.uuid4().hex[:8]}")
        child_ids.append(cid)
    s.commit()
    s.close()

    threads = [threading.Thread(target=try_reserve, args=(cid,)) for cid in child_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    passed = ok_count <= 5 and ok_count >= 1
    return passed, f"成功 {ok_count}/100（库存 5），错误样本: {errors[:2]}"


def _scenario_borrow_dedup(Session):
    from backend.domain.book.models import Book, BookCopy
    from backend.domain.borrow.service import BorrowService

    s = Session()
    u, c0 = _make_user_child(s, f"brw_{uuid.uuid4().hex[:8]}")
    b = Book(
        title="并发借书",
        author="A",
        isbn=f"978{str(uuid.uuid4().int)[:13]}",
        total_stock=1,
        available_stock=1,
        ar_value=Decimal("2.0"),
        age_min=5,
        age_max=9,
        word_count=300,
    )
    s.add(b)
    s.flush()
    copy = BookCopy(book_id=b.id, barcode=f"BC{str(uuid.uuid4().int)[:10]}", status=0)
    s.add(copy)
    s.commit()
    barcode = copy.barcode
    s.close()

    ok_count = 0
    errors = []
    lock = threading.Lock()

    def try_borrow(cid):
        nonlocal ok_count
        sess = Session()
        try:
            BorrowService(sess).scan_and_borrow(cid, barcode)
            with lock:
                ok_count += 1
        except Exception as e:
            with lock:
                errors.append(str(e)[:80])
        finally:
            sess.close()

    s = Session()
    child_ids = [c0]
    for _ in range(49):
        _, cid = _make_user_child(s, f"brw_{uuid.uuid4().hex[:8]}")
        child_ids.append(cid)
    s.commit()
    s.close()

    threads = [threading.Thread(target=try_borrow, args=(cid,)) for cid in child_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    passed = ok_count == 1
    return passed, f"成功 {ok_count}/50（副本 1），错误样本: {errors[:2]}"


def _scenario_deposit_unique(Session):
    from backend.domain.deposit.models import DepositRecord

    s = Session()
    _, cid = _make_user_child(s, f"dep_{uuid.uuid4().hex[:8]}")
    s.commit()
    s.close()

    def _insert(status_ok=True):
        sess = Session()
        try:
            rec = DepositRecord(
                child_id=cid,
                amount=Decimal("1200.00"),
                original_amount=Decimal("1200.00"),
                status=5,  # PENDING（活跃态）
                pay_order_id=f"DP{str(uuid.uuid4().int)[:24]}",
            )
            sess.add(rec)
            sess.commit()
            return True, None
        except IntegrityError as e:
            sess.rollback()
            return False, str(e.orig)[:80]
        finally:
            sess.close()

    barrier = threading.Barrier(2)
    outcomes = []
    lock = threading.Lock()

    def worker():
        barrier.wait()
        ok, err = _insert()
        with lock:
            outcomes.append((ok, err))

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    succ = sum(1 for ok, _ in outcomes if ok)
    integrity = sum(1 for ok, err in outcomes if not ok and err)
    passed = succ == 1 and integrity == 1
    return passed, f"成功 1/2（唯一索引拦截 1），结果: {outcomes}"


def _cleanup(engine):
    from backend.database import Base

    Base.metadata.drop_all(bind=engine)
    print("\n[cleanup] 测试库表已清空（--keep 可保留）")


if __name__ == "__main__":
    main()
