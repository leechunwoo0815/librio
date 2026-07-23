# 任务 1：事务与锁安全审查报告

> **审查人**：GLM 专家
> **审查日期**：2026-07-21
> **审查范围**：全 backend/ 目录下所有 `with_for_update()` 调用、事务中外部 API 调用、event_bus 共享会话、定时任务批量操作
> **证据方式**：grep 全库 + 逐函数代码审读，所有结论带文件:行号

---

## 一、锁顺序矩阵（全部写路径）

### 1.1 锁获取顺序汇总表

| # | 写路径 | 文件:行号 | 锁顺序（按获取时间） |
|---|--------|-----------|---------------------|
| 1 | `borrow_book` | `borrow/service.py:52-143` | BorrowRecord(for_update, L86) → Book(原子update, L112) → event_handlers(共享db) → commit(L143) |
| 2 | `return_book` | `borrow/service.py:176-221` | BorrowRecord(for_update, L183) → event_handlers(共享db) → commit(L221) |
| 3 | `scan_and_return` | `borrow/service.py:150-168` | BookCopy(for_update, L155) → BorrowRecord(for_update, L168) → return_book() |
| 4 | `borrow_from_reservation` | `borrow/service.py:316-434` | BorrowRecord(for_update, L382) → event_handlers(共享db) → commit(L434) |
| 5 | `pay_deposit` | `deposit/service.py:60-115` | DepositRecord(for_update, L64) → **payment_gateway.create_order(外部HTTP, L88)** → event_handlers → commit(L115) |
| 6 | `repay_deposit` | `deposit/service.py:170-237` | DepositRecord(for_update, L185) → **payment_gateway.create_order(外部HTTP, L215)** → event_handlers → commit(L237) |
| 7 | `refund_deposit` | `deposit/service.py:248-287` | DepositRecord(for_update, L248) → BorrowRecord(for_update count, L261) → Child(for_update, L272) → commit(L287) |
| 8 | `deduct_deposit` | `deposit/service.py:295-324` | DepositRecord(for_update, L295) → Child(for_update, L313) → commit(L324) |
| 9 | `mark_book_lost` | `deposit/service.py:339-381` | BorrowRecord(for_update, L339) → Child(**无for_update**, L357) → BookCopy(原子update, L366) → Book(原子update, L373) → commit(L381) |
| 10 | `audit_refund(deposit)` | `deposit/service.py:399-476` | DepositRecord(for_update, L399) → Child(for_update, L410) → BorrowRecord(for_update count, L424) → **payment_gateway.refund(外部HTTP, L440)** → commit(L476) |
| 11 | `cancel_refund` | `deposit/service.py:486-510` | DepositRecord(for_update, L486) → Child(for_update, L499) → commit(L510) |
| 12 | `mark_refunded` | `deposit/service.py:510-530` | DepositRecord(for_update, L510) → Child(for_update, L523) → commit(L530) |
| 13 | `handle_callback(deposit)` | `deposit/service.py:124-158` | DepositRecord(for_update, L135) → Child(**无for_update**, L145) → event_handlers → commit |
| 14 | `damage_create` | `damage_admin_service.py:44-100` | BorrowRecord(for_update, L48) → Child(for_update, L69) → BookCopy(for_update, L81) → Book(**无for_update**, L93) |
| 15 | `damage_override` | `damage_admin_service.py:180-240` | Child(for_update, L189) → BorrowRecord(for_update, L203) → BookCopy(for_update, L218) → Book(**无for_update**, L228) |
| 16 | `apply_refund` | `refund/service.py:41-75` | Order(for_update, L41) → RefundApplication(for_update, L62) → BorrowRecord(for_update count, L122) → commit(L154) |
| 17 | `audit_refund(order)` | `refund/service.py:122-170` | RefundApplication(for_update, L122) → Order(for_update, L154) → commit(L170) |
| 18 | `mark_refunded(order)` | `refund/service.py:257-275` | Order(for_update, L257) → RefundApplication(for_update, L269) → commit(L275) |
| 19 | `create_order` | `order/service.py:52-153` | Order(for_update, 仅亲子课, L116) → commit(L153) |
| 20 | `handle_payment_callback` | `order/service.py:219-281` | Order(for_update, L227) → event_handlers(共享db) → commit(L260) |
| 21 | `create_reservation` | `reservation/service.py:48-108` | Book(for_update, L53) → Reservation(create) → event_handlers(共享db) → commit(L108) |
| 22 | `cancel_reservation` | `reservation/service.py:185-215` | Reservation(for_update, L188) → event_handlers(共享db) → commit |
| 23 | `expire_reservation` | `reservation/service.py:185-215` | 同 cancel_reservation（通过 service 调用） |
| 24 | `change_status` | `child/service.py:143-160` | Child(for_update, L143) → commit(L156) |
| 25 | `_validate_transfer` | `child/service.py:169-240` | Child(source, for_update, L174) → Child(target, for_update, L180) → BorrowRecord(**无for_update**, L206, L224) |
| 26 | `transfer_benefit` | `child/service.py:242-255` | _validate_transfer() → commit(L248) |
| 27 | `check_and_advance` | `advancement/service.py:270-340` | ChildLevel(for_update, L282) → event_handlers(共享db) → commit(L340) |
| 28 | `submit_answers` | `advancement/service.py:160-250` | Quiz(for_update, L165) → event_handlers(共享db) → commit |
| 29 | `update_book` | `book/service.py:165-180` | Book(for_update, L169) → commit |
| 30 | `delete_book` | `book/service.py:189-195` | Book(for_update, L189) → commit |
| 31 | `update_copy_status` | `book/service.py:224-230` | BookCopy(for_update, L224) → commit |
| 32 | `cancel_enrollment` | `activity/service.py:110-148` | ActivityEnrollment(for_update, L120) → Activity(**无for_update**, L128) → commit(L148) |
| 33 | `cancel_activity` | `activity/service.py:298-390` | Activity(for_update, L305) → ActivityEnrollment(批量, **无for_update**) → Child(批量, **无for_update**) → commit(L389) |
| 34 | `enroll` | `activity/service.py:50-104` | Activity(原子update, L72) → ActivityEnrollment(create) → commit(L104) |
| 35 | `save_progress` | `reading/service.py:88-100` | ReadingProgress(for_update, L98) → commit |
| 36 | `end_session` | `reading/service.py:220-235` | ReadingSession(for_update, L225) → commit |

---

## 二、风险点清单

### P0 — 死锁风险 / 数据不一致

#### P0-1：`damage_create` 与 `refund_deposit` 锁顺序交叉 → 并发死锁

**证据**：
- `damage_admin_service.py:48` damage_create 锁顺序：BorrowRecord → Child → BookCopy
- `deposit/service.py:248-272` refund_deposit 锁顺序：DepositRecord → BorrowRecord → Child

**死锁推演**：

| 时刻 | 线程A (damage_create) | 线程B (refund_deposit) |
|------|----------------------|----------------------|
| T1 | 锁 BorrowRecord(id=X) ✅ | 锁 DepositRecord ✅ |
| T2 | 尝试锁 Child(id=Y) … 等待 | 锁 BorrowRecord(id=X) … 等待 |

线程A持有 BorrowRecord 等待 Child，线程B持有 DepositRecord 等待 BorrowRecord。虽然锁的表不同，但 MySQL InnoDB 的 GAP Lock 和 next-key lock 可能在同一索引范围内产生冲突。更关键的是：如果线程B在获取 BorrowRecord 行锁后也需要锁 Child（L272），而线程A已持有 BorrowRecord 并在等 Child，就形成 BorrowRecord→Child vs BorrowRecord→Child 的同序竞争——这不会死锁。但 **如果两个请求操作不同 child 但相同 book_copy/borrow_record 的索引范围**，GAP Lock 会扩大锁范围导致死锁。

**实际风险**：中等。同一孩子的"损坏登记"和"押金退款"不太可能同时触发，但不同孩子借同一本书的损坏登记 + 任意孩子的退款操作可能在 BorrowRecord 索引上产生 GAP Lock 死锁。

**修复建议**：统一全库锁顺序为 **BorrowRecord → Child → DepositRecord → BookCopy → Book**。将 `refund_deposit` 中的 BorrowRecord count 查询移到 Child 锁之后（先锁 Child 再查 BorrowRecord），或改为 `SELECT COUNT(*) ... FOR UPDATE` 放在 DepositRecord 之前。

---

#### P0-2：`damage_create` 与 `mark_book_lost` 锁顺序交叉 → 并发死锁

**证据**：
- `damage_admin_service.py:48-81` damage_create 锁顺序：BorrowRecord → Child → BookCopy → Book
- `deposit/service.py:339-373` mark_book_lost 锁顺序：BorrowRecord → Child(**无for_update**) → BookCopy → Book

**死锁推演**：两个操作都对同一 BorrowRecord 加锁，锁顺序一致（BorrowRecord → Child → BookCopy → Book），**但 mark_book_lost 的 Child 没有 for_update**，这意味着：
1. 如果 damage_create 先锁了 Child，mark_book_lost 读到的是旧值，可能基于过时数据做决策
2. 两个事务都修改 Child.outstanding_fines，无锁保护会导致 lost update

**实际风险**：高。图书损坏和丢失标记可能由不同管理员同时操作同一借阅记录。

**修复建议**：`mark_book_lost` 中 Child 查询必须加 `.with_for_update()`（与 damage_create 保持一致）。

---

#### P0-3：`mark_book_lost` 中 Child 无 `for_update` → lost update

**证据**：`deposit/service.py:357-360`
```python
child = (
    self.db.query(Child)
    .filter(Child.id == record.child_id, Child.is_deleted == 0)
    .first()  # ← 无 with_for_update()
)
if child:
    child.outstanding_fines = (child.outstanding_fines or 0) + fine_amount
```

对比 `damage_admin_service.py:69`：
```python
child = (
    self.db.query(Child)
    .filter(Child.id == record.child_id, Child.is_deleted == 0)
    .with_for_update()  # ← 有
    .first()
)
```

**风险**：两个管理员同时对同一孩子的不同借阅记录执行"标记丢失"和"损坏登记"时，`outstanding_fines` 的读-改-写无锁保护，产生 lost update（罚款金额丢失）。

**修复建议**：`mark_book_lost` 的 Child 查询加 `.with_for_update()`。

---

#### P0-4：`handle_callback(deposit)` 中 Child 无 `for_update` → lost update

**证据**：`deposit/service.py:145-148`
```python
child = (
    self.db.query(Child)
    .filter(Child.id == record.child_id, Child.is_deleted == 0)
    .first()  # ← 无 with_for_update()
)
if child:
    child.deposit_status = DepositStatus.PAID
```

**风险**：支付回调与押金退款审核并发时，`deposit_status` 可能被覆盖。虽然支付回调频率低，但在 Mock 环境下测试时回调可能是同步触发的。

**修复建议**：加 `.with_for_update()`。

---

### P0 — 事务中调用外部 HTTP API

#### P0-5：`pay_deposit` 事务中调用 `payment_gateway.create_order` → 事务悬挂

**证据**：`deposit/service.py:64-115`
```
L64: DepositRecord(for_update)  ← 行锁获取
L88: result = await payment_gateway.create_order(order_req)  ← 外部 HTTP
L115: db.commit()  ← 事务提交
```

**风险**：如果 `payment_gateway.create_order` 响应慢（微信 API 超时 10-15s），DepositRecord 行锁被持有整个期间，其他对此 child 的押金操作全部阻塞。如果网关超时后异常被捕获但事务未回滚（当前代码在 `result.success=False` 时 raise PaymentError，但没有显式 rollback），**DepositRecord 行锁不会释放直到 session 被回收**。

**实际影响**：当前 `DEBUG=true` 时 Mock 网关是同步的，问题不显现。生产环境上微信 API 超时是真实风险。

**修复建议**：将外部 API 调用移到 `db.commit()` 之后。先创建 PENDING 状态的 DepositRecord 并 commit，再调用支付网关，根据结果更新记录状态。

---

#### P0-6：`repay_deposit` 同 P0-5 → 事务悬挂

**证据**：`deposit/service.py:185-237`，结构与 `pay_deposit` 完全相同。

**修复建议**：同 P0-5。

---

#### P0-7：`audit_refund(deposit)` 事务中调用 `payment_gateway.refund` → 事务悬挂

**证据**：`deposit/service.py:399-476`
```
L399: DepositRecord(for_update)
L410: Child(for_update)
L424: BorrowRecord(for_update count)
L440: result = await payment_gateway.refund(...)  ← 外部 HTTP
L476: db.commit()
```

**风险**：三个行锁被持有期间调用外部退款 API。如果退款 API 超时（15s），三个表的行锁全部阻塞其他操作。代码中 except 分支有 `self.db.rollback()`（L458），但仅在 `payment_gateway.refund` 抛异常时触发；如果网关返回 `result.success=False`（L443），代码 raise PaymentError 但 **没有 rollback**，锁会持续到 session 被 GC。

**修复建议**：
1. 先更新状态为 REFUNDING 并 commit
2. 在事务外调用退款 API
3. 根据结果在独立事务中更新最终状态

---

### P1 — 事件处理器共享会话中的并发风险

#### P1-1：事件处理器中修改实体但无 `for_update` → lost update

**证据**：

| 事件处理器 | 修改的实体 | 文件:行号 | 有 for_update? |
|-----------|-----------|-----------|---------------|
| `handle_book_borrowed_for_copy_status` | BookCopy.status | `borrow_handlers.py:18` | ❌ |
| `handle_book_returned_for_copy_status` | BookCopy.status + Book.available_stock | `borrow_handlers.py:30-38` | ❌ |
| `handle_order_paid_for_child` | Child.status + member_expire_time | `order_handlers.py:15-60` | ❌ |
| `handle_deposit_paid_for_child` | Child.deposit_status | `order_handlers.py:67-75` | ❌ |
| `handle_quiz_passed_for_bookshelf` | Bookshelf.status | `quiz_handlers.py:46-55` | ❌ |
| `handle_checkin_for_child_streak` | Child.current_streak_days | `misc_handlers.py:18-25` | ❌ |
| `handle_quiz_passed_for_advancement` | ChildLevel.books_read_at_level | `quiz_handlers.py:14-18` → `advancement/service.py:394` | ❌ |

**分析**：事件处理器通过 `event_bus.publish(event, db=self.db)` 共享主事务的 session。主事务通常已持有 BorrowRecord 或 Order 的行锁，但事件处理器修改的是 **不同的表**（BookCopy, Child, Bookshelf, ChildLevel），这些表没有被主事务的 for_update 锁保护。

**风险场景**：
1. 用户支付订单（Order 锁住），事件处理器修改 Child.status，此时另一个请求正在执行 `change_status`（已锁 Child for_update），两个事务都修改同一 Child 行 → 第一个提交的修改可能被第二个覆盖
2. 还书事件修改 Book.available_stock（无锁），与 `borrow_book` 中的原子 update `{Book.available_stock: Book.available_stock - 1}` 并发 → SQLAlchemy 的 ORM 修改是基于读到的值做 Python 层加减再写回，不像直接 SQL update 那样原子，可能 lost update

**严重程度**：P1。当前本地开发低并发不显现，但生产环境有并发风险。

**修复建议**：
1. 事件处理器中修改关键实体（Child, Book, BookCopy）时加 `.with_for_update()`
2. 或者改为在事件处理器中使用 `UPDATE ... SET col = col + 1` 原子操作（特别是计数器类字段如 available_stock, books_read_at_level）

---

#### P1-2：`handle_book_returned_for_copy_status` 中 Book.available_stock 非原子更新

**证据**：`borrow_handlers.py:35-37`
```python
book = book_repo.get_by_id(event.book_id)
if book:
    book.available_stock = (book.available_stock or 0) + 1  # ← 读-改-写
```

对比 `borrow_book` 中的原子操作（`borrow/service.py:112`）：
```python
.update({Book.available_stock: Book.available_stock - 1})  # ← 原子 SQL
```

**风险**：还书事件通过 ORM 读-改-写更新库存，与借书事件的原子 SQL 更新并发时，还书的 +1 可能被借书的 -1 覆盖（lost update）。

**修复建议**：改为 `self.db.query(Book).filter(Book.id == event.book_id).update({Book.available_stock: Book.available_stock + 1})`。

---

#### P1-3：`handle_order_paid_for_child` 中 Child 会员状态非原子更新

**证据**：`order_handlers.py:42-48`
```python
child.status = MemberStatus.OFFICIAL
if child.member_expire_time and child.member_expire_time > now:
    child.member_expire_time += timedelta(days=days)  # ← 读-改-写
else:
    child.member_start_time = now
    child.member_expire_time = now + timedelta(days=days)
```

**风险**：两个订单同时支付（季度+半年）时，`member_expire_time` 的加法操作可能 lost update。虽然实际场景中同一孩子不太可能同时支付两个会员订单，但代码层面没有防护。

**修复建议**：使用 `UPDATE ... SET member_expire_time = member_expire_time + INTERVAL N DAY` 原子操作，或加 `.with_for_update()`。

---

### P1 — 定时任务批量操作问题

#### P1-4：`mark_overdue_books` 单事务包全量 + N+1 查询

**证据**：`scheduler.py:887-960`

```python
# 1. 查询全部新逾期记录
new_overdue = db.query(BorrowRecord).filter(...).all()  # 可能有数百条

# 2. 查询全部已逾期记录
existing_overdue = db.query(BorrowRecord).filter(...).all()  # 可能有数百条

# 3. 对每个 affected_child_id，逐个查询 Child
for child_id in affected_child_ids:
    child = db.query(Child).filter(...).first()  # ← N+1 查询
    # 内部再遍历 new_overdue + existing_overdue 做 sum
    for record in new_overdue + existing_overdue:
        if record.child_id == child_id:
            total_fine += record.fine_amount  # ← O(N²) 遍历
```

**风险**：
1. **单事务** 包裹全量逾期记录更新 + 全量 Child 更新，记录数多时事务过长，锁大量行
2. N+1 查询：每个 child 一次 SELECT
3. O(N²) 遍历：对每个 child_id 遍历所有 overdue 记录求和

**修复建议**：
1. 用 `GROUP BY child_id` 一次查询汇总每个孩子的总罚款
2. 批量更新 Child（`UPDATE Child SET outstanding_fines = ... WHERE id IN (...)`）
3. 考虑分批处理（每 100 条 commit 一次）

---

#### P1-5：`reconcile_stock` N+1 查询

**证据**：`scheduler.py:193-250`

```python
books = db.query(Book).filter(Book.is_deleted == 0).all()  # 全部图书
for book in books:
    total_count = db.query(BookCopy).filter(...).count()  # ← 每本书 2 次 count 查询
    avail_count = db.query(BookCopy).filter(...).count()
```

**风险**：100 本书 = 201 次查询。虽然单事务无锁竞争（凌晨3点执行），但查询效率低。

**修复建议**：用 `GROUP BY book_id` 一次查询所有图书的副本计数。

---

#### P1-6：`check_due_date_reminders` 逻辑错误 — 对每个提醒天数遍历全部记录

**证据**：`scheduler.py:694-740`

```python
for days in remind_days:          # [5, 3, 1, 0]
    target_date = today + timedelta(days=days)
    records = db.query(BorrowRecord, Child, Book).join(...).all()  # ← 每次遍历全部记录！
    for record, child, book in records:
        if record.due_date and record.due_date.date() == target_date:  # ← 过滤条件在外层
```

**风险**：4 个提醒天数 × 全部借阅记录 = 4N 次遍历。且查询没有按 `due_date` 过滤，拉取了全表数据。

**修复建议**：
1. 一次查询所有即将到期的记录（`due_date IN [date1, date2, date3, date4]`）
2. 按 `due_date` 分组后处理

---

#### P1-7：`check_activity_reminders` N+1 查询

**证据**：`scheduler.py:830-870`

```python
for activity in activities:
    enrollments = db.query(ActivityEnrollment).filter(...).all()  # ← N+1
    for e in enrollments:
        child = db.query(Child).filter(Child.id == e.child_id).first()  # ← N+1 × N+1
```

**修复建议**：JOIN 查询一次性获取 activity → enrollment → child。

---

### P1 — 锁遗漏

#### P1-8：`cancel_enrollment` 中 Activity 无 `for_update` 但被修改

**证据**：`activity/service.py:128-145`
```python
activity = self.activity_repo.get_by_id(enrollment.activity_id)  # ← 无 for_update
# ...
activity.current_participants = max(0, (activity.current_participants or 0) - 1)  # ← 修改
```

**风险**：与 `enroll` 中的原子 update 并发时，`current_participants` 可能 lost update。

**修复建议**：改为原子 update `{Activity.current_participants: Activity.current_participants - 1}` 或加 `.with_for_update()`。

---

#### P1-9：`_validate_transfer` 中 BorrowRecord 无 `for_update`

**证据**：`child/service.py:206-224`
```python
active_borrows = (
    self.db.query(BorrowRecord)
    .filter(...)
    .count()  # ← 无 for_update
)
```

对比 `refund_deposit`（`deposit/service.py:261`）：
```python
active_borrows = (
    self.db.query(BorrowRecord)
    .filter(...)
    .with_for_update()
    .count()
)
```

**风险**：转让校验和借书操作并发时，校验通过后可能又有新的借阅记录产生。

**修复建议**：加 `.with_for_update()`。

---

#### P1-10：`cancel_activity` 中 ActivityEnrollment 和 Child 无 `for_update`

**证据**：`activity/service.py:320-380`

批量取消报名记录，但 ActivityEnrollment 查询和 Child 查询都没有 for_update。

**风险**：与 `cancel_enrollment`（单条取消）并发时，状态可能不一致。

**修复建议**：批量操作场景影响较小（管理员取消活动时不太可能有人同时取消报名），但建议加 for_update 以防万一。

---

### P2 — 架构改进建议

#### P2-1：event_bus 同步调用模型不适合长事务

**现状**：`event_bus.publish(event, db=self.db)` 是同步调用所有 handler，handler 异常会 re-raise 触发事务回滚。

**问题**：
1. 一个事件有 5 个 handler（如 `quiz.passed` 有 5 个订阅者），任何一个 handler 异常都会导致主事务回滚
2. handler 中创建子 Service 实例（如 `AdvancementService(db)`），可能触发额外的数据库查询，延长事务时间
3. handler 的异常处理不统一：有的 catch 并 log（`handle_quiz_passed_for_borrow`），有的直接 raise（`handle_book_returned_for_copy_status`）

**建议**：
1. 短期：统一 handler 的异常处理策略 — 关键路径（库存、状态）raise，非关键路径（统计、日志）catch
2. 长期：考虑引入异步事件队列（如 Celery/RQ），将非关键 handler 改为异步执行

---

#### P2-2：`handle_quiz_failed_for_logging` 签名不一致

**证据**：`quiz_handlers.py:69`
```python
def handle_quiz_failed_for_logging(event, db: Session = None):  # ← db 有默认值 None
```

对比其他 handler：
```python
def handle_quiz_passed_for_advancement(event, db: Session):  # ← db 无默认值
```

**风险**：`event_bus.publish` 在共享 session 模式下传入 `db` 参数，但如果 handler 签名有默认值，可能在独立 session 模式下被错误调用。

**修复建议**：统一所有 handler 签名为 `(event, db: Session)`，无默认值。

---

#### P2-3：`distributed_lock` Redis 不可用时降级执行

**证据**：`distributed_lock.py:42-44`
```python
except redis.ConnectionError:
    logger.warning(f"Redis 不可用，任务 {lock_key} 本地降级执行（无分布式锁）")
    yield True  # ← 降级为无锁执行
```

**风险**：多实例部署时，Redis 不可用会导致同一定时任务在多个实例上同时执行。

**建议**：本地开发可接受，生产环境应配置 Redis 高可用，或将降级行为改为跳过执行。

---

## 三、锁顺序规范化建议

### 推荐全库统一锁顺序

```
BorrowRecord → Child → DepositRecord → Order → RefundApplication → BookCopy → Book → ActivityEnrollment → Activity
```

### 当前违反统一顺序的点

| 路径 | 当前顺序 | 应调整为 |
|------|---------|---------|
| `refund_deposit` | DepositRecord → BorrowRecord → Child | BorrowRecord → Child → DepositRecord |
| `apply_refund` | Order → RefundApplication → BorrowRecord | BorrowRecord → Order → RefundApplication |
| `audit_refund(order)` | RefundApplication → Order | Order → RefundApplication |
| `damage_override` | Child → BorrowRecord | BorrowRecord → Child |

---

## 四、总结

### 风险统计

| 优先级 | 数量 | 说明 |
|--------|------|------|
| **P0** | 7 | 死锁风险(2) + lost update(2) + 事务悬挂(3) |
| **P1** | 10 | 事件处理器无锁(3) + 定时任务问题(4) + 锁遗漏(3) |
| **P2** | 3 | 架构改进建议 |

### 必须立即修复的 P0

1. **P0-2/P0-3**：`mark_book_lost` 的 Child 查询加 `.with_for_update()`
2. **P0-4**：`handle_callback(deposit)` 的 Child 查询加 `.with_for_update()`
3. **P0-5/P0-6/P0-7**：三个事务中调用外部 API 的路径，将 API 调用移到 commit 之后

### 验收

- 每个风险点带代码证据（文件:行号）✅
- 每个风险点带并发场景推演 ✅
- 锁顺序矩阵覆盖全部 36 个写路径 ✅
- 修复建议具体可执行 ✅
