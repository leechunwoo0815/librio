# DmkWords V3.8 交付前技术评审报告

> **评审人**: 高见远（首席架构师）
> **评审日期**: 2026-07-15
> **评审范围**: 架构设计 / 性能 / 数据库设计 / 运维与可观测性
> **项目版本**: V3.8 | 26 领域模块 | 49 张表 | 180+ API | 14 定时任务

---

## 总览

| 维度 | P0 | P1 | P2 | 通过项 |
|------|----|----|----|--------|
| 架构设计 | 2 | 0 | 2 | 5 |
| 性能 | 0 | 2 | 3 | 3 |
| 数据库设计 | 0 | 1 | 1 | 3 |
| 运维与可观测性 | 0 | 3 | 3 | 2 |
| **合计** | **2** | **6** | **9** | **13** |

---

## 维度一：架构设计评审

### 1.1 Router 层零 ORM 操作 — ❌ P0（2 处违规）

#### 违规 1：`backend/domain/child/router.py:98-99`

```python
db.add(application)
db.commit()
db.refresh(application)
```

**问题**: Router 直接操作数据库，绕过 Service 层，违反 DDD 分层约束。
**风险**: 业务逻辑散落在 Router 中，无法复用、难以测试、权益转让的业务规则无法统一管理。
**修复**:

```python
# 在 ChildService 中新增方法
def create_benefit_transfer_application(
    self, source_child_id: int, target_child_id: int, user_id: int
) -> BenefitTransferApplication:
    self._validate_transfer(source_child_id, target_child_id)
    application = BenefitTransferApplication(
        source_child_id=source_child_id,
        target_child_id=target_child_id,
        user_id=user_id,
        status=0,
    )
    return self.benefit_repo.create(application)

# Router 改为
application = child_service.create_benefit_transfer_application(
    req.source_child_id, req.target_child_id, current_user.id
)
child_service.db.commit()
```

#### 违规 2：`backend/domain/admin/routers/admin_activities_router.py:169`

```python
enrollment = db.query(ActivityEnrollment).filter(
    ActivityEnrollment.id == enrollment_id,
    ActivityEnrollment.is_deleted == 0,
).first()
```

**问题**: Router 直接查询数据库，获取 `Session` 后绕过 Service 层。
**风险**: 同样违反分层约束，且该查询未使用 Repository（对比：`FavoritesRepository.get_by_child_and_book` 也没有 is_deleted 过滤 —— 见下文 9.3）。
**修复**: 将查询逻辑下沉至 `ActivityService` 或通过 `AdminSystemService` 统一处理。

---

### 1.2 Service 层 HTTP 代码泄漏 — ✅ 通过

所有 Service 文件中的 `*Response` 引用均为 Pydantic Schema 类（如 `BookListResponse`、`DepositResponse`），不属于 FastAPI HTTP 层对象。唯一提及 `StreamingResponse` 的是 `export_service.py:26` 注释（说明路由层职责），未实际导入。Service 层统一使用 `backend.common.exceptions.BusinessException` 体系抛出异常，由全局异常处理器转换为 HTTP 响应。**架构分层清晰，通过。**

---

### 1.3 EventBus 设计 — ✅ 通过（含 1 个 P2 建议）

**通过项**:
- 无循环依赖：`events.py` 仅定义事件数据类，不导入任何 domain 模块 ✅
- 事务一致性：`publish(db=session)` 共享事务，异常回滚 ✅
- 死信机制：独立事务记录 `DeadLetterEvent`，含重试逻辑 ✅
- 处理器注册在 `bootstrap.py` → `events/registry.py`，集中管理 ✅
- ADR-001 决策记录清晰，同步事件总线的选择有充分理由 ✅

#### P2 建议：独立 session 模式下的 session 泄漏风险

**文件**: `backend/common/events.py:391-416`

```python
session = get_session()()
try:
    handler(event, session)
    session.commit()
except Exception:
    session.rollback()
    # 重试一次
    try:
        retry_session = get_session()()
        ...
    finally:
        try:
            retry_session.close()
        except Exception:
            pass
finally:
    session.close()
```

**问题**: 当 `session.commit()` 成功但 `retry_session` 创建成功且 `retry_session.commit()` 也成功时，第一个 session 已 close，逻辑正确。但在极端情况下（如 `get_session()()` 创建 retry_session 成功但第一个 session.close() 抛异常），可能导致 session 未关闭。
**风险**: 低。仅在定时任务独立 session 模式下触发，且有多层 try/finally 保护。
**修复**: 建议将 session 生命周期管理提取为 context manager `@contextmanager def independent_db_session()`，统一处理。

---

### 1.4 PaymentGateway / SmsGateway 依赖倒置 — ✅ 通过

| 层 | 支付 | 短信 |
|----|------|------|
| **ABC** | `common/gateways/payment/base.py:PaymentGateway` | `common/gateways/sms/base.py:SmsGateway` |
| **Mock** | `common/gateways/payment/mock.py:MockPaymentGateway(PaymentGateway)` | `common/gateways/sms/mock.py:MockSmsGateway(SmsGateway)` |
| **Real** | `integrations/wechat/pay_v3.py:WeChatPayV3(PaymentGateway)` | `integrations/sms/tencent.py:TencentSmsGateway(SmsGateway)` / `integrations/sms/aliyun.py:AliyunSmsGateway(SmsGateway)` |
| **工厂** | `dependencies.py:get_payment_gateway()` | `dependencies.py:get_sms_gateway()` |

三层分离完整，工厂函数通过 `MOCK_PAYMENT`/`MOCK_SMS` 配置切换。Service 层通过 `payment_gateway: PaymentGateway` 参数接收抽象接口。**依赖倒置原则执行彻底，通过。**

---

### 1.5 ConfigService 缓存一致性 — ✅ 通过（含 1 个 P2 建议）

**通过项**:
- TTL 300 秒（5 分钟），对业务配置变更延迟可接受 ✅
- `set_config()` 写入后立即调用 `invalidate(key)`，写穿缓存 ✅
- 审计日志 `ConfigAuditLog` 记录所有配置变更 ✅
- 类型安全的方法：`get_int`/`get_decimal`/`get_bool`/`get_str`/`get_int_list` ✅

#### P2 建议：缓存击穿风险

**文件**: `backend/common/config_service.py:35-56`

```python
if key in cls._cache:
    val, ts = cls._cache[key]
    if now - ts < _CACHE_TTL:
        return val
    del cls._cache[key]  # 多请求同时过期 → 全部回源 DB

config = db.query(SystemConfig).filter(...).first()
```

**问题**: 当缓存过期时，多个并发请求同时发现过期，同时执行 `del cls._cache[key]`，然后同时查询数据库。对 `SystemConfig` 表影响极小（配置项数量有限），但严格来说是缓存击穿。
**风险**: 极低。配置读取频率不高，`SystemConfig` 表数据量小。
**修复**: 可选加 `threading.Lock()` 或使用"过期不删除，异步刷新"策略。当前阶段不必须。

---

### 1.6 领域模块依赖关系 — ✅ 通过

**分析方法**: 扫描所有 `service.py` 的跨域 import，以及 `events.py` 的事件发布/订阅关系。

**结论**: 通过 EventBus 解耦，领域模块之间无直接循环依赖。跨域通信通过事件驱动：

```
QuizService → QuizPassedEvent → AdvancementService / ChildService / BookshelfService / BorrowService
BorrowService → BookBorrowedEvent / BookReturnedEvent → BookService / AchievementService
OrderService → OrderPaidEvent → ChildService / DepositService / NotificationService
```

唯一存在直接跨域调用的是 `borrow/service.py` 中对 `reservation/models.py` 的引用，但这是通过事件处理器调用（`borrow_from_reservation`），属于合理的依赖方向（预约 → 借阅）。**DDD 边界清晰，通过。**

---

### 1.7 架构演进空间 — ✅ 通过

**新增业务模块（如拼团、积分商城）接入成本评估**:

| 步骤 | 工作量 | 说明 |
|------|--------|------|
| 1. 新建 `backend/domain/group_buy/` | 低 | 标准模板：`models.py` + `schemas.py` + `service.py` + `router.py` + `repository.py` |
| 2. 注册路由 | 低 | `main.py` 加 3 行 |
| 3. 注册 Service 工厂 | 低 | `dependencies.py` 加 7 行 |
| 4. 数据库迁移 | 中 | 1 个 alembic 迁移文件 |
| 5. 事件集成 | 低 | 如需跨域通信，在 `events.py` 定义事件，在 `events/registry.py` 注册处理器 |
| 6. 管理后台 | 中 | admin 子路由 + 前端模板 |

**接入成本**: 低。现有架构（DDD + EventBus + BaseRepository）已为新模块提供完整的脚手架，新增模块只需编写业务逻辑。**通过。**

---

## 维度四：性能评审

### 4.1 N+1 查询修复质量 — ✅ 通过

抽查 5 处：

| 修复 # | 文件 | 抽查结果 |
|--------|------|---------|
| #1 | `bookshelf/repository.py:38` | ✅ `joinedload(Bookshelf.book)` 已生效（行 38） |
| #2 | `bookshelf/repository.py:70` | ✅ `joinedload(Favorites.book)` 已生效（行 70） |
| #9 | `message/service.py:185-198` | ✅ 批量 `id.in_()` 预加载（行 170-183 使用直接查询） |
| #15 | `admin/services/book_service.py:111-122` | ✅ `Book.isbn.in_(isbns)` 批量查询（行 112-116） |
| #14 | `borrow/service.py:206-228` | ✅ `_batch_borrow_counts()` 批量加载（HANDOFF 记录） |

所有抽查项修复真实有效。**通过。**

---

### 4.2 数据库索引 — ❌ P1（3 处缺失）

#### P1-1：`borrow_record.status` 缺索引

**文件**: `backend/domain/borrow/models.py:46`

```python
status = Column(SmallInteger, default=BorrowStatus.BORROWING, comment="借阅状态")
```

**问题**: `status` 在以下高频查询中作为过滤条件，缺少索引：
- 定时任务 `mark_overdue_books`：`WHERE status = BORROWING AND due_date < NOW()`（每日）
- 定时任务 `mark_overdue_books`：`WHERE status = OVERDUE`（每日）
- `get_child_borrows`：`WHERE child_id = X AND status IN (BORROWING, OVERDUE)`
- 押金退还前校验：`WHERE child_id = X AND status IN (BORROWING, OVERDUE)`

**风险**: 随着借阅数据增长，每次全表扫描 `borrow_record` 表。
**修复**:

```python
status = Column(SmallInteger, default=BorrowStatus.BORROWING, index=True, comment="借阅状态")
```

或创建复合索引：

```python
# alembic 迁移
op.create_index("ix_borrow_record_child_status", "borrow_record", ["child_id", "status"])
op.create_index("ix_borrow_record_status_due", "borrow_record", ["status", "due_date"])
```

#### P1-2：`reservation.expire_time` 缺索引

**文件**: `backend/domain/reservation/models.py:30`

```python
expire_time = Column(DateTime, nullable=False, comment="过期时间（创建+72小时）")
```

**问题**: 定时任务 `expire_reservations`（每 30 分钟执行）扫描：
```python
WHERE status = PENDING AND expire_time < NOW()
```
`expire_time` 无索引，每次全表扫描。
**风险**: 预约表增长后，定时任务执行时间线性增长。
**修复**:

```python
expire_time = Column(DateTime, nullable=False, index=True, comment="过期时间（创建+72小时）")
```

#### P1-3：`borrow_record.due_date` 缺索引

**文件**: `backend/domain/borrow/models.py:44`

```python
due_date = Column(DateTime, nullable=False, comment="应还日期（借出+21天）")
```

**问题**: 定时任务 `mark_overdue_books` 和 `check_due_date_reminders` 都依赖 `due_date` 过滤。
**风险**: 同上，全表扫描。
**修复**:

```python
due_date = Column(DateTime, nullable=False, index=True, comment="应还日期（借出+21天）")
```

---

### 4.3 缓存策略 — ✅ 通过（含 1 个 P2 建议）

**通过项**:
- JWT 采用无状态设计，不依赖 Redis 存储 Token ✅
- Redis 仅用于分布式锁（`distributed_lock.py`）✅
- 分布式锁有 Redis 不可用时的降级策略（`ConnectionError → yield True`）✅
- 分布式锁使用 Lua 脚本安全释放 ✅

#### P2 建议：JWT 无状态设计的副作用

**问题**: JWT 一旦签发，在过期前无法主动失效。用户退出登录、密码修改、管理员封禁后 Token 仍然有效。
**风险**: 低。Token 有效期 2 小时（`ACCESS_TOKEN_EXPIRE_MINUTES = 120`），最大窗口期可接受。
**修复**: 如需更强控制，可在 Redis 维护一个 Token 黑名单（`jti` 字段），在 `get_current_user` 中检查。当前阶段不必须。

---

### 4.4 并发安全 — ✅ 通过（含 1 个 P2 建议）

**通过项**:
- `borrow_service.py:73`：`with_for_update()` 行锁保证借阅上限校验的原子性 ✅
- `borrow_service.py:92-99`：库存扣减使用 SQL `UPDATE Book SET available_stock = available_stock - 1 WHERE available_stock > 0`，原子操作 ✅
- `deposit/repository.py:40`：`with_for_update()` 行锁保证押金状态变更的串行化 ✅
- `deposit_service.py:52`：`get_active_by_child_for_update()` 获取行锁 ✅
- `distributed_lock.py`：定时任务使用 Redis 分布式锁防止多 worker 重复执行 ✅

#### P2 建议：`deposit_service.py:284-285` 的罚款累加竞态

**文件**: `backend/domain/deposit/service.py:284-285`

```python
child = self.db.query(Child).filter(Child.id == data.child_id, Child.is_deleted == 0).first()
if child:
    child.outstanding_fines = (child.outstanding_fines or 0) + data.amount
```

**问题**: `deduct_deposit` 和 `mark_book_lost` 都更新 `child.outstanding_fines`，但 Child 查询未加 `with_for_update()` 行锁。两个操作并发时可能出现 lost update。
**风险**: 低。`deduct_deposit` 和 `mark_book_lost` 是低频管理操作，实际并发概率极低。
**修复**: 在 Child 查询后加 `.with_for_update()` 或使用 SQL `UPDATE child SET outstanding_fines = outstanding_fines + :amount`。

---

### 4.5 资源泄漏 — ✅ 通过（含 2 个 P2 建议）

**通过项**:
- 数据库连接池配置完整：`pool_size=10, max_overflow=20, pool_pre_ping=True, pool_recycle=3600` ✅
- APScheduler 14 个任务在 `lifespan` shutdown 时通过 `stop_scheduler()` 关闭 ✅
- `get_db()` 使用 `finally: db.close()` 确保 session 归还连接池 ✅

#### P2 建议-1：`stop_scheduler(wait=False)` 不等待任务完成

**文件**: `backend/tasks/scheduler.py:148`

```python
scheduler.shutdown(wait=False)
```

**问题**: `wait=False` 意味着 shutdown 时正在执行的任务会被强制中断，可能导致数据库事务未提交/回滚。
**风险**: 低。正常关闭（如滚动更新）时定时任务在几秒内完成，且每个任务有独立的 try/except/rollback。
**修复**: 改为 `scheduler.shutdown(wait=True)`，或设置合理的超时。

#### P2 建议-2：Docker 镜像构建体积偏大

**文件**: `Dockerfile`

```dockerfile
FROM python:3.13-slim
COPY . .  # 包含 .venv, node_modules, tests, features, data 等
```

**问题**: `COPY . .` 复制了 venv（~200MB+）、node_modules、测试数据等非运行时文件。无 `.dockerignore`。
**风险**: 镜像体积过大，拉取/推送慢，攻击面大。
**修复**:

```dockerfile
# 添加 .dockerignore
.venv
node_modules
.git
tests
features
data
logs
uploads
*.md
.DS_Store
```

---

## 维度九：数据库设计评审

### 9.1 表结构规范性 — ✅ 通过

49 张表均继承 `BaseModel`（id + create_time + update_time + is_deleted），字段类型规范使用 SQLAlchemy Column 定义。外键关系通过 `ForeignKey` 声明。**通过。**

---

### 9.2 命名一致性 — ✅ 通过

**检查方法**: 扫描所有 `models.py` 的 `__tablename__` 和 `Column` 定义。

| 检查项 | 结果 |
|--------|------|
| 表名 | 全部 snake_case ✅ |
| 字段名 | 全部 snake_case ✅ |
| 索引名 | SQLAlchemy `index=True` 自动生成 `ix_{tablename}_{column}` ✅ |
| 外键名 | SQLAlchemy 自动生成 ✅ |

未发现 camelCase 混用。**通过。**

---

### 9.3 is_deleted 字段覆盖率 — ❌ P1（1 处遗漏）

#### P1-1：`FavoritesRepository.get_by_child_and_book` 未过滤 is_deleted

**文件**: `backend/domain/bookshelf/repository.py:55-63`

```python
def get_by_child_and_book(self, child_id: int, book_id: int) -> Favorites | None:
    q = self.db.query(Favorites).filter(
        Favorites.child_id == child_id,
        Favorites.book_id == book_id,
        # 缺少 Favorites.is_deleted == 0
    )
    return q.first()
```

**问题**: 这是所有 Repository 方法中唯一未自动过滤 `is_deleted` 的方法。BaseRepository 的其他方法（`get_by_id`、`list_all`、`count` 等）都自动添加了 `is_deleted == 0` 过滤。
**风险**: 软删除的收藏记录仍然能被查询到，可能导致用户看到已删除的收藏。
**修复**:

```python
q = self.db.query(Favorites).filter(
    Favorites.child_id == child_id,
    Favorites.book_id == book_id,
    Favorites.is_deleted == 0,
)
```

---

### 9.4 Alembic 迁移历史 — ✅ 通过（含 1 个 P2 建议）

**通过项**:
- 30 个迁移文件，链条连续无断裂 ✅
- 当前 Head: `96f200b6ed5a` (024_add_order_refund_remark)，revises `d9d508402c87` ✅
- `alembic check` 通过（HANDOFF.md 验证）✅
- 无合并冲突（所有 down_revision 唯一）✅

#### P2 建议：迁移文件命名规范不统一

**现象**:
- 早期：`4b61143c9ad0_001_initial_all_tables.py`（hash + 编号）
- 中期：`v31_omo_tables.py`（纯描述，无 hash 前缀）
- 近期：`d9d508402c87_023_final_drift_fix.py`（hash + 编号）

**风险**: 低。不影响功能，但增加维护认知负担。
**修复**: 统一为 alembic 自动生成格式（`{revision}_{slug}.py`），通过团队规范约束。

---

### 9.5 字符集确认 — ✅ 通过

**文件**: `backend/config.py:83`

```python
return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
```

连接字符串明确指定 `charset=utf8mb4`。所有表通过该引擎创建，自动继承 utf8mb4。**通过。**

---

## 维度十：运维与可观测性

### 10.1 日志体系 — ❌ P1（2 处缺失）

#### P1-1：request_log 日志格式非结构化

**文件**: `backend/middleware/request_log.py:29`

```python
logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
```

日志内容为管道分隔的文本：

```
2026-07-15 10:00:00,123 | INFO | GET /api/books | status=200 | cost=12.34ms | client=127.0.0.1 | admin_id=-
```

**问题**: 非 JSON 格式，无法被 ELK/Loki/Datadog 等集中式日志系统自动解析。字段提取需要正则表达式。
**修复**: 改为 JSON 格式：

```python
import json
import logging

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        return json.dumps(log_entry, ensure_ascii=False)
```

#### P1-2：request_log 未注入 trace_id

**文件**: `backend/middleware/request_log.py:64-67` vs `backend/middleware/trace.py:22-26`

**问题**: `trace_middleware` 将 `trace_id` 注入到 `request.state.trace_id`，但 `RequestLogMiddleware` 的日志格式中**没有包含 trace_id**。这导致：

```
# request_log 日志（无法关联）
GET /api/books | status=200 | cost=12ms | client=10.0.0.1 | admin_id=-

# 业务日志（有 trace_id 但无法与请求日志关联）
[abc12345] Book borrowed: child=42, book=7
```

**风险**: 排查问题时，无法从 HTTP 请求日志直接跳转到对应的业务日志链路。
**修复**: 在 `RequestLogMiddleware.dispatch` 中读取 `request.state.trace_id` 并写入日志：

```python
trace_id = getattr(request.state, "trace_id", "-")
logger.info(
    f"trace_id={trace_id} | {method} {path} | status={status} | cost={duration_ms}ms | "
    f"client={client} | admin_id={admin_id or '-'}"
)
```

---

### 10.2 监控指标 — ❌ P1（1 处缺失）

#### P1-1：缺少 Metrics 端点

**现状**: 仅有 `/health` 端点返回 `{"status": "ok", "version": "0.1.0"}`。无 Prometheus metrics 暴露。

**风险**: 
- 无法监控请求 QPS、P99 延迟、错误率
- 无法监控数据库连接池使用率
- 无法监控定时任务执行成功率
- 生产环境故障发现依赖人工或外部监控

**修复**: 引入 `prometheus-fastapi-instrumentator`:

```python
# main.py
from prometheus_fastapi_instrumentator import Instrumentator

instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app, endpoint="/metrics")
```

---

### 10.3 部署方案 — ❌ P1（1 处缺失）+ P2（1 处建议）

#### P1-1：Dockerfile 非多阶段构建，无 .dockerignore

**文件**: `Dockerfile`

```dockerfile
FROM python:3.13-slim         # 单一阶段，构建产物与运行环境混合
COPY . .                       # 复制所有文件，无过滤
```

**问题**:
1. 无多阶段构建，无法分离构建依赖和运行依赖
2. 无 `.dockerignore`（上文已确认不存在）
3. 镜像包含 `.venv`、`node_modules`、`tests`、`features`、`.git` 等
4. 预估镜像体积 > 500MB

**风险**: 镜像臃肿、构建/部署慢、安全攻击面大。
**修复**:

```dockerfile
# 多阶段构建
FROM python:3.13-slim AS builder
RUN apt-get update && apt-get install -y libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.13-slim
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev \
    fonts-noto-cjk fonts-wqy-microhei \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
WORKDIR /app
COPY backend/ ./backend/
COPY alembic/ ./alembic/
COPY alembic.ini .
EXPOSE 8002
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8002"]
```

同时创建 `.dockerignore`:

```
.venv
venv
node_modules
.git
tests
features
data
logs
uploads
design
docs
scripts
*.md
.DS_Store
.env
.env.example
```

---

### 10.4 容灾备份 — ✅ 通过（含 1 个 P2 建议）

**通过项**:
- `DEPLOY_CHECKLIST.md` 包含完整的回滚方案：DB 回滚、代码回滚、小程序回滚、服务器回滚 ✅
- 部署前数据库备份步骤明确 ✅
- 验证命令齐全（ruff, pytest, behave, integration test）✅

#### P2 建议：缺少自动化回滚脚本

**问题**: 回滚步骤依赖手动执行，紧急情况下操作窗口期长。
**修复**: 可选提供 `scripts/rollback.sh` 一键回滚脚本。当前阶段手动执行可接受。

---

### 10.5 定时任务可观测性 — ❌ P2（2 处建议）

#### P2-1：缺少任务执行状态持久化

**现状**: 14 个定时任务全部通过 `logger.info/error` 输出执行状态，但未持久化到数据库。

**风险**: 
- 无法查询"上一次会员到期提醒是否成功执行"
- 无法统计"本月逾期检测任务平均耗时"
- 日志轮转后执行历史丢失

**修复**: 可选创建 `SchedulerExecutionLog` 表：

```python
class SchedulerExecutionLog(BaseModel):
    __tablename__ = "scheduler_execution_log"
    job_name = Column(String(100), index=True)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    status = Column(SmallInteger)  # 0=success 1=failed
    error_message = Column(Text, nullable=True)
    affected_rows = Column(Integer, default=0)
```

#### P2-2：任务执行无超时控制

**文件**: `backend/common/distributed_lock.py:59`

```python
def distributed_lock(lock_key: str, timeout: int = 300):
```

分布式锁的 timeout 设置了 300 秒，但任务本身无超时控制。如果任务卡死（如数据库连接挂起），会持有锁 300 秒。
**风险**: 低。当前每个任务内部都有 try/except，且数据库操作有 MySQL 超时保护。

---

## 附录 A：问题汇总表

| 编号 | 维度 | 级别 | 文件:行号 | 问题简述 |
|------|------|------|-----------|---------|
| ARC-01 | 架构 | **P0** | `child/router.py:98-99` | Router 直接 `db.add/commit`，绕过 Service |
| ARC-02 | 架构 | **P0** | `admin/routers/admin_activities_router.py:169` | Router 直接 `db.query`，绕过 Service |
| ARC-03 | 架构 | P2 | `events.py:391-416` | 独立 session 模式 session 泄漏边缘情况 |
| ARC-04 | 架构 | P2 | `config_service.py:48` | 缓存过期时无击穿防护 |
| PERF-01 | 性能 | **P1** | `borrow/models.py:46` | `status` 字段缺索引 |
| PERF-02 | 性能 | **P1** | `reservation/models.py:30` | `expire_time` 缺索引 |
| PERF-03 | 性能 | **P1** | `borrow/models.py:44` | `due_date` 缺索引 |
| PERF-04 | 性能 | P2 | `deposit/service.py:284-285` | `outstanding_fines` 累加无行锁 |
| PERF-05 | 性能 | P2 | `tasks/scheduler.py:148` | `shutdown(wait=False)` 可能中断事务 |
| DB-01 | 数据库 | **P1** | `bookshelf/repository.py:55-63` | `get_by_child_and_book` 未过滤 `is_deleted` |
| DB-02 | 数据库 | P2 | `alembic/versions/` | 迁移文件命名规范不统一 |
| OPS-01 | 运维 | **P1** | `request_log.py:29` | 日志格式非 JSON 结构化 |
| OPS-02 | 运维 | **P1** | `request_log.py:64-67` | 日志未注入 trace_id |
| OPS-03 | 运维 | **P1** | `main.py` | 缺少 `/metrics` 端点 |
| OPS-04 | 运维 | **P1** | `Dockerfile` | 非多阶段构建，无 `.dockerignore` |
| OPS-05 | 运维 | P2 | 全局 | 缺少定时任务执行状态持久化 |
| OPS-06 | 运维 | P2 | 全局 | 缺少自动化回滚脚本 |

---

## 附录 B：发版建议

**P0 项（2 项）必须在上线前修复。** 均为 Router 层 ORM 违规，修复成本低（各 < 30 行代码）。

**P1 项（6 项）建议在上线前修复。** 其中：
- 3 个索引缺失（PERF-01/02/03）直接影响数据库查询性能，随数据量增长风险递增
- 日志缺少 trace_id（OPS-01/02）严重影响问题排查效率
- Metrics 缺失（OPS-03）可通过 `prometheus-fastapi-instrumentator` 一行代码解决
- Dockerfile（OPS-04）需要 20 分钟重构

**P2 项（9 项）可在上线后迭代修复。** 均为优化改进，不影响核心功能。

---

> **签署**: 高见远 | 首席架构师 | 2026-07-15
