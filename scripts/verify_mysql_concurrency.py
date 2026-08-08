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
    results.append(("D 损坏报告并发双确认（行锁）", _scenario_damage_double_confirm(Session)))
    results.append(("E 取消订单 vs 支付（行锁）", _scenario_cancel_vs_paid(Session)))
    results.append(("F 库存并发双报损（行锁）", _scenario_stock_double_lost(Session)))
    results.append(("G 缓冲期关停 vs 续费（行锁）", _scenario_grace_vs_renew(Session)))

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


def _scenario_damage_double_confirm(Session):
    """F-080：损坏报告并发双确认——行锁串行化后每个报告恰 1 次生效（罚款不双计）

    20 个报告 × 2 管理员并发 confirm：修复前存在双成功（fines 双计）；修复后 0 双成功。
    """
    from datetime import datetime, timedelta

    from backend.domain.admin.services.damage_admin_service import DamageAdminService
    from backend.domain.book.damage_model import BookDamageReport
    from backend.domain.borrow.models import BorrowRecord
    from backend.domain.child.models import Child

    s = Session()
    report_ids = []
    child_ids = []
    for i in range(20):
        _, cid = _make_user_child(s, f"dmg_{uuid.uuid4().hex[:8]}")
        child = s.query(Child).filter(Child.id == cid).first()
        child.outstanding_fines = Decimal("0")
        br = BorrowRecord(
            child_id=cid,
            book_id=1,
            borrow_time=datetime.now() - timedelta(days=10),
            due_date=datetime.now() - timedelta(days=5),
            status=0,
        )
        s.add(br)
        s.flush()
        report = BookDamageReport(
            child_id=cid,
            borrow_record_id=br.id,
            damage_level=2,
            fine_amount=Decimal("100"),
            status=BookDamageReport.STATUS_PENDING_REVIEW,
            description=f"并发双确认 {i}",
        )
        s.add(report)
        s.flush()
        report_ids.append(report.id)
        child_ids.append(cid)
    s.commit()
    s.close()

    ok_counts = []
    errors = []
    lock = threading.Lock()

    def try_confirm(report_id, admin_id):
        sess = Session()
        try:
            DamageAdminService(sess).confirm_report(report_id, admin_id)
            with lock:
                ok_counts.append(1)
        except Exception as e:
            with lock:
                errors.append(str(e)[:80])
        finally:
            sess.close()

    for rid in report_ids:
        threads = [
            threading.Thread(target=try_confirm, args=(rid, a))
            for a in (1, 2)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    s = Session()
    double_count = 0
    for cid in child_ids:
        child = s.query(Child).filter(Child.id == cid).first()
        if child.outstanding_fines != Decimal("100"):
            double_count += 1
    s.close()

    passed = double_count == 0 and len(ok_counts) == 20
    return (
        passed,
        f"确认成功 {len(ok_counts)}/20（应恰 20），双计报告 {double_count}（应 0），"
        f"错误样本: {errors[:2]}",
    )


def _scenario_cancel_vs_paid(Session):
    """F-053：并发取消订单 vs 支付——cancel 不得把已 PAID 覆盖为 CLOSED

    30 个 PENDING 订单，每单两个线程并发：cancel_order vs 模拟支付回调（带锁置 PAID）。
    缺陷特征：最终状态 CLOSED 且 pay_time 非空（钱已收但订单被关）。
    """
    from datetime import datetime, timedelta

    from backend.common.types import PayStatus
    from backend.domain.order.models import Order
    from backend.domain.order.service import OrderService

    s = Session()
    order_ids = []
    user_ids = []
    for i in range(30):
        u, cid = _make_user_child(s, f"ccl_{uuid.uuid4().hex[:8]}")
        order = Order(
            order_no=f"CANCEL{i}-{uuid.uuid4().hex[:6]}",
            user_id=u,
            child_id=cid,
            type=2,
            amount=Decimal("500"),
            pay_status=PayStatus.PENDING,
            create_time=datetime.now() - timedelta(minutes=1),
        )
        s.add(order)
        s.flush()
        order_ids.append(order.id)
        user_ids.append(u)
    s.commit()
    s.close()

    lock = threading.Lock()
    outcomes = []

    def try_cancel(order_id, user_id):
        sess = Session()
        try:
            OrderService(sess).cancel_order(order_id, user_id)
            with lock:
                outcomes.append(("cancel_ok", order_id))
        except Exception as e:
            with lock:
                outcomes.append((f"cancel_err:{str(e)[:30]}", order_id))
        finally:
            sess.close()

    def try_mark_paid(order_id):
        """模拟支付回调写：带行锁置 PAID + 记录 pay_time（与回调同语义）"""
        sess = Session()
        try:
            order = (
                sess.query(Order)
                .filter(Order.id == order_id)
                .with_for_update()
                .first()
            )
            order.pay_status = PayStatus.PAID
            order.pay_time = datetime.now()
            sess.commit()
            with lock:
                outcomes.append(("paid_ok", order_id))
        except Exception as e:
            with lock:
                outcomes.append((f"paid_err:{str(e)[:30]}", order_id))
        finally:
            sess.close()

    for oid, uid in zip(order_ids, user_ids):
        threads = [
            threading.Thread(target=try_cancel, args=(oid, uid)),
            threading.Thread(target=try_mark_paid, args=(oid,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    s = Session()
    corrupted = 0
    final_states = {}
    for oid in order_ids:
        order = s.query(Order).filter(Order.id == oid).first()
        final_states[order.pay_status] = final_states.get(order.pay_status, 0) + 1
        if order.pay_status == PayStatus.CLOSED and order.pay_time is not None:
            corrupted += 1
    s.close()

    passed = corrupted == 0
    return (
        passed,
        f"损坏订单（CLOSED+pay_time）{corrupted}/30（应 0），最终状态分布: {final_states}",
    )


def _scenario_stock_double_lost(Session):
    """F-001/004：并发双报损——库存读-改-写丢失更新（total 应减 2，实际可能只减 1）

    1 本书 total=2 + 2 副本各一条借阅记录，2 线程并发 mark_book_lost。
    缺陷特征：最终 total=1（丢失更新）；修复后 total=0。
    """
    from datetime import datetime, timedelta

    from backend.domain.book.models import Book, BookCopy
    from backend.domain.borrow.models import BorrowRecord
    from backend.domain.deposit.service import DepositService

    s = Session()
    u, cid = _make_user_child(s, f"stk_{uuid.uuid4().hex[:8]}")
    book = Book(
        title="并发库存书",
        author="A",
        isbn=f"978{str(uuid.uuid4().int)[:13]}",
        total_stock=2,
        available_stock=2,
        offline_available=1,
        ar_value=Decimal("2.0"),
        age_min=5,
        age_max=9,
        word_count=500,
    )
    s.add(book)
    s.flush()
    bid = book.id
    borrow_ids = []
    for _ in range(2):
        copy = BookCopy(book_id=bid, barcode=f"STK-{uuid.uuid4().hex[:8]}", status=0)
        s.add(copy)
        s.flush()
        br = BorrowRecord(
            child_id=cid,
            book_id=bid,
            book_copy_id=copy.id,
            borrow_time=datetime.now() - timedelta(days=10),
            due_date=datetime.now() - timedelta(days=5),
            status=0,  # BORROWING（mark_book_lost 允许 BORROWING/OVERDUE）
        )
        s.add(br)
        s.flush()
        borrow_ids.append(br.id)
    s.commit()
    s.close()

    lock = threading.Lock()
    outcomes = []

    def try_lost(br_id, admin_id):
        sess = Session()
        try:
            DepositService(sess).mark_book_lost(br_id, admin_id)
            with lock:
                outcomes.append("ok")
        except Exception as e:
            with lock:
                outcomes.append(f"err:{str(e)[:60]}")
        finally:
            sess.close()

    threads = [
        threading.Thread(target=try_lost, args=(borrow_ids[0], 1)),
        threading.Thread(target=try_lost, args=(borrow_ids[1], 2)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    s = Session()
    book = s.query(Book).filter(Book.id == bid).first()
    total = book.total_stock
    s.close()

    passed = total == 0
    return passed, f"双报损后 total_stock={total}（应 0，丢失更新则 1），结果: {outcomes}"


def _scenario_grace_vs_renew(Session):
    """F-046：缓冲期关停任务 vs 并发续费——任务不得把续费后的会员覆盖为 EXPIRED

    30 个 OFFICIAL+expire 过期 child：15 个并发续费（带锁置 expire=未来），
    1 个任务线程 check_grace_period_shutdown（_get_db_session 指向测试库）。
    缺陷特征：续费成功的 child 被任务覆盖为 EXPIRED。
    """
    from datetime import datetime, timedelta

    from backend.common.types import MemberStatus
    from backend.domain.child.models import Child

    s = Session()
    child_ids = []
    for _ in range(30):
        _, cid = _make_user_child(s, f"grc_{uuid.uuid4().hex[:8]}")
        child = s.query(Child).filter(Child.id == cid).first()
        child.status = MemberStatus.OFFICIAL
        child.member_expire_time = datetime.now() - timedelta(days=20)
        child_ids.append(cid)
    s.commit()
    s.close()

    renew_ids = child_ids[:15]
    lock = threading.Lock()
    outcomes = []

    def try_renew(cid):
        sess = Session()
        try:
            child = (
                sess.query(Child)
                .filter(Child.id == cid)
                .with_for_update()
                .first()
            )
            child.status = MemberStatus.OFFICIAL
            child.member_expire_time = datetime.now() + timedelta(days=365)
            sess.commit()
            with lock:
                outcomes.append("renew_ok")
        except Exception as e:
            with lock:
                outcomes.append(f"renew_err:{str(e)[:60]}")
        finally:
            sess.close()

    threads = [threading.Thread(target=try_renew, args=(cid,)) for cid in renew_ids]
    for t in threads:
        t.start()

    # 任务线程：_get_db_session 指向测试库
    import backend.tasks.scheduler as sched_mod
    from backend.tasks.scheduler import check_grace_period_shutdown

    orig = sched_mod._get_db_session
    sched_mod._get_db_session = lambda: Session()
    try:
        check_grace_period_shutdown()
    finally:
        sched_mod._get_db_session = orig

    for t in threads:
        t.join()

    s = Session()
    corrupted = 0
    renewed_ok = 0
    for cid in renew_ids:
        child = s.query(Child).filter(Child.id == cid).first()
        if child.status == MemberStatus.OFFICIAL:
            renewed_ok += 1
        else:
            corrupted += 1  # 续费成功但被任务覆盖 EXPIRED
    s.close()

    passed = corrupted == 0 and renewed_ok >= 1
    return (
        passed,
        f"续费成功 {renewed_ok}/15，被任务覆盖 EXPIRED {corrupted}（应 0），"
        f"结果样本: {outcomes[:2]}",
    )


def _cleanup(engine):
    from backend.database import Base

    Base.metadata.drop_all(bind=engine)
    print("\n[cleanup] 测试库表已清空（--keep 可保留）")


if __name__ == "__main__":
    main()
